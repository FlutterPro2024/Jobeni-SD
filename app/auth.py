# ~/jobeni-sD/app/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app.models import User, Job, CV, Application, db, InterviewReport, Notification
from app.serper_search import serper_searcher
from app.notifications import send_welcome_email
import re, os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    latest_jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).limit(6).all()
    return render_template('index.html', jobs=latest_jobs)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return redirect(url_for('auth.dashboard'))
        flash('بيانات الدخول غير صحيحة.', 'danger')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').lower().strip()
        role = request.form.get('role', 'jobseeker')

        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash('اسم المستخدم أو البريد الإلكتروني مسجل مسبقاً.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(
            username=username,
            email=email,
            full_name=request.form.get('full_name'),
            password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'),
            role=role
        )
        db.session.add(new_user)
        db.session.commit()

        try:
            send_welcome_email(new_user.email, new_user.username, new_user.id)
        except Exception as e:
            print(f"❌ [Mail Error]: {e}")

        flash('تم إنشاء الحساب بنجاح! سجل دخولك الآن.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'employer':
        return render_template('dashboard_employer.html', jobs=current_user.jobs)

    recent_apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).limit(5).all()
    reports = InterviewReport.query.filter_by(user_id=current_user.id).order_by(InterviewReport.created_at.asc()).all()

    chart_labels = [r.created_at.strftime('%m/%d') for r in reports]
    chart_scores = []
    for r in reports:
        match = re.search(r'(\d+)', str(r.score))
        chart_scores.append(int(match.group(1)) if match else 0)

    web_jobs = []
    latest_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if latest_cv and latest_cv.profession:
        try:
            res = serper_searcher.search_jobs(query=f"{latest_cv.profession} jobs in Sudan")
            if res and 'jobs' in res:
                web_jobs = res['jobs'][:4]
        except Exception as e:
            print(f"Dashboard Search Error: {e}")

    return render_template('dashboard.html',
                           cvs=current_user.cvs,
                           recent_applications=recent_apps,
                           web_jobs=web_jobs,
                           chart_labels=chart_labels,
                           chart_scores=chart_scores)

@auth_bp.route('/notifications/unread-count')
@login_required
def unread_count():
    count = current_user.notifications.filter_by(is_read=False).count()
    return jsonify({'count': count})

@auth_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    current_user.notifications.filter_by(is_read=False).update({Notification.is_read: True})
    db.session.commit()
    return jsonify({'status': 'success'})

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username').strip()
        current_user.email = request.form.get('email').lower().strip()
        current_user.full_name = request.form.get('full_name').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.bio = request.form.get('bio', '').strip()
        current_user.headline = request.form.get('headline', '').strip()
        current_user.location_name = request.form.get('location_name', '').strip()
        db.session.commit()
        flash('تم تحديث ملفك الشخصي بنجاح!', 'success')
        return redirect(url_for('auth.profile'))
    return render_template('profile.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('auth.login'))
