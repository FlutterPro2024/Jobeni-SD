# ~/jobeni-sD/run.py
import os, sys, threading, time, requests
from sqlalchemy import text # أضفنا هذا السطر
from dotenv import load_dotenv
from app import create_app, db

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

env = 'production' if os.environ.get('VERCEL') else 'development'
app = create_app(env)

# ... (نفس دالة telegram_worker بدون تغيير) ...

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # محاولة فك القيد يدوياً للسماح بالمرسل رقم 0
        try:
            db.session.execute(text('ALTER TABLE message DROP CONSTRAINT IF EXISTS message_sender_id_fkey'))
            db.session.execute(text('ALTER TABLE message DROP CONSTRAINT IF EXISTS message_recipient_id_fkey'))
            db.session.commit()
        except: pass
        os.makedirs(os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'cvs'), exist_ok=True)

    if os.environ.get('TELEGRAM_BOT_TOKEN') and not os.environ.get('VERCEL'):
        threading.Thread(target=telegram_worker, args=(app,), daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    with app.app_context():
        db.create_all()
        # فك القيود في بيئة Vercel السحابية
        try:
            db.session.execute(text('ALTER TABLE message DROP CONSTRAINT IF EXISTS message_sender_id_fkey'))
            db.session.execute(text('ALTER TABLE message DROP CONSTRAINT IF EXISTS message_recipient_id_fkey'))
            db.session.commit()
        except: pass
