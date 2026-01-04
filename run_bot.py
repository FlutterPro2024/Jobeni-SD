# run_bot.py
from app import create_app
from app.telegram_bot import BOT_TOKEN
import requests
import time

app = create_app()

def start_polling():
    offset = 0
    print("🤖 Bot is now polling for messages...")
    while True:
        try:
            # طلب الرسائل الجديدة من تلجرام
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url).json()

            if "result" in response:
                for update in response["result"]:
                    # إرسال البيانات لدالة المعالجة التي كتبناها في telegram_bot.py
                    from app.telegram_bot import handle_telegram_webhook
                    with app.app_context():
                        handle_telegram_webhook(update)
                    
                    # تحديث الـ offset لعدم تكرار الرسالة
                    offset = update["update_id"] + 1
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5) # الانتظار قبل المحاولة مرة أخرى

if __name__ == "__main__":
    start_polling()
