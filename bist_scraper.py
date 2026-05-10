import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo


from supabase import create_client
from tradingview_ta import TA_Handler, Interval, Exchange


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TZ = ZoneInfo("Europe/Istanbul")


TARGET_ASSETS = {
    "XU100": "index",
    "THYAO": "stock",
    "ASELS": "stock",

}


def get_analysis(symbol):
    handler = TA_Handler(
        symbol=symbol,
        screener="turkey",
        exchange="BIST",
        interval=Interval.INTERVAL_1_DAY,
    )

    return handler.get_analysis()


def build_rows():
    now = datetime.now(TZ)
    price_date = now.date().isoformat()

    rows = []

    for symbol, asset_type in TARGET_ASSETS.items():

        try:
            analysis = get_analysis(symbol)

            indicators = analysis.indicators

            close_price = indicators.get("close")
            open_price = indicators.get("open")
            high_price = indicators.get("high")
            low_price = indicators.get("low")
            volume = indicators.get("volume")

            change_percent = None

            if close_price and open_price:
                change_percent = (
                    (close_price - open_price) / open_price
                ) * 100

            row = {
                "asset_code": symbol,
                "symbol": symbol,
                "asset_type": asset_type,
                "price_date": price_date,
                "open_price": open_price,
                "high_price": high_price,
                "low_price": low_price,
                "close_price": close_price,
                "change_percent": change_percent,
                "volume": volume,
                "source": "tradingview",
                "fetched_at": now.isoformat(),
            }

            rows.append(row)

            print(f"[OK] {symbol} çekildi")
            time.sleep(3)

        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
            time.sleep(5)

    return rows


def save_rows(rows):

    if not rows:
        print("[WARN] Veri yok")
        return

    supabase.table("daily_prices").upsert(
        rows,
        on_conflict="asset_code,price_date",
    ).execute()

    print(f"[OK] {len(rows)} kayıt kaydedildi")


def main():

    print("AsroB TradingView scraper başladı...")

    rows = build_rows()

    save_rows(rows)

    print("AsroB TradingView scraper tamamlandı.")


if __name__ == "__main__":
    main()
