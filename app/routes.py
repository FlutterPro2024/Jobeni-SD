# app/auth/routes.py
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.auth import bp
from app.models import User

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'jobseeker')

        user = User.query.filter((User.username == username) | (User.email == email)).first()
        if user:
            flash('اسم المستخدم أو البريد الإلكتروني مسجل مسبقاً.', 'danger')
            return redirect(url_for('auth.register'))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='sha256'),
            role=role
        )
        db.session.add(new_user)
        db.session.commit()
        flash('تم التسجيل بنجاح! يمكنك الآن تسجيل الدخول.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash('خطأ في البريد الإلكتروني أو كلمة المرور.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        return redirect(url_for('main.dashboard'))
    return render_template('auth/login.html')

@bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    current_user.full_name = request.form.get('full_name')
    current_user.headline = request.form.get('headline')
    current_user.bio = request.form.get('bio')
    current_user.phone = request.form.get('phone')
    current_user.location_name = request.form.get('location_name')
    current_user.telegram_id = request.form.get('telegram_id')
    
    db.session.commit()
    flash('تم تحديث بيانات ملفك الشخصي بنجاح.', 'success')
    return redirect(url_for('main.profile'))

@bp.route('/agent/update', methods=['POST'])
@login_required
def update_agent_settings():
    """تحديث إعدادات الرادار الوظيفي"""
    current_user.agent_query = request.form.get('agent_query')
    current_user.agent_enabled = True if request.form.get('agent_enabled') == 'on' else False
    
    db.session.commit()
    flash('تم تحديث إعدادات الرادار بنجاح.', 'info')
    return redirect(url_for('main.dashboard'))

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
