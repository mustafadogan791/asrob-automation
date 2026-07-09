"""
bist_scraper.py
GitHub Actions ile her gün 18:30 Türkiye saatinde (15:30 UTC) çalışır.
Yahoo Finance'den BIST fiyatlarını çekip Supabase'e kaydeder.
"""

import os
import yfinance as yf
from datetime import datetime, timedelta
from supabase import create_client, Client

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabase credentials bulunamadı!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
# FİYAT ÇEKME (Yahoo Finance)
# ============================================================

def fetch_price(symbol: str) -> float | None:
    """Yahoo Finance'den kapanış fiyatı çek. .IS = Istanbul Stock Exchange"""
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

def main():
    today = datetime.now().date()
    today_str = today.isoformat()

    print(f"\n{'='*60}")
    print(f"🔄 BIST Fiyat Çekme - {today_str}")
    print(f"{'='*60}\n")

    # 1. Bugünün poll'larını oluştur (yoksa)
    create_daily_polls(today_str)

    # 2. Fiyatları çek
    all_symbols = BENCHMARKS + STOCKS
    success = 0
    fail = 0

    for symbol in all_symbols:
        price = fetch_price(symbol)
        if price:
  supabase.table('daily_prices').upsert({
                'symbol': symbol,
                'date': today_str,
                'close_price': price,
                'source': 'yahoo_finance',
            }, on_conflict='symbol,date').execute()
            success += 1
            print(f"  ✅ {symbol}: {price:.2f} TL")
        else:
            fail += 1
            print(f"  ❌ {symbol}: Fiyat bulunamadı")

    print(f"\n{'='*60}")
    print(f"🎉 Tamamlandı: {success} başarılı, {fail} başarısız")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
