import os
import random
from datetime import datetime
from supabase import create_client, Client

# Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabase credentials bulunamadı!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Semboller
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

def fetch_bist_prices():
    """BIST fiyatlarını çek ve Supabase'e kaydet"""
    today = datetime.now().date().isoformat()
    
    print(f"\n{'='*60}")
    print(f"🔄 BIST Fiyat Çekme Başlıyor")
    print(f"📅 Tarih: {today}")
    print(f"{'='*60}\n")
    
    all_symbols = SYMBOLS['benchmarks'] + SYMBOLS['stocks']
    success_count = 0
    
    for symbol in all_symbols:
        try:
            # ŞİMDİLİK MOCK DATA (Gerçek BIST API ile değiştir)
            mock_price = round(50 + random.random() * 100, 2)
            
            # Supabase'e kaydet (upsert = varsa güncelle, yoksa ekle)
            supabase.table('daily_prices').upsert({
                'symbol': symbol,
                'date': today,
                'close_price': mock_price,
                'source': 'bist'
            }).execute()
            
            success_count += 1
            print(f"✅ {symbol}: {mock_price} TL")
            
        except Exception as e:
            print(f"❌ {symbol} hatası: {e}")
    
    print(f"\n{'='*60}")
    print(f"🎉 {success_count}/{len(all_symbols)} fiyat kaydedildi!")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    fetch_bist_prices()
