"""
send_notification.py
Firebase Cloud Messaging ile push bildirimi gönderir.
GitHub Actions tarafından çağrılır.

Kullanım:
  python send_notification.py --type market_close
  python send_notification.py --type market_open
  python send_notification.py --type streak_warning --user_id <id>
"""

import os
import sys
import argparse
import requests
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY")  # Firebase Console > Proje Ayarları > Cloud Messaging

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# FCM GÖNDERME
# ============================================================

def send_fcm(token: str, title: str, body: str, data: dict = None):
    """Tek bir cihaza FCM bildirimi gönder"""
    if not FCM_SERVER_KEY:
        print("⚠️  FCM_SERVER_KEY bulunamadı, bildirim gönderilemedi")
        return False

    payload = {
        "to": token,
        "notification": {
            "title": title,
            "body": body,
            "sound": "default",
        },
        "data": data or {},
        "android": {
            "priority": "high",
            "notification": {"channel_id": "asrob_main"},
        },
    }

    response = requests.post(
        "https://fcm.googleapis.com/fcm/send",
        json=payload,
        headers={
            "Authorization": f"key={FCM_SERVER_KEY}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    return response.status_code == 200


def send_to_topic(topic: str, title: str, body: str):
    """Bir topic'e abone tüm kullanıcılara gönder"""
    if not FCM_SERVER_KEY:
        print("⚠️  FCM_SERVER_KEY bulunamadı")
        return

    payload = {
        "to": f"/topics/{topic}",
        "notification": {"title": title, "body": body, "sound": "default"},
    }
    requests.post(
        "https://fcm.googleapis.com/fcm/send",
        json=payload,
        headers={"Authorization": f"key={FCM_SERVER_KEY}", "Content-Type": "application/json"},
        timeout=10,
    )


# ============================================================
# BİLDİRİM TÜRLERİ
# ============================================================

def notify_market_close():
    """18:30 - Borsa kapandı, oylama açıldı"""
    print("📲 Piyasa kapanış bildirimleri gönderiliyor...")

    # Tüm kullanıcılara (topic ile)
    send_to_topic(
        "all_users",
        "📊 Oylama Açıldı! 🔔",
        "Borsa kapandı. Yarın için tahminini yap ve lider tablosunda yüksel!",
    )
    print("✅ Kapanış bildirimi gönderildi")


def notify_market_open():
    """09:30 - Borsa açıldı, puanlar hesaplandı"""
    print("📲 Piyasa açılış bildirimleri gönderiliyor...")

    # Tüm kullanıcılara genel bildirim
    send_to_topic(
        "all_users",
        "🔔 Borsa Açıldı! Oylama Kapandı",
        "Tahmin sonuçların hesaplandı. Puanlarını kontrol et!",
    )

    # Bireysel bildirimler: doğru tahmin sayısı + streak uyarısı
    try:
        users = supabase.table("users").select("id, fcm_token, username, current_streak").not_.is_("fcm_token", "null").execute()

        for user in users.data:
            token = user.get("fcm_token")
            if not token:
                continue

            user_id = user["id"]
            username = user.get("username", "Kullanıcı")
            streak = user.get("current_streak", 0)

            # Bugün kaç doğru tahmin?
            from datetime import date
            today = date.today().isoformat()
            correct = supabase.table("prediction_results").select("id").eq("user_id", user_id).eq("result_date", today).eq("is_correct", True).execute()
            correct_count = len(correct.data) if correct.data else 0

            if correct_count > 0:
                send_fcm(
                    token,
                    f"🎯 {correct_count} Doğru Tahmin!",
                    f"Harika gün {username}! {correct_count} tahminin doğru çıktı. {'🔥' * min(streak, 4)} Seri: {streak}",
                )

        print("✅ Bireysel bildirimler gönderildi")

    except Exception as e:
        print(f"❌ Bireysel bildirim hatası: {e}")


def notify_streak_warnings():
    """Streak kırılmak üzere olan kullanıcılara uyarı (opsiyonel, gün içi çalışabilir)"""
    try:
        users = supabase.table("users").select("id, fcm_token, username, current_streak").gt("current_streak", 2).not_.is_("fcm_token", "null").execute()

        from datetime import date
        today = date.today().isoformat()
        count = 0

        for user in users.data:
            token = user.get("fcm_token")
            if not token:
                continue

            # Bugün oy vermiş mi?
            voted = supabase.table("votes").select("id").eq("user_id", user["id"]).gte("created_at", f"{today}T00:00:00").execute()

            if not voted.data:
                streak = user.get("current_streak", 0)
                username = user.get("username", "")
                send_fcm(
                    token,
                    "⚠️ Streakini Kaybedeceksin!",
                    f"{username}, {streak} günlük seriniz tehlikede! Hemen tahminini yap 🔥",
                )
                count += 1

        print(f"✅ {count} streak uyarısı gönderildi")

    except Exception as e:
        print(f"❌ Streak uyarı hatası: {e}")


# ============================================================
# ANA
# ============================================================

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
