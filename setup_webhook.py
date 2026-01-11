# ~/jobeni-sD/setup_webhook.py
import requests

TOKEN = "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
# الرابط الحقيقي للموقع على Vercel مع المسار الصحيح للـ Webhook
WEBHOOK_URL = "https://jobeni-sd.vercel.app/telegram/webhook"

def set_webhook():
    # حذف الـ Webhook القديم أولاً لتنظيف الاتصال
    delete_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    requests.post(delete_url)
    
    # ضبط الـ Webhook الجديد
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    response = requests.post(url, json={
        "url": WEBHOOK_URL,
        "allowed_updates": ["message", "callback_query"]
    })
    
    print(f"Set Webhook Status: {response.json()}")

if __name__ == "__main__":
    set_webhook()
