# ~/jobeni-sD/run_bot.py
from app import create_app, db
from app.telegram_bot import BOT_TOKEN, handle_telegram_webhook
from app.agent_worker import run_agent # استيراد مشغل الرادار
import requests
import time

# إنشاء التطبيق مع سياق Flask
app = create_app()

def start_polling():
    offset = 0
    print("🤖 Jobeni Smart Radar is now Polling (Local Termux Mode)...")
    print("📡 البوت شغال حالياً وبراقب في الرسائل والرادار...")

    while True:
        try:
            # طلب التحديثات من تليجرام باستخدام Long Polling
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35).json()

            if "result" in response:
                for update in response["result"]:
                    with app.app_context():
                        # 1. معالجة الرسالة في نظام الرد الآلي والذكاء الاصطناعي
                        handle_telegram_webhook(update)

                        # 2. إذا كانت هناك رسالة جديدة، نقوم بتشغيل الرادار لتحديث الـ Dashboard
                        # هذا يضمن أن المستخدم بمجرد ما يتفاعل مع البوت، الرادار بيبحث ليه عن وظائف فوراً
                        if "message" in update and "text" in update["message"]:
                            print(f"📡 اكتشاف نشاط من {update['message']['from'].get('username')}: جاري تشغيل الرادار...")
                            try:
                                # تشغيل الوكيل للبحث والمطابقة وحفظها في قاعدة البيانات
                                with app.test_request_context(): # لضمان عمل الـ url_for داخل الرادار
                                    run_agent()
                                print("✅ تم مزامنة الوظائف الجديدة مع الداتابيز وإرسال التنبيهات.")
                            except Exception as agent_err:
                                print(f"⚠️ خطأ في تشغيل الوكيل الآلي: {agent_err}")

                        # تحديث الـ offset لعدم تكرار معالجة نفس الرسالة
                        offset = update["update_id"] + 1
            
        except Exception as e:
            print(f"📡 Waiting for connection or error occurred... {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_polling()
