# ~/jobeni-sD/config.py
import os

class Config:
    # مفتاح الأمان للتشفير والجلسات
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'jobeni-sd-secret-key-2026-v3'

    # --- إعدادات قاعدة البيانات ---
    # يدعم Postgres (Vercel/Neon) و Postgres المحلي (Termux)
    DATABASE_URL = os.environ.get('DATABASE_URL')

    if DATABASE_URL:
        # تصحيح بروتوكول postgres القديم ليتوافق مع SQLAlchemy الحديثة
        if DATABASE_URL.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        else:
            SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # الإعداد الافتراضي لـ Termux (تأكد من إنشاء قاعدة البيانات محلياً باسم jobeni_db)
        SQLALCHEMY_DATABASE_URI = 'postgresql://localhost:5432/jobeni_db'

    # تحسينات الاتصال بالقاعدة لمنع انقطاع الجلسات (مهم جداً لـ Vercel)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 15} if "postgresql" in SQLALCHEMY_DATABASE_URI else {}
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- إعدادات البريد الإلكتروني ---
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')

    # --- إدارة الملفات والمجلدات ---
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # تحديد مسار الرفع (Uploads)
    # ملاحظة: Vercel لديه نظام ملفات للقراءة فقط، يفضل استخدام S3 لاحقاً للإنتاج
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # الحد الأقصى للملفات: 16 ميجابايت

    # إنشاء مجلد الرفع تلقائياً إذا لم يكن موجوداً (لبيئة Termux)
    @staticmethod
    def init_app(app):
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# قاموس التكوينات للتبديل بين البيئات
config = {
    'development': Config,
    'production': Config,
    'default': Config
}
