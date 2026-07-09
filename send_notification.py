"""
send_notification.py
Firebase Cloud Messaging ile push bildirimi gönderir (firebase-admin SDK).
GitHub Actions tarafından çağrılır.

Kullanım:
  python send_notification.py --type market_close
  python send_notification.py --type market_open
  python send_notification.py --type streak_warning
"""

import os
import argparse
from datetime import date
from supabase import create_client, Client
import firebase_admin
from firebase_admin import credentials, messaging

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase bilgileri eksik!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)


def send_fcm(token: str, title: str, body: str, data: dict = None):
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(channel_id="asrob_main", sound="default"),
            ),
        )
        messaging.send(message)
        return True
    except Exception as e:
        print(f"Gonderim hatasi ({token[:12]}...): {e}")
        return False


def send_to_topic(topic: str, title: str, body: str):
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            topic=topic,
        )
        messaging.send(message)
        print(f"Topic bildirimi gonderildi: {topic}")
    except Exception as e:
        print(f"Topic gonderim hatasi: {e}")


def notify_market_close():
    print("Piyasa kapanis bildirimleri gonderiliyor...")
    send_to_topic(
        "all_users",
        "Oylama Acildi!",
        "Borsa kapandi. Yarin icin tahminini yap ve lider tablosunda yuksel!",
    )
    print("Kapanis bildirimi gonderildi")


def notify_market_open():
    print("Piyasa acilis bildirimleri gonderiliyor...")

    send_to_topic(
        "all_users",
        "Borsa Acildi! Oylama Kapandi",
        "Tahmin sonuclarin hesaplandi. Puanlarini kontrol et!",
    )

    try:
        users = supabase.table("users").select("id, fcm_token, username, current_streak").not_.is_("fcm_token", "null").execute()

        sent_count = 0
        for user in users.data:
            token = user.get("fcm_token")
            if not token:
                continue

            user_id = user["id"]
            username = user.get("username", "Kullanici")
            streak = user.get("current_streak", 0)

            today = date.today().isoformat()
            correct = supabase.table("prediction_results").select("id").eq("user_id", user_id).eq("result_date", today).eq("is_correct", True).execute()
            correct_count = len(correct.data) if correct.data else 0

            if correct_count > 0:
                success = send_fcm(
                    token,
                    f"{correct_count} Dogru Tahmin!",
                    f"Harika gun {username}! {correct_count} tahminin dogru cikti. Seri: {streak}",
                )
                if success:
                    sent_count += 1

        print(f"{sent_count} bireysel bildirim gonderildi")

    except Exception as e:
        print(f"Bireysel bildirim hatasi: {e}")


def notify_streak_warnings():
    try:
        users = supabase.table("users").select("id, fcm_token, username, current_streak").gt("current_streak", 2).not_.is_("fcm_token", "null").execute()

        today = date.today().isoformat()
        count = 0

        for user in users.data:
            token = user.get("fcm_token")
            if not token:
                continue

            voted = supabase.table("votes").select("id").eq("user_id", user["id"]).gte("created_at", f"{today}T00:00:00").execute()

            if not voted.data:
                streak = user.get("current_streak", 0)
                username = user.get("username", "")
                success = send_fcm(
                    token,
                    "Streakini Kaybedeceksin!",
                    f"{username}, {streak} gunluk seriniz tehlikede! Hemen tahminini yap",
                )
                if success:
                    count += 1

        print(f"{count} streak uyarisi gonderildi")

    except Exception as e:
        print(f"Streak uyari hatasi: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["market_close", "market_open", "streak_warning"], required=True)
    args = parser.parse_args()

    if args.type == "market_close":
        notify_market_close()
    elif args.type == "market_open":
        notify_market_open()
    elif args.type == "streak_warning":
        notify_streak_warnings()
