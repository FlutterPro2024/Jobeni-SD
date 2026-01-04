# ~/jobeni-sD/run.py
import os, sys, threading, time, requests
from dotenv import load_dotenv
from app import create_app, db

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
app = create_app('development')

def telegram_worker(flask_app):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token: return
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_id+1}&timeout=20"
            res = requests.get(url).json()
            if res.get("ok"):
                for up in res.get("result", []):
                    last_id = up["update_id"]
                    # معالجة الرسائل تتم الآن عبر الـ Webhook أو هذا الخيط
                    # استدعاء الدالة من telegram_bot لتوحيد المعالجة
                    from app.telegram_bot import handle_telegram_webhook
                    with flask_app.app_context():
                        handle_telegram_webhook(up)
        except Exception as e:
            print(f"Telegram Thread Error: {e}")
        time.sleep(3)

if __name__ == '__main__':
    with app.app_context():
        # التأكد من إنشاء الجداول في PostgreSQL عند التشغيل
        db.create_all()
        # إنشاء مجلدات الرفع إذا لم تكن موجودة
        os.makedirs(os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'cvs'), exist_ok=True)

    # تشغيل خيط البوت إذا وجد التوكن
    if os.environ.get('TELEGRAM_BOT_TOKEN'):
        threading.Thread(target=telegram_worker, args=(app,), daemon=True).start()
        print("🤖 Telegram Bot: RUNNING (Long Polling Mode)")

    app.run(host='0.0.0.0', port=5000, debug=False)
