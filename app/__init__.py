# ~/jobeni-sD/app/__init__.py
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
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
    env_config = 'production' if os.environ.get('VERCEL') else config_name
    app.config.from_object(config[env_config])
    
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'

    with app.app_context():
        from app.models import User, Notification
        from app.auth import auth_bp
        from app.jobs import jobs_bp
        from app.chat import chat_bp
        from app.telegram_bot import telegram_bp
        
        # تسجيل الأساسيات فوراً
        app.register_blueprint(auth_bp)
        app.register_blueprint(jobs_bp, url_prefix='/jobs')
        app.register_blueprint(chat_bp, url_prefix='/chat')
        app.register_blueprint(telegram_bp, url_prefix='/telegram')

        # تسجيل البقية مع حماية
        try:
            from app.cv import cv_bp
            app.register_blueprint(cv_bp, url_prefix='/cv')
            from app.search import search_bp
            app.register_blueprint(search_bp, url_prefix='/search')
            from app.admin import admin_bp
            app.register_blueprint(admin_bp, url_prefix='/admin')
            from app.community import community_bp
            app.register_blueprint(community_bp, url_prefix='/community')
        except Exception as e:
            print(f"Non-critical blueprint failed: {e}")

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    return app
