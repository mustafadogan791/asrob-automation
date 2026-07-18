"""
bist_scraper.py
GitHub Actions ile her gün 18:30 Türkiye saatinde (15:30 UTC) çalışır.
BIST hisselerini Bigpara'dan (Yahoo yedekli), endeksleri Yahoo Finance'den
çekip Supabase'e kaydeder.
"""

import argparse
import os
from typing import Any

import requests
import yfinance as yf
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from supabase import create_client, Client

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

def _to_float(value: Any) -> float | None:
    """Bigpara'nın sayı/string değerlerini güvenli biçimde float'a çevir."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    normalized = value.strip().replace(' ', '')
    if not normalized:
        return None
    if ',' in normalized:
        normalized = normalized.replace('.', '').replace(',', '.')

    try:
        return float(normalized)
    except ValueError:
        return None


def _find_bigpara_close(value: Any, symbol: str) -> float | None:
    """Bigpara yanıtındaki kapanış değerini şema değişikliklerine toleranslı bul."""
    if isinstance(value, dict):
        response_symbol = str(value.get('sembol', '')).upper()
        if not response_symbol or response_symbol == symbol:
            for key in ('kapanis', 'son', 'fiyat'):
                price = _to_float(value.get(key))
                if price is not None and price > 0:
                    return price
        for child in value.values():
            price = _find_bigpara_close(child, symbol)
            if price is not None:
                return price
    elif isinstance(value, list):
        for child in value:
            price = _find_bigpara_close(child, symbol)
            if price is not None:
                return price
    return None


def fetch_bigpara_price(symbol: str) -> float | None:
    """Bigpara yüzeysel hisse servisinden son/kapanış fiyatını çek."""
    try:
        response = http.get(
            BIGPARA_DETAIL_URL.format(symbol=symbol),
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        price = _find_bigpara_close(response.json(), symbol)
        return round(price, 4) if price is not None else None
    except (requests.RequestException, ValueError) as exc:
        print(f"  ⚠️  {symbol}: Bigpara erişilemedi ({exc})")
        return None


def fetch_yahoo_price(symbol: str) -> float | None:
    """Yahoo Finance'den kapanış fiyatı çek. .IS = Istanbul Stock Exchange."""
    try:
        ticker = yf.Ticker(f"{symbol}.IS")
        hist = ticker.history(period="2d")
        if not hist.empty:
            price = round(float(hist['Close'].iloc[-1]), 2)
            return price
        return None
    except Exception as e:
        print(f"  ⚠️  {symbol}: {e}")
        return None


def fetch_price(symbol: str, kind: str) -> tuple[float | None, str | None]:
    """Hisselerde Bigpara'yı, başarısızsa Yahoo'yu; endekslerde Yahoo'yu kullan."""
    if kind == 'stock':
        bigpara_price = fetch_bigpara_price(symbol)
        if bigpara_price is not None:
            return bigpara_price, 'bigpara'

    yahoo_price = fetch_yahoo_price(symbol)
    if yahoo_price is not None:
        return yahoo_price, 'yahoo_finance'
    return None, None

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

    all_symbols = (
        [(symbol, 'benchmark') for symbol in BENCHMARKS]
        + [(symbol, 'stock') for symbol in STOCKS]
    )
    success = 0
    fail = 0

    for symbol, kind in all_symbols:
        price, source = fetch_price(symbol, kind)
        if price:
            supabase.table('daily_prices').upsert({
                'symbol': symbol,
                'date': date_str,
                'close_price': price,
                'source': source,
            }, on_conflict='symbol,date').execute()
            success += 1
            print(f"  ✅ {symbol}: {price:.2f} TL")
        else:
            fail += 1
            print(f"  ❌ {symbol}: Fiyat bulunamadı")

    print(f"\n🎉 Fiyat çekme tamamlandı: {success} başarılı, {fail} başarısız")
    if success == 0:
        raise RuntimeError('Hiçbir kapanış fiyatı alınamadı; puanlama durduruldu.')


def main(mode: str):
    today = datetime.now(ISTANBUL_TZ).date()
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
    args = parser.parse_args()
    main(args.mode)
