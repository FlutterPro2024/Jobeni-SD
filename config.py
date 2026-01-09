# ~/jobeni-sD/config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'jobeni-sd-secret-key-2026'

    # منطق قاعدة البيانات المزدوج
    DATABASE_URL = os.environ.get('DATABASE_URL')

    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        else:
            SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Postgres المحلي في Termux
        SQLALCHEMY_DATABASE_URI = 'postgresql://localhost:5432/jobeni_db'

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 10} if "postgresql" in SQLALCHEMY_DATABASE_URI else {}
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # إعدادات البريد
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')

    # المجلدات والملفات (تم تصحيح المسار ليعمل في Vercel وتيرمكس)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

config = {
    'development': Config,
    'production': Config,
    'default': Config
}
