# ~/jobeni-sD/setup_webhook.py
import requests

TOKEN = "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
# استبدل هذا الرابط برابط سيرفرك الحقيقي (يجب أن يكون HTTPS)
WEBHOOK_URL = "https://YOUR_DOMAIN.com/telegram-webhook"

def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    response = requests.post(url, json={"url": WEBHOOK_URL})
    print(f"Status: {response.json()}")

if __name__ == "__main__":
    set_webhook()
