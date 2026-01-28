# ~/jobeni-sD/app/auth.py
import os
import re
import base64
import io
import qrcode
import requests
import urllib.parse
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Job, CV, Application, db, InterviewReport, Notification, Post, JobQuestion, QuizResult, AgentMemory
from app.openrouter_ai import openrouter_ai

# إعداد نظام الـ Logging لمراقبة أداء الوكيل الذكي
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# --- دوال المساعدة السيادية ---

def generate_secure_qr(data):
    """توليد كود QR مع تنسيق عالي الدقة للهوية الرقمية 2026"""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def upload_to_imgbb(file):
    """دالة مساعدة لرفع الصور لـ ImgBB واسترجاع الرابط المباشر لضمان استقرار الصور"""
    api_key = os.environ.get('IMGBB_API_KEY')
    if not api_key:
        logger.warning("⚠️ IMGBB_API_KEY is missing in environment variables")
        return None
    url = "https://api.imgbb.com/1/upload"
    try:
        files = {"image": file.read()}
        params = {"key": api_key}
        response = requests.post(url, params=params, files=files, timeout=10)
        data = response.json()
        if data.get('status') == 200:
            return data['data']['url']
    except Exception as e:
        logger.error(f"❌ ImgBB Upload Error: {e}")
    return None

# --- المسارات والوظائف الذكية ---

@auth_bp.before_app_request
def update_last_seen():
    """تحديث آخر ظهور للمستخدم مع معالجة أخطاء الجلسة"""
    try:
        if current_user.is_authenticated:
            current_user.last_seen = datetime.utcnow()
            db.session.commit()
    except Exception:
        db.session.rollback()

@auth_bp.route('/')
def index():
    """الصفحة الرئيسية مع عرض أحدث الوظائف النشطة"""
    try:
        latest_jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).limit(6).all()
    except Exception:
        db.session.rollback()
        latest_jobs = []
    return render_template('index.html', jobs=latest_jobs)

@auth_bp.route('/instructions')
def instructions():
    """صفحة شرح كيفية عمل المنصة لعام 2026"""
    return render_template('instructions.html')

@auth_bp.route('/scanner')
@login_required
def scanner():
    """مسار الماسح الضوئي للـ QR"""
    return render_template('scanner.html')

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
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('auth.dashboard'))
        flash('بيانات الدخول غير صحيحة.', 'danger')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """تسجيل حساب جديد مع دعم خيار باحث عن منحة 2026"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role', 'jobseeker')

        if password != confirm_password:
            flash('كلمات المرور غير متطابقة.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash('البريد أو اسم المستخدم مسجل مسبقاً.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            role=role,
            avatar=f"https://ui-avatars.com/api/?name={username}&background=random&color=fff",
            last_seen=datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.commit()

        role_label = "باحث عن منحة" if role == "scholarship_seeker" else "عضو جديد"
        flash(f'مرحباً بك في جوبيني! تم إنشاء حسابك كـ {role_label}.', 'success')
        login_user(new_user)
        return redirect(url_for('auth.dashboard'))
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم الذكية: تشمل رادار المهارات، التقارير الأسبوعية، والتعلم الآلي"""
    if current_user.role == 'employer':
        jobs = Job.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard_employer.html', jobs=jobs)

    one_week_ago = datetime.utcnow() - timedelta(days=7)

    # تصحيح: استخدام applied_at بدلاً من created_at لجدول Application
    recent_apps = Application.query.filter(
        Application.user_id == current_user.id,
        Application.applied_at >= one_week_ago
    ).all()

    training_sessions = AgentMemory.query.filter(
        AgentMemory.user_id == current_user.id,
        AgentMemory.action == 'interview_prep',
        AgentMemory.created_at >= one_week_ago
    ).count()

    weekly_report_memory = AgentMemory.query.filter(
        AgentMemory.user_id == current_user.id,
        AgentMemory.action == 'weekly_report'
    ).order_by(AgentMemory.created_at.desc()).first()

    weekly_stats = {
        'matches_count': len(recent_apps),
        'top_score': max([a.match_score for a in recent_apps]) if recent_apps else 0,
        'training_sessions': training_sessions,
        'ai_advice': weekly_report_memory.feedback_notes if weekly_report_memory else "أكمل بياناتك ليبدأ الأيجنت في تقديم نصائح مخصصة لك."
    }

    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    radar_labels = ["تقني", "تواصل", "خبرة", "قيادة", "إبداع"]
    radar_scores = [50, 50, 50, 50, 50]

    if current_user.role == 'scholarship_seeker':
        course_suggestions = "الوكيل الذكي يستعد الآن لجلب منح دراسية تناسب خلفيتك الأكاديمية. ارفع شهاداتك للبدء."
    else:
        course_suggestions = "ارفع سيرتك الذاتية للحصول على توصيات مخصصة من مستشار AI عالمي."

    if last_cv and last_cv.extracted_text:
        try:
            if last_cv.radar_labels and last_cv.radar_scores:
                radar_labels = last_cv.radar_labels
                radar_scores = last_cv.radar_scores
            else:
                radar_data = openrouter_ai.generate_skills_radar_data(last_cv.extracted_text[:4000])
                radar_labels = radar_data.get('labels', radar_labels)
                radar_scores = radar_data.get('scores', radar_scores)
                last_cv.radar_labels = radar_labels
                last_cv.radar_scores = radar_scores
                db.session.commit()
            course_suggestions = openrouter_ai.suggest_courses_for_gaps({"labels": radar_labels, "scores": radar_scores})
        except Exception as e:
            logger.error(f"Radar Error: {e}")

    agent_memories = AgentMemory.query.filter_by(user_id=current_user.id).order_by(AgentMemory.created_at.desc()).limit(10).all()
    user_link = url_for('auth.verify_certificate', username=current_user.username, _external=True)
    user_qr_base64 = generate_secure_qr(user_link)

    return render_template('dashboard.html',
                           radar_labels=radar_labels,
                           radar_scores=radar_scores,
                           course_suggestions=course_suggestions,
                           user_qr=user_qr_base64,
                           agent_memories=agent_memories,
                           weekly_stats=weekly_stats)

@auth_bp.route('/update_agent_settings', methods=['POST'])
@login_required
def update_agent_settings():
    """تحديث إعدادات الوكيل الذكي والواتساب"""
    try:
        current_user.agent_enabled = 'agent_enabled' in request.form
        current_user.agent_query = request.form.get('agent_query')
        current_user.agent_work_type = request.form.get('agent_work_type', 'both')
        current_user.agent_target_score = int(request.form.get('agent_target_score', 75))

        whatsapp = request.form.get('whatsapp_number')
        if whatsapp:
            clean_wa = whatsapp.strip().replace('+', '').replace(' ', '').replace('-', '')
            if clean_wa != current_user.whatsapp_number:
                current_user.whatsapp_number = clean_wa
                try:
                    from app.agent_worker import send_whatsapp_via_whapi
                    welcome_msg = f"مرحباً بك في جوبيني يا *{current_user.username}*! 🤖 تم ربط رادارك الذكي بنجاح."
                    send_whatsapp_via_whapi(clean_wa, welcome_msg)
                except: pass

        db.session.add(AgentMemory(user_id=current_user.id, action='settings_updated', feedback_notes="تم تحديث إعدادات الرادار"))
        db.session.commit()
        flash('تم تحديث إعدادات الرادار بنجاح ✅', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {str(e)}', 'danger')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/test_whatsapp_agent', methods=['POST', 'GET'])
@login_required
def test_whatsapp_agent():
    if not current_user.whatsapp_number:
        return jsonify({'status': 'error', 'message': 'يرجى حفظ رقم الواتساب أولاً'}), 400

    from app.agent_worker import send_whatsapp_via_whapi
    test_msg = f"🔔 اختبار الرادار الذكي: الاتصال مستقر يا {current_user.username} ✅"
    res = send_whatsapp_via_whapi(current_user.whatsapp_number, test_msg)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success', 'message': 'وصلت رسالة الاختبار! ✅'})
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/generate_interview_prep')
@login_required
def generate_interview_prep():
    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not last_cv: return jsonify({'status': 'error', 'message': 'ارفع سيرتك الذاتية أولاً'}), 400
    try:
        questions = openrouter_ai.generate_interview_simulation(last_cv.profession or "متخصص", last_cv.extracted_text[:4000])
        db.session.add(AgentMemory(user_id=current_user.id, action='interview_prep', feedback_notes="توليد جلسة تدريب"))
        db.session.commit()
        return jsonify({'status': 'success', 'questions': questions})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.bio = request.form.get('bio')
        current_user.headline = request.form.get('headline')
        if 'avatar' in request.files:
            img_url = upload_to_imgbb(request.files['avatar'])
            if img_url: current_user.avatar = img_url
        db.session.commit()
        flash('تم تحديث بروفايلك بنجاح ✅', 'success')
        return redirect(url_for('auth.profile'))

    user_link = url_for('auth.user_profile', username=current_user.username, _external=True)
    user_qr_base64 = generate_secure_qr(user_link)
    return render_template('profile.html', user_qr=user_qr_base64)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/user/<path:username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    is_online = (datetime.utcnow() - user.last_seen).total_seconds() < 300 if user.last_seen else False
    user_qr = generate_secure_qr(url_for('auth.user_profile', username=user.username, _external=True))
    return render_template('user_profile.html', user=user, is_online=is_online, user_qr=user_qr)

@auth_bp.route('/verify/<username>')
def verify_certificate(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('certificate_verify.html', user=user)

@auth_bp.route('/force_upgrade')
def force_upgrade():
    """مسار التحديث القوي لإصلاح كافة مشاكل قاعدة البيانات في Vercel"""
    try:
        from sqlalchemy import text
        # 1. إضافة أعمدة جدول المستخدم (User)
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(20)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_evaluation TEXT'))
        
        # 2. إضافة العمود الحرج في agent_memory (لربط المنح والدراسات)
        db.session.execute(text('ALTER TABLE "agent_memory" ADD COLUMN IF NOT EXISTS scholarship_id INTEGER'))
        
        # 3. إنشاء جدول المنح (Scholarship) في حال عدم وجوده
        db.session.execute(text('''
            CREATE TABLE IF NOT EXISTS scholarship (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                university VARCHAR(200),
                country VARCHAR(100),
                field_of_study VARCHAR(200),
                level VARCHAR(50),
                funding_type VARCHAR(50),
                deadline TIMESTAMP,
                official_link VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        
        db.session.commit()
        return "✅ تم تحديث قاعدة البيانات وإضافة scholarship_id وجدول المنح بنجاح! جرب الداشبورد الآن."
    except Exception as e:
        db.session.rollback()
        return f"❌ فشل التحديث العميق: {str(e)}"
