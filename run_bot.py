# ~/jobeni-sD/run_bot.py
from app import create_app
from app.telegram_bot import BOT_TOKEN, handle_telegram_webhook
import requests
import time

app = create_app()

def start_polling():
    offset = 0
    print("🤖 Jobeni Bot is now polling (Local Mode)...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35).json()

            if "result" in response:
                for update in response["result"]:
                    with app.app_context():
                        handle_telegram_webhook(update) # استدعاء الدالة المحدثة
                    offset = update["update_id"] + 1
        except Exception as e:
            print(f"📡 Waiting for connection... {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_polling()
