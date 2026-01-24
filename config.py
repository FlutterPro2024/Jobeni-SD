# ~/jobeni-sD/config.py
import os

class Config:
    # المفتاح السري لتأمين الجلسات (Sessions)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'jobeni-sd-secret-key-2026-v3'

    # --- إضافة مفتاح الأمان السري للـ API ---
    # هذا المفتاح هو "كلمة السر" التي يجب إرسالها في الهيدر للوصول لبيانات الـ API
    API_KEY = os.environ.get('JOBENI_API_KEY') or 'jobeni_secret_key_2026_sd'

    # جلب رابط قاعدة البيانات من Vercel أو Neon أو متغيرات البيئة
    DATABASE_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')

    if DATABASE_URL:
        # تصحيح البروتوكول ليتناسب مع SQLAlchemy (تحويل postgres إلى postgresql)
        if DATABASE_URL.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        else:
            SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # المسار المحلي للـ Termux أو بيئة التطوير المحلية
        # تأكد من تشغيل PostgreSQL محلياً أو تغيير هذا المسار لـ sqlite:///app.db للتجارب السريعة
        SQLALCHEMY_DATABASE_URI = 'postgresql://localhost:5432/jobeni_db'

    # خيارات محرك SQLAlchemy لضمان استقرار الاتصال (خصوصاً مع Neon و Vercel)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # إعدادات المجلدات - استخدام مسارات مؤقتة لـ Vercel (لأن نظام الملفات هناك للقراءة فقط)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    if os.environ.get('VERCEL'):
        # Vercel لا يسمح بالكتابة إلا في مجلد /tmp
        UPLOAD_FOLDER = '/tmp'
    else:
        # في البيئة المحلية نستخدم المجلد التقليدي
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')

    @staticmethod
    def init_app(app):
        """تهيئة التطبيق والتأكد من وجود مجلدات الرفع في البيئات المسموح بها"""
        if not os.environ.get('VERCEL'):
            if not os.path.exists(Config.UPLOAD_FOLDER):
                try:
                    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                except Exception as e:
                    print(f"⚠️ Warning: Could not create upload folder: {e}")
                    pass

# تعريف القواميس لاختيار البيئة المناسبة
config = {
    'development': Config,
    'production': Config,
    'default': Config
}
