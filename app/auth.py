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
        # استخدام استعلام محدد لتجنب أي Cache قديم للأعمدة
        latest_jobs = db.session.query(Job).filter(Job.is_active == True).order_by(Job.created_at.desc()).limit(6).all()
    except Exception as e:
        print(f"❌ Database Error in Index: {e}")
        db.session.rollback()
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
        try:
            send_welcome_email(new_user.email, new_user.username, new_user.id)
        except: pass
        flash('تم إنشاء حسابك بنجاح! يمكنك الآن تسجيل الدخول.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

# --- لوحة التحكم ---
@auth_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'employer':
        # استخدام العلاقة المعدلة
        return render_template('dashboard_employer.html', jobs=current_user.jobs)

    recent_apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).limit(5).all()
    reports = InterviewReport.query.filter_by(user_id=current_user.id).order_by(InterviewReport.created_at.asc()).all()

    chart_labels = [r.created_at.strftime('%m/%d') for r in reports]
    chart_scores = [int(re.search(r'(\d+)', str(r.score)).group(1)) if re.search(r'(\d+)', str(r.score)) else 0 for r in reports]

    web_jobs = []
    latest_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if latest_cv and latest_cv.profession:
        try:
            res = serper_searcher.search_jobs(query=f"{latest_cv.profession} jobs in Sudan")
            web_jobs = res.get('jobs', [])[:4]
        except: pass

    return render_template('dashboard.html', cvs=current_user.cvs, recent_applications=recent_apps,
                           web_jobs=web_jobs, chart_labels=chart_labels, chart_scores=chart_scores)

# --- إعدادات الوكيل الذكي ---
@auth_bp.route('/update-agent-settings', methods=['GET', 'POST'])
@login_required
def update_agent_settings():
    if request.method == 'POST':
        current_user.agent_query = request.form.get('agent_query')
        current_user.agent_enabled = 'agent_enabled' in request.form
        db.session.commit()
        flash('تم تحديث إعدادات القناص الذكي بنجاح! 🚀', 'success')
        return redirect(url_for('auth.dashboard'))
    return render_template('agent_settings.html')

# --- إصلاح قاعدة البيانات ---
@auth_bp.route('/fix-db-now')
def fix_db_now():
    from sqlalchemy import text
    try:
        # إصلاح جذري بـ SQL
        db.session.execute(text("""
            DO $$ 
            BEGIN 
                IF EXISTS (SELECT 1 FROM information_schema.columns 
                           WHERE table_name='job' AND column_name='employer_id') THEN
                    ALTER TABLE job RENAME COLUMN employer_id TO user_id;
                END IF;
            END $$;
        """))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE;'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_query VARCHAR(255);'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_agent_run TIMESTAMP;'))
        db.session.commit()
        return "✅ تم تحديث قاعدة البيانات بنجاح!"
    except Exception as e:
        db.session.rollback()
        return f"❌ حدث خطأ: {str(e)}"

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج.', 'info')
    return redirect(url_for('auth.login'))
