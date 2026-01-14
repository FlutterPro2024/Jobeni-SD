# ~/jobeni-sD/app/__init__.py
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail

# إضافة المسار الرئيسي للمشروع لضمان استيراد config بشكل صحيح
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config

# تعريف الأدوات (Extensions) ككائنات عالمية
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()

def create_app(config_name='default'):
    app = Flask(__name__)

    # اختيار الإعدادات المناسبة (الإنتاج إذا كان على Vercel أو المحلي)
    env_config = 'production' if os.environ.get('VERCEL') else config_name
    app.config.from_object(config[env_config])

    # تهيئة الأدوات مع تطبيق Flask
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # إعدادات نظام تسجيل الدخول
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "يرجى تسجيل الدخول للوصول إلى هذه الصفحة."
    login_manager.login_message_category = "info"

    with app.app_context():
        # 1. استيراد النماذج لضمان تسجيلها في قاعدة البيانات
        from app.models import User, Notification, Job, CV, Message, Post

        # 2. استيراد وتسجيل الـ Blueprints (الموديولات)
        # تم ترتيبها لضمان عدم التضارب في الروابط
        
        from app.auth import auth_bp
        from app.jobs import jobs_bp
        from app.chat import chat_bp
        from app.community import community_bp  # الموديول المنفصل للمجتمع
        from app.telegram_bot import telegram_bp
        from app.notifications import notifications_bp
        from app.agent_worker import agent_bp
        
        # تسجيل المسارات الأساسية
        app.register_blueprint(auth_bp)
        app.register_blueprint(jobs_bp, url_prefix='/jobs')
        app.register_blueprint(chat_bp, url_prefix='/chat')
        app.register_blueprint(community_bp, url_prefix='/community')
        app.register_blueprint(telegram_bp, url_prefix='/telegram')
        app.register_blueprint(notifications_bp, url_prefix='/notifications')
        app.register_blueprint(agent_bp, url_prefix='/agent')

        # 3. تسجيل الموديولات الإضافية مع معالجة الأخطاء (لضمان استمرار التطبيق)
        try:
            from app.cv import cv_bp
            app.register_blueprint(cv_bp, url_prefix='/cv')

            from app.search import search_bp
            app.register_blueprint(search_bp, url_prefix='/search')

            from app.admin import admin_bp
            app.register_blueprint(admin_bp, url_prefix='/admin')

            from app.applications import apps_bp
            app.register_blueprint(apps_bp, url_prefix='/apps')

            from app.interview import interview_bp
            app.register_blueprint(interview_bp, url_prefix='/interview')

        except Exception as e:
            app.logger.error(f"⚠️ فشل في تسجيل بعض الأجزاء غير الأساسية: {e}")

    # محمل المستخدم لنظام Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        # استخدام session.get بدلاً من Query.get للنسخ الحديثة من SQLAlchemy
        return db.session.get(User, int(user_id))

    # حقن متغيرات عامة في جميع قوالب HTML (Context Processor)
    @app.context_processor
    def inject_vars():
        from app.models import Notification
        from datetime import datetime, timedelta
        return dict(
            Notification=Notification,
            utcnow=datetime.utcnow(),
            timedelta=timedelta
        )

    return app
