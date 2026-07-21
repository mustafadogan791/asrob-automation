"""
bist_scraper.py
GitHub Actions ile her gün 18:30 Türkiye saatinde (15:30 UTC) çalışır.
BIST hisselerini Bigpara'dan (Yahoo yedekli), endeksleri Yahoo Finance'den
çekip Supabase'e kaydeder.
"""

import argparse
import os
import time
from datetime import date, datetime, timedelta
import requests
import yfinance as yf
from zoneinfo import ZoneInfo
from supabase import create_client, Client
from price_integrity import PriceQuote, extract_bigpara_quotes

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabase credentials bulunamadı!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BIGPARA_DETAIL_URL = (
    "https://bigpara.hurriyet.com.tr/api/v1/borsa/hisseyuzeysel/{symbol}"
)
HTTP_TIMEOUT_SECONDS = 15

http = requests.Session()
http.headers.update({
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://bigpara.hurriyet.com.tr/borsa/hisse-fiyatlari/',
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/126.0 Safari/537.36'
    ),
})

ISTANBUL_TZ = ZoneInfo('Europe/Istanbul')

# ============================================================
# SEMBOLLER
# ============================================================

BENCHMARKS = ['XU100', 'XU030', 'XU050', 'XBANK', 'XUSIN', 'XELKT',
               'XGIDA', 'XKAGT', 'XMESY', 'XTEKS', 'XUTEK', 'XUHIZ',
               'XTRZM', 'XULAS', 'XILTM', 'XSGRT', 'XKMYA', 'XHOLD', 'XTAST']

STOCKS = [
    'AKBNK', 'AKSA', 'AKSEN', 'ALARK', 'ALTNY', 'ANSGR', 'AEFES', 'ARCLK',
    'ASELS', 'ASTOR', 'BALSU', 'BTCIM', 'BSOKE', 'BERA', 'BIMAS', 'BRSAN',
    'BRYAT', 'CCOLA', 'CVKMD', 'CWENE', 'CANTE', 'CIMSA', 'DAPGM', 'DSTKF',
    'DOHOL', 'DOAS', 'EFOR', 'ECILC', 'EKGYO', 'ENJSA', 'ENERY', 'ENKAI',
    'EREGL', 'ESEN', 'EUREN', 'EUPWR', 'FENER', 'FROTO', 'GSRAY', 'GENIL',
    'GESAN', 'GRTHO', 'GUBRF', 'GLRMK', 'GRSEL', 'SAHOL', 'HEKTS', 'IEYHO',
    'ISMEN', 'IZENR', 'KRDMD', 'KTLEV', 'KLRHO', 'KCHOL', 'KUYAS', 'MAGEN',
    'MAVI', 'MIATK', 'MGROS', 'MPARK', 'OBAMS', 'ODAS', 'ODINE', 'OTKAR',
    'OYAKC', 'PASEU', 'PSGYO', 'PAHOL', 'PATEK', 'PGSUS', 'PETKM', 'QUAGR',
    'RALYH', 'REEDR', 'SARKY', 'SASA', 'SKBNK', 'SOKM', 'TAVHL', 'TKFEN',
    'TOASO', 'TRMET', 'TRENJ', 'TUKAS', 'TCELL', 'TUPRS', 'TRALT', 'THYAO',
    'GARAN', 'HALKB', 'ISCTR', 'TSKB', 'TURSG', 'SISE', 'VAKBN', 'TTKOM',
    'ULKER', 'VESTL', 'YKBNK', 'ZOREN',
]

# ============================================================
# FİYAT ÇEKME (Bigpara + Yahoo yedeği)
# ============================================================

def fetch_bigpara_quote(symbol: str, target_date: date) -> PriceQuote | None:
    """Fetch a Bigpara quote only when its own timestamp matches target_date."""
    for attempt in range(1, 4):
        try:
            response = http.get(
                BIGPARA_DETAIL_URL.format(symbol=symbol),
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            quotes = extract_bigpara_quotes(response.json(), symbol)
            matching = [quote for quote in quotes if quote.as_of_date == target_date]
            if matching:
                quote = matching[0]
                return PriceQuote(round(quote.price, 4), quote.source, target_date)

            dates = sorted({quote.as_of_date.isoformat() for quote in quotes})
            detail = ', '.join(dates) if dates else 'tarihli fiyat yok'
            print(
                f"  ⚠️  {symbol}: Bigpara verisi {target_date} gününe ait değil "
                f"({detail})"
            )
            return None
        except (requests.RequestException, ValueError) as exc:
            print(f"  ⚠️  {symbol}: Bigpara deneme {attempt}/3 başarısız ({exc})")
            if attempt < 3:
                time.sleep(attempt)
    return None


def fetch_yahoo_quote(symbol: str, target_date: date) -> PriceQuote | None:
    """Fetch the unadjusted Yahoo close for the exact requested trading date."""
    try:
        ticker = yf.Ticker(f"{symbol}.IS")
        hist = ticker.history(
            start=target_date.isoformat(),
            end=(target_date + timedelta(days=1)).isoformat(),
            auto_adjust=False,
        )
        if not hist.empty and 'Close' in hist:
            row_date = hist.index[-1].date()
            if row_date != target_date:
                print(
                    f"  ⚠️  {symbol}: Yahoo verisi {target_date} yerine "
                    f"{row_date} gününe ait"
                )
                return None
            price = round(float(hist['Close'].iloc[-1]), 4)
            return PriceQuote(price, 'yahoo_finance', row_date)
        return None
    except Exception as e:
        print(f"  ⚠️  {symbol}: {e}")
        return None


def fetch_price(symbol: str, kind: str, target_date: date) -> PriceQuote | None:
    """Fetch a date-verified quote, preferring Bigpara for stocks."""
    if kind == 'stock':
        bigpara_quote = fetch_bigpara_quote(symbol, target_date)
        if bigpara_quote is not None:
            return bigpara_quote

    return fetch_yahoo_quote(symbol, target_date)

# ============================================================
# POLL OLUŞTURMA (Her gün yeni poll'lar)
# ============================================================

def create_daily_polls(date_str: str):
    """Bugünün poll'larını oluştur (yoksa)"""
    existing = supabase.table('polls').select('id').eq('date', date_str).limit(1).execute()
    if existing.data:
        print(f"✅ {date_str} için poll'lar zaten var ({len(existing.data)} kayıt)")
        return

    print(f"📋 {date_str} için yeni poll'lar oluşturuluyor...")

    benchmarks = [
        {'symbol': 'XU100', 'name': 'BIST 100'},
        {'symbol': 'XU030', 'name': 'BIST 30'},
        {'symbol': 'XU050', 'name': 'BIST 50'},
        {'symbol': 'XBANK', 'name': 'Bankacılık'},
        {'symbol': 'XUSIN', 'name': 'Sanayi'},
        {'symbol': 'XELKT', 'name': 'Elektrik'},
        {'symbol': 'XGIDA', 'name': 'Gıda'},
        {'symbol': 'XKAGT', 'name': 'Kağıt'},
        {'symbol': 'XMESY', 'name': 'Maden'},
        {'symbol': 'XTEKS', 'name': 'Tekstil'},
        {'symbol': 'XUTEK', 'name': 'Teknoloji'},
        {'symbol': 'XUHIZ', 'name': 'Hizmetler'},
        {'symbol': 'XTRZM', 'name': 'Turizm'},
        {'symbol': 'XULAS', 'name': 'Ulaştırma'},
        {'symbol': 'XILTM', 'name': 'İletişim'},
        {'symbol': 'XSGRT', 'name': 'Sigorta'},
        {'symbol': 'XKMYA', 'name': 'Kimya'},
        {'symbol': 'XHOLD', 'name': 'Holding'},
        {'symbol': 'XTAST', 'name': 'Taş Toprak'},
    ]

    benchmark_polls = [
        {'date': date_str, 'symbol': b['symbol'], 'kind': 'benchmark',
         'question': f"{b['name']} ({b['symbol']}) yarın nasıl kapanır?",
         'positive_count': 0, 'neutral_count': 0, 'negative_count': 0}
        for b in benchmarks
    ]

    stock_polls = [
        {'date': date_str, 'symbol': s, 'kind': 'stock',
         'question': f"{s} yarın nasıl kapanır?",
         'positive_count': 0, 'neutral_count': 0, 'negative_count': 0}
        for s in STOCKS
    ]

    supabase.table('polls').insert(benchmark_polls).execute()
    supabase.table('polls').insert(stock_polls).execute()
    print(f"✅ {len(benchmark_polls) + len(stock_polls)} poll oluşturuldu!")

# ============================================================
# ANA FONKSIYON
# ============================================================

def next_business_day(day):
    """Resmi tatiller hariç bir sonraki hafta içini döndür."""
    candidate = day + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def fetch_and_store_prices(date_str: str):
    """Kapanış fiyatlarını çek ve günlük fiyat tablosuna kaydet."""
    print(f"\n{'='*60}")
    print(f"🔄 BIST Kapanış Fiyatları - {date_str}")
    print(f"{'='*60}\n")

    target_date = date.fromisoformat(date_str)
    if target_date.weekday() >= 5:
        raise ValueError(f'{date_str} işlem günü değil; fiyat yazılmadı.')

    all_symbols = (
        [(symbol, 'benchmark') for symbol in BENCHMARKS]
        + [(symbol, 'stock') for symbol in STOCKS]
    )
    success = 0
    fail = 0

    for symbol, kind in all_symbols:
        quote = fetch_price(symbol, kind, target_date)
        if quote is not None:
            supabase.table('daily_prices').upsert({
                'symbol': symbol,
                'date': quote.as_of_date.isoformat(),
                'close_price': quote.price,
                'source': quote.source,
            }, on_conflict='symbol,date').execute()
            success += 1
            print(
                f"  ✅ {symbol}: {quote.price:.2f} TL "
                f"({quote.source}, {quote.as_of_date})"
            )
        else:
            fail += 1
            print(f"  ❌ {symbol}: Fiyat bulunamadı")

    print(f"\n🎉 Fiyat çekme tamamlandı: {success} başarılı, {fail} başarısız")
    if success == 0:
        raise RuntimeError('Hiçbir kapanış fiyatı alınamadı; puanlama durduruldu.')


def main(mode: str, requested_date: str | None = None):
    today = (
        date.fromisoformat(requested_date)
        if requested_date
        else datetime.now(ISTANBUL_TZ).date()
    )
    today_str = today.isoformat()

    if mode in ('prices', 'all'):
        fetch_and_store_prices(today_str)

    if mode in ('polls', 'all'):
        poll_date = next_business_day(today)
        create_daily_polls(poll_date.isoformat())
        print(f"✅ {poll_date.isoformat()} işlem günü anketleri hazır")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--mode',
        choices=['prices', 'polls', 'all'],
        default='all',
        help='18:25 prices, 18:30 polls; all yalnızca elle test içindir.',
    )
    parser.add_argument(
        '--date',
        help='Fiyat geri doldurma testi için hedef işlem günü (YYYY-MM-DD).',
    )
    args = parser.parse_args()
    main(args.mode, args.date)
