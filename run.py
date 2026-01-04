# ~/jobeni-sD/run.py
import os, sys, threading, time, requests
from dotenv import load_dotenv
from app import create_app, db

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# تحديد الإعدادات بناءً على البيئة (Vercel يستخدم الإنتاج أوتوماتيكياً)
env = 'production' if os.environ.get('VERCEL') else 'development'
app = create_app(env)

def telegram_worker(flask_app):
    """هذا الخيط سيعمل فقط في البيئة المحلية ولا يعمل في Vercel"""
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
                    from app.telegram_bot import handle_telegram_webhook
                    with flask_app.app_context():
                        handle_telegram_webhook(up)
        except Exception as e:
            print(f"Telegram Thread Error: {e}")
        time.sleep(3)

# الجزء القادم هو الأهم لضمان عمل الروابط في Vercel
if __name__ == '__main__':
    with app.app_context():
        # التأكد من إنشاء الجداول في PostgreSQL عند التشغيل
        db.create_all()
        # إنشاء مجلدات الرفع إذا لم تكن موجودة
        os.makedirs(os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'cvs'), exist_ok=True)

    # تشغيل خيط البوت فقط إذا كنا لسنا في Vercel (للمحلي فقط)
    if os.environ.get('TELEGRAM_BOT_TOKEN') and not os.environ.get('VERCEL'):
        threading.Thread(target=telegram_worker, args=(app,), daemon=True).start()
        print("🤖 Telegram Bot: RUNNING (Long Polling Mode - Local)")

    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    # هذا الجزء يضمن لـ Vercel أن الجداول موجودة عند بدء التشغيل السحابي
    with app.app_context():
        db.create_all()
