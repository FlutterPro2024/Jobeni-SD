# ~/jobeni-sD/run_bot.py
from app import create_app, db
from app.telegram_bot import BOT_TOKEN, handle_telegram_webhook
from app.agent_worker import run_agent # استيراد مشغل الرادار
import requests
import time

app = create_app()

def start_polling():
    offset = 0
    print("🤖 Jobeni Smart Radar is now Polling (Local Termux Mode)...")
    
    while True:
        try:
            # طلب التحديثات من تليجرام
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35).json()

            if "result" in response:
                for update in response["result"]:
                    with app.app_context():
                        # 1. معالجة الرسالة في نظام الرد الآلي
                        handle_telegram_webhook(update)
                        
                        # 2. إذا كانت هناك رسالة جديدة، نقوم بتشغيل الرادار لتحديث الـ Dashboard
                        if "message" in update and "text" in update["message"]:
                            print(f"📡 اكتشاف نشاط: جاري تشغيل الرادار لتحديث المقترحات...")
                            try:
                                # تشغيل الوكيل للبحث والمطابقة وحفظها في قاعدة البيانات
                                run_agent()
                                print("✅ تم مزامنة الوظائف الجديدة مع الداتابيز.")
                            except Exception as agent_err:
                                print(f"⚠️ خطأ في تشغيل الوكيل الآلي: {agent_err}")

                        offset = update["update_id"] + 1
        except Exception as e:
            print(f"📡 Waiting for connection... {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_polling()
