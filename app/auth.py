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
from app.models import User, Job, CV, Application, db, Notification, Post, JobQuestion, QuizResult, AgentMemory, Scholarship
from app.openrouter_ai import openrouter_ai

# إعداد نظام الـ Logging لمراقبة أداء الوكيل الذكي (The Executioner Watcher)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# --- دوال المساعدة السيادية ---

def generate_secure_qr(data):
    """توليد كود QR مع تنسيق عالي الدقة للهوية الرقمية 2026"""
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        logger.error(f"QR Generation Error: {e}")
        return ""

def upload_to_imgbb(file):
    """دالة مساعدة لرفع الصور لـ ImgBB لضمان استقرار السيرفر"""
    api_key = os.environ.get('IMGBB_API_KEY')
    if not api_key:
        logger.warning("⚠️ IMGBB_API_KEY is missing")
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
    """تحديث آخر ظهور للمستخدم"""
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
    """شرح آلية عمل المنصة"""
    return render_template('instructions.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        try:
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                login_user(user, remember=True)
                return redirect(url_for('auth.dashboard'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Login Error: {e}")
        flash('بيانات الدخول غير صحيحة يا مكنة، تأكد من كلمة المرور.', 'danger')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        role = request.form.get('role', 'jobseeker')

        try:
            if User.query.filter((User.email == email) | (User.username == username)).first():
                flash('البريد أو اسم المستخدم مسجل مسبقاً.', 'warning')
                return redirect(url_for('auth.register'))

            new_user = User(
                username=username,
                email=email,
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                role=role
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('auth.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('حدث خطأ أثناء التسجيل، حاول مرة أخرى.', 'danger')
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم الذكية: نسخة سيادية مضادة للانهيار 2026"""
    try:
        if current_user.role == 'employer':
            jobs = Job.query.filter_by(user_id=current_user.id).all()
            return render_template('dashboard_employer.html', jobs=jobs)

        # 1. جلب إحصائيات الأسبوع بحذر
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        recent_apps = Application.query.filter(Application.user_id == current_user.id, Application.applied_at >= one_week_ago).all()

        weekly_report_memory = AgentMemory.query.filter(AgentMemory.user_id == current_user.id, AgentMemory.action == 'weekly_report').order_by(AgentMemory.created_at.desc()).first()

        weekly_stats = {
            'matches_count': len(recent_apps),
            'top_score': max([a.match_score for a in recent_apps]) if recent_apps else 0,
            'ai_advice': weekly_report_memory.feedback_notes if weekly_report_memory else "أكمل بياناتك ليبدأ 'الجلاد' في تقديم نصائح مخصصة لك."
        }

        # 2. جلب آخر سيرة ذاتية وإدارة الرادار
        last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
        radar_labels = ["تقني", "تواصل", "خبرة", "قيادة", "إبداع"]
        radar_scores = [20, 20, 20, 20, 20] # قيم افتراضية منخفضة
        course_suggestions = "ارفع سيرتك الذاتية للحصول على توصيات AI عالمية."

        if last_cv:
            # استخدام البيانات الكاش إذا وجدت
            if last_cv.radar_labels and last_cv.radar_scores:
                radar_labels, radar_scores = last_cv.radar_labels, last_cv.radar_scores
            elif last_cv.extracted_text:
                try:
                    # محاولة توليد بيانات الرادار من AI
                    radar_data = openrouter_ai.generate_skills_radar_data(last_cv.extracted_text[:4000])
                    if radar_data and 'labels' in radar_data:
                        radar_labels, radar_scores = radar_data.get('labels'), radar_data.get('scores')
                        last_cv.radar_labels, last_cv.radar_scores = radar_labels, radar_scores
                        db.session.commit()
                except Exception as ai_err:
                    logger.error(f"AI Radar Error: {ai_err}")
                    db.session.rollback()
            
            # جلب الاقتراحات
            try:
                course_suggestions = openrouter_ai.suggest_courses_for_gaps({"labels": radar_labels, "scores": radar_scores})
            except: pass

        # 3. جلب الذاكرة والـ QR
        agent_memories = AgentMemory.query.filter_by(user_id=current_user.id).order_by(AgentMemory.created_at.desc()).limit(10).all()
        
        user_profile_url = url_for('auth.user_profile', username=current_user.username, _external=True)
        user_qr_base64 = generate_secure_qr(user_profile_url)

        return render_template('dashboard.html',
                               radar_labels=radar_labels,
                               radar_scores=radar_scores,
                               course_suggestions=course_suggestions,
                               user_qr=user_qr_base64,
                               agent_memories=agent_memories,
                               weekly_stats=weekly_stats,
                               cv=last_cv)

    except Exception as e:
        db.session.rollback()
        logger.critical(f"🔥 Dashboard Crash: {e}")
        # عرض صفحة الخطأ بكرامة بدل الانهيار التام
        return render_template('errors/500.html', error=str(e)), 500

@auth_bp.route('/update_agent_settings', methods=['POST'])
@login_required
def update_agent_settings():
    """تحديث إعدادات الرادار وربط الواتساب بنظام الجلاد"""
    try:
        current_user.agent_enabled = 'agent_enabled' in request.form
        current_user.agent_query = request.form.get('agent_query')
        current_user.role = request.form.get('role', 'jobseeker')
        current_user.agent_work_type = request.form.get('agent_work_type', 'both')
        current_user.agent_target_score = int(request.form.get('agent_target_score', 75))

        whatsapp = request.form.get('whatsapp_number')
        if whatsapp:
            clean_wa = whatsapp.strip().replace('+', '').replace(' ', '')
            current_user.whatsapp_number = clean_wa
            try:
                from app.agent_worker import send_whatsapp_via_whapi
                send_whatsapp_via_whapi(clean_wa, f"تم تفعيل رادار جوبيني الصارم بنجاح لـ {current_user.username} 🤖\nسنرسل لك الفرص التي تتجاوز {current_user.agent_target_score}% فقط.")
            except: pass

        db.session.add(AgentMemory(user_id=current_user.id, action='settings_updated', feedback_notes="تحديث إعدادات الرادار الصارم"))
        db.session.commit()
        flash('تم تحديث الرادار بنجاح ✅', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في التحديث: {str(e)}', 'danger')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/generate_interview_prep')
@login_required
def generate_interview_prep():
    """توليد أسئلة مقابلة مخصصة"""
    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not last_cv: return jsonify({'status': 'error', 'message': 'ارفع CV أولاً يا مكنة'})
    try:
        questions = openrouter_ai.generate_interview_simulation(last_cv.profession, last_cv.extracted_text[:4000])
        return jsonify({'status': 'success', 'questions': questions})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """عرض وتعديل الإعدادات الشخصية"""
    if request.method == 'POST':
        try:
            current_user.full_name = request.form.get('full_name')
            current_user.phone = request.form.get('phone')
            db.session.commit()
            flash('تم تحديث بيانات البروفايل بنجاح ✅', 'success')
        except Exception as e:
            db.session.rollback()
            flash('فشل التحديث، حاول لاحقاً.', 'danger')
        return redirect(url_for('auth.profile'))
    return render_template('profile_settings.html')

@auth_bp.route('/scanner')
@login_required
def scanner():
    """ماسح الـ QR الذكي للتوثيق"""
    return render_template('scanner.html')

@auth_bp.route('/user/<path:username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    user_qr = generate_secure_qr(request.url)
    return render_template('user_profile.html', user=user, user_qr=user_qr)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج، نراك قريباً في مهمة جديدة.', 'info')
    return redirect(url_for('auth.index'))

@auth_bp.route('/force_upgrade')
def force_upgrade():
    """إصلاح قاعدة البيانات وإضافة الأعمدة الأكاديمية الصارمة 2026"""
    try:
        from sqlalchemy import text
        # تحديثات المستخدم
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT \'jobseeker\''))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(20)'))
        # تحديثات السيرة الذاتية (GPA والدرجات)
        db.session.execute(text('ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS optimized_text TEXT'))
        db.session.execute(text('ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS gpa VARCHAR(50)'))
        db.session.execute(text('ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS academic_level VARCHAR(100)'))
        db.session.execute(text('ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS university_name VARCHAR(500)'))
        # تحديثات الذاكرة
        db.session.execute(text('ALTER TABLE "agent_memory" ADD COLUMN IF NOT EXISTS scholarship_id VARCHAR(500)'))
        db.session.commit()
        return "✅ تم تحديث هيكل قاعدة البيانات بنظام 'الجلاد' الصارم!"
    except Exception as e:
        db.session.rollback()
        return f"❌ فشل التحديث: {str(e)}"
