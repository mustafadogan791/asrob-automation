import os
import yfinance as yf
from datetime import datetime
from supabase import create_client, Client

# Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabase credentials bulunamadı!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Semboller (5 endeks + 100 hisse)
SYMBOLS = {
    'benchmarks': ['XU100', 'XU030', 'XBANK', 'XUSIN', 'XELKT'],
    'stocks': [
        'AEFES', 'AGHOL', 'AKBNK', 'AKFGY', 'AKFYE', 'AKGRT', 'AKSA', 'AKSEN',
        'ALARK', 'ALBRK', 'ALFAS', 'ALGYO', 'ALKIM', 'ALTIN', 'ARCLK', 'ASELS',
        'ASUZU', 'BAGFS', 'BERA', 'BIENY', 'BIMAS', 'BIOEN', 'BRISA', 'BRSAN',
        'BRYAT', 'BYDNR', 'CCOLA', 'CIMSA', 'CONSE', 'CWENE', 'DEVA',
        'DOAS', 'DOHOL', 'ECILC', 'EGEEN', 'EKGYO', 'ENJSA', 'ENKAI', 'EREGL',
        'EUPWR', 'EUREN', 'FROTO', 'GARAN', 'GENIL', 'GENTS', 'GESAN', 'GOLTS',
        'GOODY', 'GOZDE', 'GUBRF', 'GWIND', 'HALKB', 'HEKTS', 'INDES', 'IPEKE',
        'ISCTR', 'ISGYO', 'ISMEN', 'KARSN', 'KAYSE', 'KCHOL', 'KONKA', 'KONTR',
        'KONYA', 'KORDS', 'KOZAA', 'KOZAL', 'KRDMD', 'KZBGY', 'MAVI', 'MGROS',
        'MIATK', 'ODAS', 'OYAKC', 'OZKGY', 'PAPIL', 'PARSN', 'PENTA', 'PETKM',
        'PGSUS', 'PKART', 'PSGYO', 'QUAGR', 'RALYH', 'RTALB', 'SAHOL', 'SASA',
        'SELEC', 'SISE', 'SKBNK', 'SOKM', 'TAVHL', 'TCELL', 'THYAO', 'TKFEN',
        'TKNSA', 'TOASO', 'TRGYO', 'TSKB', 'TTKOM', 'TTRAK', 'TUPRS', 'TURSG',
        'ULKER', 'VAKBN', 'VESTL', 'VESBE', 'YKBNK', 'YYLGD', 'ZOREN'
    ]
}

def fetch_real_bist_price(symbol):
    """Gerçek BIST fiyatını Yahoo Finance'den çek"""
    try:
        # BIST sembolleri için .IS uzantısı (Istanbul Stock Exchange)
        ticker = yf.Ticker(f"{symbol}.IS")
        
        # Son 2 günün verisini çek (bugün kapanış olmayabilir)
        data = ticker.history(period="2d")
        
        if not data.empty:
            # Son kapanış fiyatını al
            close_price = round(data['Close'].iloc[-1], 2)
            return close_price
        else:
            return None
    except Exception as e:
        print(f"⚠️ {symbol} Yahoo Finance hatası: {e}")
        return None

def fetch_bist_prices():
    """BIST fiyatlarını çek ve Supabase'e kaydet"""
    today = datetime.now().date().isoformat()
    
    print(f"\n{'='*60}")
    print(f"🔄 BIST Fiyat Çekme Başlıyor (Yahoo Finance)")
    print(f"📅 Tarih: {today}")
    print(f"{'='*60}\n")
    
    all_symbols = SYMBOLS['benchmarks'] + SYMBOLS['stocks']
    success_count = 0
    fail_count = 0
    
    for symbol in all_symbols:
        try:
            # Gerçek fiyatı çek
            real_price = fetch_real_bist_price(symbol)
            
            if real_price:
                # Supabase'e kaydet
                supabase.table('daily_prices').upsert({
                    'symbol': symbol,
                    'date': today,
                    'close_price': real_price,
                    'source': 'yahoo_finance'
                }).execute()
                
                success_count += 1
                print(f"✅ {symbol}: {real_price} TL")
            else:
                fail_count += 1
                print(f"❌ {symbol}: Fiyat bulunamadı")
            
        except Exception as e:
            fail_count += 1
            print(f"❌ {symbol} hatası: {e}")
    
    print(f"\n{'='*60}")
    print(f"🎉 {success_count}/{len(all_symbols)} başarılı")
    print(f"❌ {fail_count} başarısız")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    fetch_bist_prices()
