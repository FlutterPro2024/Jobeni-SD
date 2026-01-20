# ~/jobeni-sD/run_bot.py
from app import create_app, db
from app.telegram_bot import BOT_TOKEN, handle_telegram_webhook
from app.agent_worker import run_agent  # استيراد مشغل الرادار
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
            # تم تعطيل verify=False لضمان العمل في بيئات الشبكة المتقلبة
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35, verify=False).json()

            if "result" in response:
                for update in response["result"]:
                    # استخدام سياق التطبيق لضمان الوصول لقاعدة البيانات والـ Models
                    with app.app_context():
                        try:
                            # 1. معالجة الرسالة (الذكاء الاصطناعي، المقابلات، الصوت)
                            handle_telegram_webhook(update)

                            # 2. تشغيل الرادار عند وجود نص جديد
                            if "message" in update and "text" in update["message"]:
                                user_info = update['message']['from'].get('username') or update['message']['from'].get('first_name')
                                print(f"📡 نشاط من {user_info}: جاري تشغيل الرادار العالمي...")
                                
                                try:
                                    # تشغيل الوكيل للبحث عن وظائف وإرسال التنبيهات
                                    run_agent()
                                    print(f"✅ تم تحديث وظائف {user_info} وإرسال إشعارات المطابقة.")
                                except Exception as agent_err:
                                    print(f"⚠️ خطأ في تشغيل الرادار: {agent_err}")

                        except Exception as inner_e:
                            print(f"⚠️ خطأ في معالجة التحديث: {inner_e}")

                    # تحديث الـ offset لعدم تكرار الرسالة
                    offset = update["update_id"] + 1

        except Exception as e:
            # في حالة انقطاع الإنترنت أو خطأ في الاتصال
            print(f"📡 جاري محاولة الاتصال بخوادم تليجرام... {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_polling()
