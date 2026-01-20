# ~/jobeni-sD/run_bot.py
from app import create_app, db
from app.telegram_bot import BOT_TOKEN, handle_telegram_webhook
from app.agent_worker import run_agent  # استيراد مشغل الرادار
import requests
import time

# إنشاء التطبيق مع سياق Flask
app = create_app()

def start_polling():
    # تعديل الـ offset ليكون -1 في البداية لتجاوز الرسائل القديمة المعلقة
    offset = -1
    print("🤖 Jobeni Smart Radar is now Polling (Local Termux Mode)...")
    print(f"📡 البوت شغال حالياً وبراقب في الرسائل والرادار... (Token: {BOT_TOKEN[:10]}...)")

    while True:
        try:
            # طلب التحديثات من تليجرام باستخدام Long Polling
            # تم تعطيل verify=False لضمان العمل في بيئات الشبكة المتقلبة
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35, verify=False).json()

            if "result" in response and len(response["result"]) > 0:
                for update in response["result"]:
                    # تحديث الـ offset فوراً لضمان عدم تكرار الرسالة حتى لو حدث خطأ لاحق
                    offset = update["update_id"] + 1
                    
                    # استخدام سياق التطبيق لضمان الوصول لقاعدة البيانات والـ Models
                    with app.app_context():
                        try:
                            # طباعة للتأكد من وصول الرسالة فعلياً للكود
                            if "message" in update:
                                user_info = update['message']['from'].get('username') or update['message']['from'].get('first_name')
                                msg_text = update['message'].get('text', '[Voice/Other]')
                                print(f"✅ استلام رسالة من {user_info}: {msg_text}")

                                # 1. معالجة الرسالة (الذكاء الاصطناعي، المقابلات، الصوت)
                                handle_telegram_webhook(update)

                                # 2. تشغيل الرادار عند وجود نص جديد (استبعاد الأوامر من تشغيل الرادار لتوفير الموارد)
                                if "text" in update["message"] and not msg_text.startswith('/'):
                                    print(f"📡 جاري تشغيل الرادار العالمي لـ {user_info}...")
                                    try:
                                        # تشغيل الوكيل للبحث عن وظائف وإرسال التنبيهات
                                        run_agent()
                                        print(f"✅ تم تحديث وظائف {user_info} وإرسال إشعارات المطابقة.")
                                    except Exception as agent_err:
                                        print(f"⚠️ خطأ في تشغيل الرادار: {agent_err}")

                        except Exception as inner_e:
                            print(f"⚠️ خطأ في معالجة التحديث داخلياً: {inner_e}")

            elif response.get("error_code") == 409:
                print("❌ Conflict Error: في نسخة تانية من البوت شغالة! قفلها وشغل دي بس.")
                time.sleep(5)

        except Exception as e:
            # في حالة انقطاع الإنترنت أو خطأ في الاتصال
            print(f"📡 جاري محاولة الاتصال بخوادم تليجرام... {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_polling()
