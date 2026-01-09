# ~/jobeni-sD/app/__init__.py
import os
import sys
from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_required
from flask_migrate import Migrate
from flask_mail import Mail

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()

def create_app(config_name='default'):
    app = Flask(__name__)

    if os.environ.get('VERCEL'):
        app.config.from_object(config['production'])
    else:
        app.config.from_object(config[config_name])

    app.config['MAIL_DEFAULT_SENDER'] = app.config.get('MAIL_USERNAME')

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
        from app import models
        from app.auth import auth_bp
        from app.cv import cv_bp
        from app.jobs import jobs_bp
        from app.search import search_bp
        from app.telegram_bot import telegram_bp
        from app.admin import admin_bp
        from app.chat import chat_bp
        from app.applications import apps_bp
        from app.agent_worker import agent_bp
        from app.interview import interview_bp
        from app.community import community_bp 

        app.register_blueprint(auth_bp)
        app.register_blueprint(cv_bp)
        app.register_blueprint(jobs_bp)
        app.register_blueprint(search_bp)
        app.register_blueprint(telegram_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(chat_bp)
        app.register_blueprint(apps_bp)
        app.register_blueprint(agent_bp)
        app.register_blueprint(interview_bp)
        # تم ضبط الـ prefix هنا لضمان عمل المسارات بشكل صحيح
        app.register_blueprint(community_bp, url_prefix='/community') 

        db.create_all()

    @app.route('/notifications/mark-read', methods=['POST'])
    @login_required
    def mark_notifications_read():
        from app.models import Notification
        try:
            Notification.query.filter_by(user_id=current_user.id, is_read=False).update({Notification.is_read: True})
            db.session.commit()
            return jsonify({'status': 'success'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/force-db-update-2026')
    def force_db_update():
        try:
            with app.app_context():
                from app import models
                db.create_all()
                return "✅ Database Updated Successfully!", 200
        except Exception as e:
            return f"❌ Migration Error: {str(e)}", 500

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    return app
