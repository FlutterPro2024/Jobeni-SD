import os
import sys
from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_required
from flask_migrate import Migrate
from flask_mail import Mail
from sqlalchemy import text

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

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'

    with app.app_context():
        # استيراد الموديلات أولاً
        from app import models
        
        # استيراد الـ Blueprints
        from app.community import community_bp
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

        # تسجيل الكومينتي (تأكد من وجود url_prefix)
        app.register_blueprint(community_bp, url_prefix='/community')

        # تسجيل البقية
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

        db.create_all()

    @app.route('/force-db-update-2026')
    def force_db_update():
        from app import models
        db.create_all()
        return "✅ Database Updated Successfully!", 200

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    return app
