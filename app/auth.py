# ~/jobeni-sD/app/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Job, CV, Application, db, InterviewSession
from app.serper_search import serper_searcher
from app.notifications import send_welcome_email

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
            flash('المستخدم موجود مسبقاً.', 'warning')
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
            send_welcome_email(new_user.email, new_user.username)
        except Exception as e:
            print(f"❌ [Mail Error] Failed to send: {e}")

        flash('تم إنشاء الحساب بنجاح! سجل دخولك الآن.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'employer':
        return render_template('dashboard_employer.html', jobs=current_user.jobs)

    recent_apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).limit(5).all()
    sessions = InterviewSession.query.filter_by(user_id=current_user.id).order_by(InterviewSession.created_at.desc()).all()
    user_messages = getattr(current_user, 'received_messages', [])

    web_jobs = []
    latest_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()

    if latest_cv and latest_cv.profession:
        try:
            res = serper_searcher.search_jobs(query=f"{latest_cv.profession} jobs")
            if res and 'jobs' in res:
                web_jobs = res['jobs'][:4]
        except Exception as e:
            print(f"Dashboard Search Error: {e}")

    return render_template('dashboard.html',
                           cvs=current_user.cvs,
                           recent_applications=recent_apps,
                           web_jobs=web_jobs,
                           sessions=sessions,
                           messages=user_messages)

@auth_bp.route('/update-agent-settings', methods=['POST'])
@login_required
def update_agent_settings():
    """تحديث إعدادات الوكيل الذكي من الداشبورد"""
    agent_enabled = 'agent_enabled' in request.form
    agent_query = request.form.get('agent_query', '').strip()
    
    current_user.agent_enabled = agent_enabled
    current_user.agent_query = agent_query
    
    try:
        db.session.commit()
        flash('✅ تم تحديث إعدادات الوكيل الذكي بنجاح!', 'success')
    except:
        db.session.rollback()
        flash('❌ حدث خطأ أثناء الحفظ.', 'danger')
        
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.username = request.form.get('username')
        current_user.email = request.form.get('email').lower().strip()
        try:
            db.session.commit()
            flash('تم تحديث الملف الشخصي بنجاح.', 'success')
        except:
            db.session.rollback()
            flash('اسم المستخدم أو البريد مستخدم بالفعل.', 'danger')
        return redirect(url_for('auth.profile'))
    return render_template('profile.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
