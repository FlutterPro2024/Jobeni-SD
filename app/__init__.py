# ~/jobeni-sD/app/__init__.py
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail

# تأمين مسارات النظام للوصول إلى config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config

# تعريف الإضافات
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()

def create_app(config_name='default'):
    app = Flask(__name__)

    # اختيار الإعدادات
    env_config = 'production' if os.environ.get('VERCEL') else config_name
    app.config.from_object(config[env_config])
    config[env_config].init_app(app)

    # تهيئة الإضافات
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = "يرجى تسجيل الدخول للوصول إلى هذه الصفحة"

    with app.app_context():
        # استيراد الموديلات
        from app.models import User, Notification, Job
        
        # --- [بداية كود الإصلاح التلقائي للأعمدة] ---
        from sqlalchemy import text
        try:
            # محاولة تغيير اسم العمود المتعطل فوراً
            db.session.execute(text('ALTER TABLE job RENAME COLUMN employer_id TO user_id;'))
            db.session.commit()
            print("✅ Auto-Fix: employer_id renamed to user_id")
        except Exception:
            db.session.rollback() # العمود مصلح بالفعل أو غير موجود

        try:
            # إضافة أعمدة الوكيل الذكي إذا لم تكن موجودة
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE;'))
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_query VARCHAR(255);'))
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_agent_run TIMESTAMP;'))
            db.session.commit()
            print("✅ Auto-Fix: User agent columns verified")
        except Exception:
            db.session.rollback()
        # --- [نهاية كود الإصلاح التلقائي] ---

        # تسجيل الـ Blueprints
        from app.auth import auth_bp
        from app.community import community_bp
        from app.cv import cv_bp
        from app.jobs import jobs_bp
        from app.search import search_bp
        from app.telegram_bot import telegram_bp
        from app.admin import admin_bp
        from app.chat import chat_bp
        from app.applications import apps_bp
        from app.agent_worker import agent_bp
        from app.interview import interview_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(community_bp, url_prefix='/community')
        app.register_blueprint(cv_bp, url_prefix='/cv')
        app.register_blueprint(jobs_bp, url_prefix='/jobs')
        app.register_blueprint(search_bp, url_prefix='/search')
        app.register_blueprint(telegram_bp, url_prefix='/telegram')
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(chat_bp, url_prefix='/chat')
        app.register_blueprint(apps_bp, url_prefix='/apps')
        app.register_blueprint(agent_bp, url_prefix='/agent')
        app.register_blueprint(interview_bp, url_prefix='/interview')

        db.create_all()

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_vars():
        return dict(Notification=Notification)

    # مسار الطوارئ المطور (احتياطي)
    @app.route('/force-db-update-2026')
    def force_db_update():
        from sqlalchemy import text
        try:
            db.session.execute(text('ALTER TABLE job RENAME COLUMN employer_id TO user_id;'))
            db.session.commit()
            return "✅ Database Synchronized!", 200
        except Exception as e:
            db.session.rollback()
            return f"❌ Fix Failed: {str(e)}", 500

    return app
