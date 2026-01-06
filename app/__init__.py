# ~/jobeni-sD/app/__init__.py
import os
import sys
from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_mail import Mail

# إضافة المسار الرئيسي للمشروع لضمان وصول الاستيرادات
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config

# تعريف كائنات الإضافات
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()

def create_app(config_name='default'):
    app = Flask(__name__)

    # اختيار الإعدادات (Production في حال Vercel)
    if os.environ.get('VERCEL'):
        app.config.from_object(config['production'])
    else:
        app.config.from_object(config[config_name])

    app.config['MAIL_DEFAULT_SENDER'] = app.config.get('MAIL_USERNAME')

    # تهيئة الإضافات مع التطبيق
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = "يرجى تسجيل الدخول للوصول إلى هذه الصفحة."
    login_manager.login_message_category = "info"

    @app.before_request
    def check_for_maintenance():
        if os.path.exists("maintenance.flag") and \
           request.endpoint not in ['auth.login', 'static', 'admin.toggle_maintenance'] and \
           (not current_user.is_authenticated or current_user.role != 'admin'):
            return render_template('maintenance.html'), 503

    with app.app_context():
        # استيراد كافة الـ Blueprints
        from app.auth import auth_bp
        from app.cv import cv_bp
        from app.jobs import jobs_bp
        from app.search import search_bp
        from app.telegram_bot import telegram_bp
        from app.admin import admin_bp
        from app.chat import chat_bp
        from app.applications import apps_bp
        from app.agent_worker import agent_bp  # الوكيل الجديد

        # تسجيل الـ Blueprints
        app.register_blueprint(auth_bp)
        app.register_blueprint(cv_bp)
        app.register_blueprint(jobs_bp)
        app.register_blueprint(search_bp)
        app.register_blueprint(telegram_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(chat_bp)
        app.register_blueprint(apps_bp)
        app.register_blueprint(agent_bp) # تفعيل مسار الوكيل

        # إنشاء الجداول (تلقائياً عند التشغيل الأول)
        # ملاحظة: في Vercel مع PostgreSQL قد تحتاج لعمل Migrations 
        # ولكن db.create_all() ستحاول إنشاء الجداول غير الموجودة.
        db.create_all()

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    return app
