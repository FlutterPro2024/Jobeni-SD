# ~/jobeni-sD/config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'jobeni-sd-secret-key-2026-v3'

    # جلب رابط قاعدة البيانات من Vercel أو Neon
    DATABASE_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')

    if DATABASE_URL:
        # تصحيح البروتوكول ليتناسب مع SQLAlchemy
        if DATABASE_URL.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        else:
            SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # المسار المحلي للـ Termux أو التطوير
        SQLALCHEMY_DATABASE_URI = 'postgresql://localhost:5432/jobeni_db'

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # إعدادات المجلدات - استخدام مسارات مؤقتة لـ Vercel
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    # في Vercel نستخدم /tmp للتخزين المؤقت إذا لزم الأمر
    if os.environ.get('VERCEL'):
        UPLOAD_FOLDER = '/tmp'
    else:
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')

    @staticmethod
    def init_app(app):
        # منع محاولة إنشاء مجلدات في بيئة Vercel للقراءة فقط
        if not os.environ.get('VERCEL'):
            if not os.path.exists(Config.UPLOAD_FOLDER):
                try:
                    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                except:
                    pass

config = {
    'development': Config,
    'production': Config,
    'default': Config
}
