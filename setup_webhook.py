# ~/jobeni-sD/setup_webhook.py
import requests

# توكين البوت الخاص بك
TOKEN = "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
# الرابط الحقيقي للموقع على Vercel مع المسار الصحيح للـ Webhook
# تأكد دائماً أن المسار ينتهي بـ /telegram/webhook كما هو معرف في Blueprint
WEBHOOK_URL = "https://jobeni-sd.vercel.app/telegram/webhook"

def set_webhook():
    print(f"🔄 البدء في تهيئة Webhook للبوت...")

    # 1. حذف الـ Webhook القديم أولاً لتنظيف أي إعدادات سابقة
    delete_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    requests.post(delete_url)
    print("🧹 تم حذف الإعدادات القديمة.")

    # 2. ضبط الـ Webhook الجديد
    set_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    payload = {
        "url": WEBHOOK_URL,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True  # تجاهل أي رسائل قديمة كانت معلقة
    }
    
    response = requests.post(set_url, json=payload)
    result = response.json()

    if result.get("ok"):
        print(f"✅ نجاح! تم ربط البوت بالرابط: {WEBHOOK_URL}")
    else:
        print(f"❌ فشل الربط: {result.get('description')}")

    # 3. التحقق النهائي من الحالة
    info_url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
    info_res = requests.get(info_url).json()
    print(f"📊 معلومات الاتصال الحالية: {info_res.get('result')}")

if __name__ == "__main__":
    set_webhook()
