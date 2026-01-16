# ~/jobeni-sD/setup_webhook.py
import requests
import json

# التوكين الرسمي الجديد (تم التحديث)
TOKEN = "8428928079:AAE9adzjOfMPj3k-WHuzmZc3uDM7KyBw8zA"
# رابط الـ Webhook الخاص بمشروعك على Vercel
WEBHOOK_URL = "https://jobeni-sd.vercel.app/telegram/webhook"

def set_webhook():
    print(f"🚀 البدء في تنشيط البوت الذكي جوبيني (JOBENISDbot)... ")
    print(f"📡 الرابط المستهدف: {WEBHOOK_URL}")
    print(f"🔑 التوكين المستخدم يبدأ بـ: {TOKEN[:10]}...")

    # 1. تنظيف أي جلسات معلقة قديمة
    print("🧹 جاري تنظيف الجلسات السابقة...")
    del_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    requests.post(del_url, json={"drop_pending_updates": True})

    # 2. إعداد الـ Webhook الجديد بمواصفات كاملة
    set_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    payload = {
        "url": WEBHOOK_URL,
        "allowed_updates": ["message", "callback_query", "chat_member"],
        "drop_pending_updates": True
    }

    try:
        response = requests.post(set_url, json=payload, timeout=15)
        result = response.json()

        if result.get("ok"):
            print(f"✅ نجاح باهر! تم ربط البوت الجديد بنجاح.")
            print(f"📝 رسالة تليجرام: {result.get('description')}")
        else:
            print(f"❌ فشل الربط!")
            print(f"⚠️ السبب: {result.get('description')}")

        # 3. فحص الحالة النهائية للتأكد من الاتصال
        print("\n📊 فحص حالة الاتصال:")
        status_url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
        status_res = requests.get(status_url).json()
        if status_res.get("ok"):
            info = status_res.get("result")
            print(f"🌐 الرابط المسجل: {info.get('url')}")
            print(f"⏳ الرسائل المنتظرة: {info.get('pending_update_count')}")
            if info.get('last_error_message'):
                print(f"❗ آخر خطأ مسجل: {info.get('last_error_message')}")
        
    except Exception as e:
        print(f"💥 حدث خطأ غير متوقع: {e}")

if __name__ == "__main__":
    set_webhook()
