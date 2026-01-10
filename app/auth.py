# ~/jobeni-sD/app/auth.py
import os
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Job, CV, Application, db, InterviewReport, Notification
from app.serper_search import serper_searcher
from app.notifications import send_welcome_email

auth_bp = Blueprint('auth', __name__)

# --- الصفحة الرئيسية ---
@auth_bp.route('/')
def index():
    try:
        # جلب أحدث 6 وظائف نشطة لعرضها في الهوم بيج
        latest_jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).limit(6).all()
    except Exception:
        latest_jobs = []
    return render_template('index.html', jobs=latest_jobs)

# --- تسجيل الدخول ---
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
        
        flash('بيانات الدخول غير صحيحة، يرجى المحاولة مرة أخرى.', 'danger')
    
    return render_template('login.html')

# --- تسجيل حساب جديد ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        role = request.form.get('role', 'jobseeker')

        # التحقق من عدم تكرار البيانات
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash('اسم المستخدم أو البريد الإلكتروني مسجل بالفعل.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(
            username=username,
            email=email,
            full_name=request.form.get('full_name', '').strip(),
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            role=role
        )
        db.session.add(new_user)
        db.session.commit()

        # محاولة إرسال بريد الترحيب
        try:
            send_welcome_email(new_user.email, new_user.username, new_user.id)
        except Exception as e:
            print(f"⚠️ [Mail Error]: {e}")

        flash('تم إنشاء حسابك بنجاح! يمكنك الآن تسجيل الدخول.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

# --- لوحة التحكم الذكية ---
@auth_bp.route('/dashboard')
@login_required
def dashboard():
    # 1. لوحة تحكم صاحب العمل
    if current_user.role == 'employer':
        return render_template('dashboard_employer.html', jobs=current_user.jobs)

    # 2. لوحة تحكم الباحث عن عمل
    recent_apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).limit(5).all()
    reports = InterviewReport.query.filter_by(user_id=current_user.id).order_by(InterviewReport.created_at.asc()).all()

    # تجهيز بيانات الرسم البياني لمستوى الأداء
    chart_labels = [r.created_at.strftime('%m/%d') for r in reports]
    chart_scores = []
    for r in reports:
        match = re.search(r'(\d+)', str(r.score))
        chart_scores.append(int(match.group(1)) if match else 0)

    # الرادار: جلب وظائف من الويب بناءً على آخر سيرة ذاتية مرفوعة
    web_jobs = []
    latest_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if latest_cv and latest_cv.profession:
        try:
            res = serper_searcher.search_jobs(query=f"{latest_cv.profession} jobs in Sudan")
            if res and 'jobs' in res:
                web_jobs = res['jobs'][:4]
        except Exception as e:
            print(f"❌ Serper API Error: {e}")

    return render_template('dashboard.html',
                           cvs=current_user.cvs,
                           recent_applications=recent_apps,
                           web_jobs=web_jobs,
                           chart_labels=chart_labels,
                           chart_scores=chart_scores)

# --- نظام التنبيهات (Real-time APIs) ---
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

# --- الملف الشخصي ---
@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username', '').strip()
        current_user.email = request.form.get('email', '').lower().strip()
        current_user.full_name = request.form.get('full_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.bio = request.form.get('bio', '').strip()
        current_user.headline = request.form.get('headline', '').strip()
        current_user.location_name = request.form.get('location_name', '').strip()
        
        db.session.commit()
        flash('تم تحديث ملفك الشخصي بنجاح!', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('profile.html')

# --- تسجيل الخروج ---
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح. نتمنى رؤيتك قريباً.', 'info')
    return redirect(url_for('auth.login'))

# --- إعدادات الرادار الآلي ---
@auth_bp.route('/update-agent-settings', methods=['POST'])
@login_required
def update_agent_settings():
    current_user.agent_query = request.form.get('agent_query')
    current_user.agent_enabled = 'agent_enabled' in request.form
    db.session.commit()
    flash('تم تحديث إعدادات البحث الآلي بنجاح.', 'success')
    return redirect(url_for('auth.dashboard'))
@auth_bp.route('/fix-db-now')
def fix_db_now():
    from sqlalchemy import text
    try:
        # تنفيذ التعديلات يدوياً على السيرفر السحابي
        db.session.execute(text('ALTER TABLE job RENAME COLUMN employer_id TO user_id;'))
    except: pass # إذا كان الاسم متغيراً بالفعل تخطى
    
    try:
        db.session.execute(text('ALTER TABLE job ADD COLUMN IF NOT EXISTS latitude FLOAT;'))
        db.session.execute(text('ALTER TABLE job ADD COLUMN IF NOT EXISTS longitude FLOAT;'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS lat FLOAT;'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS lng FLOAT;'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS location_name VARCHAR(100);'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS phone VARCHAR(20);'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS avatar VARCHAR(200);'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS headline VARCHAR(200);'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS bio TEXT;'))
        db.session.execute(text('DROP TABLE IF EXISTS alembic_version;'))
        db.session.commit()
        return "✅ تم تحديث قاعدة بيانات Vercel بنجاح!"
    except Exception as e:
        return f"❌ حدث خطأ: {str(e)}"
