# ~/jobeni-sD/run.py
import os, sys, threading, time
from sqlalchemy import text
from dotenv import load_dotenv
from app import create_app, db

# تحميل المتغيرات البيئية
load_dotenv()

# إعداد المسارات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# تحديد البيئة
env = 'production' if os.environ.get('VERCEL') else 'development'
app = create_app(env)

def telegram_worker(flask_app):
    """وظيفة لتشغيل بوت التليجرام (للمحلي فقط)"""
    with flask_app.app_context():
        time.sleep(5)
        try:
            from app.telegram_bot import bot
            bot.remove_webhook()
            bot.infinity_polling()
        except Exception as e:
            print(f"❌ [Telegram Bot Error]: {e}")

# --- منطق تهيئة قاعدة البيانات والمجلدات ---
with app.app_context():
    try:
        db.create_all()
        # محاولة معالجة القيود للمسائل المتعلقة بقاعدة البيانات
        try:
            db.session.execute(text('ALTER TABLE message DROP CONSTRAINT IF EXISTS message_sender_id_fkey'))
            db.session.execute(text('ALTER TABLE message DROP CONSTRAINT IF EXISTS message_recipient_id_fkey'))
            db.session.commit()
        except Exception:
            db.session.rollback()
    except Exception as e:
        print(f"⚠️ [DB Warning]: {e}")

    try:
        os.makedirs(os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'cvs'), exist_ok=True)
    except Exception:
        pass

# التصدير لـ Vercel
app = app

if __name__ == '__main__':
    if os.environ.get('TELEGRAM_BOT_TOKEN') and not os.environ.get('VERCEL'):
        worker_thread = threading.Thread(target=telegram_worker, args=(app,), daemon=True)
        worker_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=False)
