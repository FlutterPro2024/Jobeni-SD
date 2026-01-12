# ~/jobeni-sD/app/auth.py
import os
import re
import cloudinary
import cloudinary.uploader
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app.models import User, Job, CV, Application, db, InterviewReport, Notification, Message
from app.serper_search import serper_searcher
from app.notifications import send_welcome_email
from sqlalchemy import text

# إعدادات Cloudinary (تُستبدل بالبيانات القادمة من الدوحة)
cloudinary.config(
  cloud_name = "dvv7v9v9v", 
  api_key = "your_key", 
  api_secret = "your_secret",
  secure = True
)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    try:
        query = text("""
            SELECT id, title, company_name, location, description, category, salary, job_type, created_at
            FROM job WHERE is_active = true ORDER BY created_at DESC LIMIT 6
        """)
        result = db.session.execute(query)
        latest_jobs = result.fetchall()
    except Exception as e:
        db.session.rollback()
        latest_jobs = []
    return render_template('index.html', jobs=latest_jobs)

@auth_bp.route('/run-jobs-agent')
@login_required
def run_jobs_agent():
    try:
        from app.serper_search import serper_searcher
        query_text = current_user.agent_query or "وظائف في السودان"
        results = serper_searcher.search_jobs(query_text)

        if isinstance(results, str):
            flash(f'تنبيه من المحرك: {results}', 'info')
            return redirect(url_for('auth.dashboard'))

        new_jobs_count = 0
        if results and isinstance(results, list):
            for job_data in results:
                if not isinstance(job_data, dict): continue
                title = job_data.get('title')
                company = job_data.get('company')
                if not title or not company: continue

                exists = Job.query.filter_by(title=title, company_name=company).first()
                if not exists:
                    new_job = Job(
                        title=title, company_name=company,
                        location=job_data.get('location', 'ريموت'),
                        description=job_data.get('description', ''),
                        link=job_data.get('link', ''),
                        source='الرادار الآلي', is_active=True
                    )
                    db.session.add(new_job)
                    new_jobs_count += 1
            db.session.commit()
            flash(f'تم تشغيل الرادار بنجاح! وجدنا {new_jobs_count} وظائف جديدة.', 'success')
        else:
            flash('لم يتم العثور على نتائج حالياً.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء تشغيل الرادار: {str(e)}', 'danger')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return redirect(url_for('auth.dashboard'))
        flash('بيانات الدخول غير صحيحة.', 'danger')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').lower().strip()
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash('البريد أو المستخدم مسجل مسبقاً.', 'warning')
            return redirect(url_for('auth.register'))
        
        # استخدام رابط صورة تلقائي ذكي
        avatar_url = f"https://ui-avatars.com/api/?name={username}&background=random&color=fff"
        
        new_user = User(
            username=username, email=email,
            full_name=request.form.get('full_name', '').strip(),
            password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'),
            role=request.form.get('role', 'jobseeker'),
            avatar=avatar_url
        )
        db.session.add(new_user)
        db.session.commit()
        # إرسال إيميل الترحيب
        try: send_welcome_email(email, username, new_user.id)
        except: pass
        flash('تم إنشاء الحساب بنجاح!', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'employer':
        query = text("SELECT id, title, company_name, location, created_at FROM job WHERE user_id = :uid")
        jobs = db.session.execute(query, {"uid": current_user.id}).fetchall()
        return render_template('dashboard_employer.html', jobs=jobs)

    recent_apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).limit(5).all()
    reports = InterviewReport.query.filter_by(user_id=current_user.id).order_by(InterviewReport.created_at.asc()).all()
    chart_labels = [r.created_at.strftime('%m/%d') for r in reports]
    chart_scores = []
    for r in reports:
        match = re.search(r'(\d+)', str(r.score))
        chart_scores.append(int(match.group(1)) if match else 0)

    return render_template('dashboard.html', cvs=current_user.cvs, recent_applications=recent_apps,
                           chart_labels=chart_labels, chart_scores=chart_scores)

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.bio = request.form.get('bio')
        db.session.commit()
        flash('تم تحديث البروفايل', 'success')
    return render_template('profile.html')

@auth_bp.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    file = request.files.get('avatar')
    if file:
        try:
            # الرفع السحابي لحل مشكلة Vercel
            upload_result = cloudinary.uploader.upload(file, 
                folder="jobeni_avatars",
                public_id=f"user_{current_user.id}",
                overwrite=True)
            current_user.avatar = upload_result['secure_url']
            db.session.commit()
            flash('تم تحديث الصورة بنجاح!', 'success')
        except Exception as e:
            flash(f'خطأ في الرفع: {str(e)}', 'danger')
    return redirect(url_for('auth.profile'))

@auth_bp.route('/update_agent_settings', methods=['POST'])
@login_required
def update_agent_settings():
    current_user.agent_enabled = 'agent_enabled' in request.form
    current_user.agent_query = request.form.get('agent_query')
    db.session.commit()
    flash('تم تحديث إعدادات المستشار الذكي', 'success')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/unread_count')
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@auth_bp.route('/mark_notifications_read', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({Notification.is_read: True})
    db.session.commit()
    return jsonify({'status': 'success'})

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
