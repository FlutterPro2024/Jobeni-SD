# ~/jobeni-sD/config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'jobeni-sd-secret-key-2026'

    # منطق قاعدة البيانات المزدوج (تم تحديثه ليدعم Postgres المحلي في Termux)
    DATABASE_URL = os.environ.get('DATABASE_URL')

    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        else:
            SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # إذا لم يوجد متغير بيئة، سنحاول الاتصال بـ Postgres المحلي أولاً، وإلا SQLite
        # تعديل السطر التالي ليشير لـ Postgres المحلي بدلاً من SQLite مباشرة
        SQLALCHEMY_DATABASE_URI = 'postgresql://localhost:5432/jobeni_db'

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 7} if "postgresql" in SQLALCHEMY_DATABASE_URI else {}
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # إعدادات البريد الإلكتروني - تم الضبط لضمان قبول Gmail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # Force Sender: إجبار النظام على استخدام نفس إيميل اليوزرنيم لتفادي خطأ 530
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')

    # المجلدات والملفات
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16777216))

config = {
    'development': Config,
    'production': Config,
    'default': Config
}
