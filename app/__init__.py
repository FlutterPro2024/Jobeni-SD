# ~/jobeni-sD/app/__init__.py
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_apscheduler import APScheduler

# إضافة المسار الأساسي لضمان استيراد الإعدادات بشكل صحيح من خارج المجلد
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config

# تعريف الإضافات عالمياً
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
scheduler = APScheduler()

def create_app(config_name='default'):
    app = Flask(__name__)

    # تحديد بيئة التشغيل (Vercel أو محلي أو إنتاج)
    env_config = 'production' if os.environ.get('VERCEL') else config_name
    app.config.from_object(config[env_config])

    # تهيئة الإضافات (Extensions)
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    
    # تهيئة وتشغيل المجدول (Scheduler) لإدارة مهام الأيجنت الذكي
    if not scheduler.running:
        scheduler.init_app(app)
        scheduler.start()

    # إعدادات الحماية والوصول للـ Login Manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "يرجى تسجيل الدخول للوصول إلى هذه الصفحة."
    login_manager.login_message_category = "info"

    with app.app_context():
        # 1. استيراد النماذج لضمان تسجيلها في SQLAlchemy
        from app.models import User, Notification, Job, CV, Message, Post

        # 2. تسجيل Blueprints الأساسية
        from app.auth import auth_bp
        from app.jobs import jobs_bp
        from app.chat import chat_bp
        from app.community import community_bp
        from app.telegram_bot import telegram_bp
        from app.notifications import notifications_bp
        from app.agent_worker import agent_bp

        # تسجيل الـ Blueprints في التطبيق
        app.register_blueprint(auth_bp) # المسارات الجذرية /
        app.register_blueprint(agent_bp, url_prefix='/agent')
        app.register_blueprint(jobs_bp, url_prefix='/jobs')
        app.register_blueprint(chat_bp, url_prefix='/chat')
        app.register_blueprint(community_bp, url_prefix='/community')
        app.register_blueprint(telegram_bp, url_prefix='/telegram')
        app.register_blueprint(notifications_bp, url_prefix='/notifications')

        # 3. تسجيل الإضافات المتقدمة (الـ AI والبحث والإدارة) مع معالجة الأخطاء
        try:
            from app.api import api_bp
            app.register_blueprint(api_bp)
        except ImportError:
            app.logger.error("⚠️ ملف api.py غير موجود")

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
            app.logger.error(f"⚠️ فشل في تحميل بعض الوحدات المتقدمة: {e}")

        # 4. إعداد مهام الأيجنت الدورية (الرادار الذكي)
        try:
            from app.tasks import run_ai_agent_discovery, send_weekly_agent_summary
            
            # مهمة الرادار اليومي (كل 24 ساعة)
            if not scheduler.get_job('ai_agent_job'):
                scheduler.add_job(id='ai_agent_job', func=run_ai_agent_discovery, trigger='interval', hours=24)
                app.logger.info("✅ رادار الأيجنت اليومي نشط")

            # مهمة التقرير الأسبوعي
            if not scheduler.get_job('weekly_summary_job'):
                scheduler.add_job(id='weekly_summary_job', func=send_weekly_agent_summary, trigger='interval', weeks=1)
                app.logger.info("✅ التقرير الأسبوعي مبرمج بنجاح")
        except ImportError:
            app.logger.warning("⚠️ لم يتم تفعيل المهام الدورية (tasks.py غير موجود)")

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_vars():
        """حقن متغيرات عالمية (التعميم السيادي، نظام الإشعارات، الوقت)"""
        from app.models import Notification
        from datetime import datetime, timedelta

        # منطق التعميم السيادي (قراءة من announcement.txt)
        announcement_path = os.path.join(app.root_path, '..', 'announcement.txt')
        announcement = None
        announcement_color = 'danger' # القيمة الافتراضية للتحذيرات

        if os.path.exists(announcement_path):
            try:
                with open(announcement_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if "|" in content:
                        # تنسيق: color|message (مثال: success|مرحباً بكم)
                        announcement_color, announcement = content.split("|", 1)
                    else:
                        announcement = content
            except Exception:
                announcement = None

        return dict(
            Notification=Notification,
            utcnow=datetime.utcnow(),
            timedelta=timedelta,
            global_announcement=announcement,
            announcement_color=announcement_color
        )

    return app
