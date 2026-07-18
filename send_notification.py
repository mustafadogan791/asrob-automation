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
from collections import defaultdict
from datetime import date
from dotenv import load_dotenv
from supabase import create_client, Client
import firebase_admin
from firebase_admin import credentials, messaging

load_dotenv()

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


def get_users_with_tokens():
    response = supabase.table("users").select(
        "id, fcm_token, username, current_streak"
    ).not_.is_("fcm_token", "null").execute()
    return response.data or []


def notify_poll_opened():
    print("Yeni anket bildirimleri gonderiliyor...")
    sent_count = 0
    for user in get_users_with_tokens():
        if send_fcm(
            user["fcm_token"],
            "Yeni Oylama Acildi!",
            "Yarin icin tahminini yap, Asro Puanini ve serini buyut!",
            {"type": "poll_opened"},
        ):
            sent_count += 1
    print(f"{sent_count} yeni anket bildirimi gonderildi")


def notify_results_ready():
    print("Puan sonucu bildirimleri gonderiliyor...")
    today = date.today().isoformat()
    results_response = supabase.table("prediction_results").select(
        "user_id, points_earned, accuracy_level"
    ).eq("result_date", today).execute()

    summaries = defaultdict(lambda: {"points": 0, "exact": 0, "total": 0})
    for result in results_response.data or []:
        summary = summaries[result["user_id"]]
        summary["points"] += int(result.get("points_earned") or 0)
        summary["total"] += 1
        if result.get("accuracy_level") == "exact":
            summary["exact"] += 1

    sent_count = 0
    for user in get_users_with_tokens():
        summary = summaries.get(user["id"])
        if not summary:
            continue

        username = user.get("username") or "Kullanici"
        body = (
            f"{username}, {summary['total']} tahmin sonuclandi: "
            f"{summary['exact']} tam isabet, {summary['points']} Asro Puan!"
        )
        if send_fcm(
            user["fcm_token"],
            "Puanlarin Hazir!",
            body,
            {"type": "results_ready", "result_date": today},
        ):
            sent_count += 1
    print(f"{sent_count} sonuc bildirimi gonderildi")


def notify_market_close():
    """Eski komutla uyumluluk: yeni anket bildirimi."""
    notify_poll_opened()


def notify_market_open():
    print("Oylama kapanis bildirimleri gonderiliyor...")
    sent_count = 0
    for user in get_users_with_tokens():
        if send_fcm(
            user["fcm_token"],
            "Oylama Kapandi",
            "Bugunun tahminleri kilitlendi. Sonuclar borsa kapanisindan sonra!",
            {"type": "voting_closed"},
        ):
            sent_count += 1
    print(f"{sent_count} oylama kapanis bildirimi gonderildi")


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
    parser.add_argument(
        "--type",
        choices=[
            "market_close",
            "market_open",
            "poll_opened",
            "results_ready",
            "streak_warning",
        ],
        required=True,
    )
    args = parser.parse_args()

    if args.type == "market_close":
        notify_market_close()
    elif args.type == "market_open":
        notify_market_open()
    elif args.type == "poll_opened":
        notify_poll_opened()
    elif args.type == "results_ready":
        notify_results_ready()
    elif args.type == "streak_warning":
        notify_streak_warnings()
