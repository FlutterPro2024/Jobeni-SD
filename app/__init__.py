# ~/jobeni-sD/app/__init__.py
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_apscheduler import APScheduler  # إضافة المجدول

# إضافة المسار الأساسي لضمان استيراد الإعدادات بشكل صحيح
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
scheduler = APScheduler() # تعريف المجدول

def create_app(config_name='default'):
    app = Flask(__name__)

    # تحديد بيئة التشغيل (Vercel أو محلي)
    env_config = 'production' if os.environ.get('VERCEL') else config_name
    app.config.from_object(config[env_config])

    # تهيئة الإضافات (Extensions)
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # تهيئة وتشغيل المجدول (Scheduler) لمهام الأيجنت
    if not scheduler.running:
        scheduler.init_app(app)
        scheduler.start()

    # إعدادات الحماية والوصول
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "يرجى تسجيل الدخول للوصول إلى هذه الصفحة."
    login_manager.login_message_category = "info"

    with app.app_context():
        # استيراد النماذج الأساسية
        from app.models import User, Notification, Job, CV, Message, Post

        # --- أولاً: استيراد Blueprints الأساسية ---
        from app.auth import auth_bp
        from app.jobs import jobs_bp
        from app.chat import chat_bp
        from app.community import community_bp
        from app.telegram_bot import telegram_bp
        from app.notifications import notifications_bp
        from app.agent_worker import agent_bp

        # --- ثانياً: تسجيل Blueprints بترتيب يمنع تضارب الروابط ---
        app.register_blueprint(auth_bp) # المسارات الجذرية /
        app.register_blueprint(agent_bp, url_prefix='/agent')
        app.register_blueprint(jobs_bp, url_prefix='/jobs')
        app.register_blueprint(chat_bp, url_prefix='/chat')
        app.register_blueprint(community_bp, url_prefix='/community')
        app.register_blueprint(telegram_bp, url_prefix='/telegram')
        app.register_blueprint(notifications_bp, url_prefix='/notifications')

        # --- ثالثاً: تسجيل الإضافات المتقدمة (الـ AI والبحث والإدارة) ---
        try:
            from app.api import api_bp
            app.register_blueprint(api_bp)
        except ImportError:
            app.logger.error("⚠️ لم يتم العثور على ملف api.py")

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
            app.logger.error(f"⚠️ فشل في تسجيل بعض الأجزاء المتقدمة: {e}")

        # --- رابعاً: إعداد مهام الأيجنت الدورية ---
        from app.tasks import run_ai_agent_discovery, send_weekly_agent_summary

        # 1. إضافة مهمة الرادار اليومي (كل 24 ساعة)
        if not scheduler.get_job('ai_agent_job'):
            scheduler.add_job(id='ai_agent_job', func=run_ai_agent_discovery, trigger='interval', hours=24)
            app.logger.info("✅ تم تفعيل مهمة الرادار الذكي اليومي")

        # 2. إضافة مهمة التقرير الأسبوعي (كل أسبوع)
        if not scheduler.get_job('weekly_summary_job'):
            scheduler.add_job(id='weekly_summary_job', func=send_weekly_agent_summary, trigger='interval', weeks=1)
            app.logger.info("✅ تم تفعيل مهمة التقرير الأسبوعي الشامل")

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_vars():
        """حقن متغيرات عالمية في قوالب الـ HTML لسهولة الوصول"""
        from app.models import Notification
        from datetime import datetime, timedelta
        return dict(
            Notification=Notification,
            utcnow=datetime.utcnow(),
            timedelta=timedelta
        )

    return app
