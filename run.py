# ~/jobeni-sD/run.py
import os, sys, threading, time, requests
from sqlalchemy import text
from dotenv import load_dotenv
from app import create_app, db

# تحميل المتغيرات البيئية
load_dotenv()

# إعداد المسارات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# تحديد البيئة (فرسيل أو محلي)
env = 'production' if os.environ.get('VERCEL') else 'development'
app = create_app(env)

def telegram_worker(flask_app):
    """وظيفة لتشغيل بوت التليجرام في خلفية التطبيق (للمحلي فقط)"""
    with flask_app.app_context():
        # تأخير بسيط لضمان استقرار السيرفر
        time.sleep(5)
        try:
            from app.telegram_bot import bot
            print("🚀 [Telegram Bot] Starting polling...")
            bot.remove_webhook()
            bot.infinity_polling()
        except Exception as e:
            print(f"❌ [Telegram Bot Error]: {e}")

# --- منطق التشغيل الرئيسي ---

with app.app_context():
    # إنشاء الجداول الأساسية (بما فيها الكومينتي والمقابلات)
    try:
        db.create_all()
        # فك القيود يدوياً للسماح بالمرسل رقم 0 (نظام الرسائل)
        db.session.execute(text('ALTER TABLE message DROP CONSTRAINT IF EXISTS message_sender_id_fkey'))
        db.session.execute(text('ALTER TABLE message DROP CONSTRAINT IF EXISTS message_recipient_id_fkey'))
        db.session.commit()
    except Exception as e:
        print(f"⚠️ [DB Warning]: {e}")
    
    # إنشاء مجلدات الرفع إذا لم تكن موجودة
    os.makedirs(os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'cvs'), exist_ok=True)

if __name__ == '__main__':
    # تشغيل البوت في خيط منفصل (فقط إذا لم نكن على فرسيل)
    if os.environ.get('TELEGRAM_BOT_TOKEN') and not os.environ.get('VERCEL'):
        worker_thread = threading.Thread(target=telegram_worker, args=(app,), daemon=True)
        worker_thread.start()
    
    # تشغيل تطبيق Flask محلياً
    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    # هذا الجزء مخصص لـ Vercel (WSGI)
    # لا نقوم بتشغيل Thread هنا لتفادي تعليق السيرفر
    application = app
