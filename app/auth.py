# ~/jobeni-sD/app/auth.py
import os
import re
import base64
import io
import qrcode
import requests
import urllib.parse
import logging
from datetime import datetime
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
    """عرض دليل المنصة للمستخدمين والمطورين"""
    return render_template('instructions.html')

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
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').lower().strip()
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash('البريد أو اسم المستخدم مسجل مسبقاً.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(
            username=username,
            email=email,
            full_name=request.form.get('full_name', '').strip(),
            password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'),
            role=request.form.get('role', 'jobseeker'),
            avatar=f"https://ui-avatars.com/api/?name={username}&background=random&color=fff",
            last_seen=datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.commit()
        flash('تم إنشاء الحساب بنجاح! مرحباً بك في جوبيني.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم الذكية: تشمل رادار المهارات، التقارير الأسبوعية، والتعلم الآلي"""
    if current_user.role == 'employer':
        jobs = Job.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard_employer.html', jobs=jobs)

    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    radar_labels = ["تقني", "تواصل", "خبرة", "قيادة", "إبداع"]
    radar_scores = [50, 50, 50, 50, 50]
    course_suggestions = "ارفع سيرتك الذاتية للحصول على توصيات مخصصة من مستشار AI عالمي."

    # نظام التعلم الذكي: تحليل الرفض السابق لتحسين التوصيات
    rejected_count = Application.query.filter_by(user_id=current_user.id, status='rejected').count()

    if last_cv and last_cv.extracted_text:
        try:
            if last_cv.radar_labels and last_cv.radar_scores:
                radar_labels = last_cv.radar_labels
                radar_scores = last_cv.radar_scores
            else:
                # دعم Chunking ضمني عبر تحليل أول 4000 حرف لضمان استقرار الـ AI
                radar_data = openrouter_ai.generate_skills_radar_data(last_cv.extracted_text[:4000])
                radar_labels = radar_data.get('labels', radar_labels)
                radar_scores = radar_data.get('scores', radar_scores)
                last_cv.radar_labels = radar_labels
                last_cv.radar_scores = radar_scores
                db.session.commit()
            
            # تخصيص الاقتراحات بناءً على أداء المستخدم (Rejected Jobs Learning)
            course_suggestions = openrouter_ai.suggest_courses_for_gaps({"labels": radar_labels, "scores": radar_scores})
            if rejected_count > 2:
                course_suggestions += "<br>⚠️ <b>ملاحظة الذكاء الاصطناعي:</b> تم رصد فجوة في مهارات المقابلات، ننصح بجلسة تدريب فورية."

        except Exception as e:
            logger.error(f"Radar Generation Error: {e}")

    agent_memories = AgentMemory.query.filter_by(user_id=current_user.id).order_by(AgentMemory.created_at.desc()).limit(10).all()

    # توليد الهوية الرقمية المؤمنة 2026
    user_link = url_for('auth.verify_certificate', username=current_user.username, _external=True)
    user_qr_base64 = generate_secure_qr(user_link)

    return render_template('dashboard.html',
                           radar_labels=radar_labels,
                           radar_scores=radar_scores,
                           course_suggestions=course_suggestions,
                           user_qr=user_qr_base64,
                           agent_memories=agent_memories)

@auth_bp.route('/update_agent_settings', methods=['POST'])
@login_required
def update_agent_settings():
    """تحديث إعدادات الوكيل الذكي والواتساب مع دعم Retry و Slack"""
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
                
                # إرسال إشعار ترحيبي عبر القنوات المتاحة (WhatsApp + Slack)
                try:
                    from app.agent_worker import send_whatsapp_via_whapi
                    welcome_msg = (
                        f"مرحباً بك يا *{current_user.full_name or current_user.username}* في جوبيني! 🤖✨\n\n"
                        f"تم ربط رادارك الذكي بنجاح. سأراقب الفرص بدقة *{current_user.agent_target_score}%*.\n\n"
                        f"🇸🇩 جوبيني: نصنع مستقبلك بذكاء."
                    )
                    send_whatsapp_via_whapi(clean_wa, welcome_msg)
                    
                    # إشعار Slack للمطورين (Logging & Metrics)
                    slack_url = os.environ.get('SLACK_WEBHOOK_URL')
                    if slack_url:
                        requests.post(slack_url, json={"text": f"🚀 مستخدم جديد فعل الوكيل: {current_user.username}"})
                except Exception as e: 
                    logger.error(f"Notification Error: {e}")

        memory = AgentMemory(user_id=current_user.id, action='settings_updated',
                             feedback_notes=f"الوضع: {current_user.agent_work_type} | الهدف: {current_user.agent_target_score}%")
        db.session.add(memory)
        db.session.commit()
        flash('تم تحديث إعدادات الرادار الآلي بنجاح ✅', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في معالجة البيانات: {str(e)}', 'danger')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/test_whatsapp_agent', methods=['POST', 'GET'])
@login_required
def test_whatsapp_agent():
    """إرسال رسالة اختبار فورية للواتساب مع دعم نظام الـ Retry"""
    if not current_user.whatsapp_number:
        return jsonify({'status': 'error', 'message': 'يرجى حفظ رقم الواتساب أولاً'}), 400

    from app.agent_worker import send_whatsapp_via_whapi
    test_msg = (
        f"🔔 *إشعار اختبار الرادار الذكي* 🚀\n\n"
        f"يا {current_user.full_name or current_user.username}، مبروك! الاتصال مستقر 100%.\n\n"
        f"🤖 *حالة الوكيل:* نشط وجاهز للقنص.\n"
        f"🌍 *المجال:* {current_user.agent_query or 'عام'}"
    )
    res = send_whatsapp_via_whapi(current_user.whatsapp_number, test_msg)
    is_success = res and ('id' in str(res) or 'sent' in str(res).lower())

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if is_success: return jsonify({'status': 'success', 'message': 'وصلت رسالة الاختبار! ✅'})
        return jsonify({'status': 'error', 'message': 'فشل الاتصال - جاري المحاولة في الخلفية'}), 500

    flash('وصلت رسالة الاختبار! ✅', 'success') if is_success else flash('فشل الإرسال.', 'danger')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/scanner')
@login_required
def scanner():
    """مسار الماسح الضوئي للتحقق من الشهادات الموثوقة"""
    return render_template('scanner.html')

@auth_bp.route('/generate_interview_prep')
@login_required
def generate_interview_prep():
    """توليد جلسة محاكاة مقابلة ذكية مع دعم الـ Logging"""
    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not last_cv or not last_cv.extracted_text:
        return jsonify({'status': 'error', 'message': 'يرجى رفع سيرتك الذاتية أولاً.'}), 400
    try:
        # استخدام Chunking بسيط لضمان عدم تجاوز حدود الـ Token
        questions = openrouter_ai.generate_interview_simulation(last_cv.profession or "متخصص", last_cv.extracted_text[:4000])
        memory = AgentMemory(user_id=current_user.id, action='interview_prep', feedback_notes="توليد جلسة محاكاة ذكية")
        db.session.add(memory)
        db.session.commit()
        return jsonify({'status': 'success', 'questions': questions})
    except Exception as e:
        logger.error(f"Interview Prep AI Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/force_upgrade')
def force_upgrade():
    """تحديث قاعدة البيانات السيادي لإضافة أعمدة الأمان والذكاء لعام 2026"""
    try:
        from sqlalchemy import text
        user_cols = [
            ('whatsapp_number', 'VARCHAR(20)'),
            ('agent_enabled', 'BOOLEAN DEFAULT FALSE'),
            ('agent_active', 'BOOLEAN DEFAULT TRUE'),
            ('agent_query', 'VARCHAR(200)'),
            ('agent_work_type', "VARCHAR(20) DEFAULT 'both'"),
            ('agent_target_score', 'INTEGER DEFAULT 75'),
            ('agent_city_focus', 'VARCHAR(100)'),
            ('cover_photo', 'VARCHAR(200)'),
            ('last_evaluation', 'TEXT'),
            ('qr_code_key', 'VARCHAR(50)'),
            ('bio', 'TEXT'),
            ('headline', 'VARCHAR(150)')
        ]
        for col, col_type in user_cols:
            try:
                db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN {col} {col_type}'))
                db.session.commit()
            except Exception: db.session.rollback()

        updates = [
            'ALTER TABLE "application" ADD COLUMN IF NOT EXISTS quiz_score INTEGER',
            'ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS radar_labels JSON',
            'ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS radar_scores JSON',
            'ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS profession VARCHAR(100)',
            'ALTER TABLE "post" ADD COLUMN IF NOT EXISTS image_file VARCHAR(100)',
            'ALTER TABLE "notification" ADD COLUMN IF NOT EXISTS sender_id INTEGER'
        ]
        for sql in updates:
            try:
                db.session.execute(text(sql))
                db.session.commit()
            except Exception: db.session.rollback()

        return "<h1 style='color:green; text-align:center;'>✅ تم التحديث السيادي بنجاح 2026!</h1>"
    except Exception as e:
        return f"<h1>❌ فشل التحديث: {e}</h1>"

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """إدارة الملف الشخصي مع دعم الرفع لـ ImgBB و الـ QR الآمن"""
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.bio = request.form.get('bio')
        current_user.headline = request.form.get('headline')
        current_user.phone = request.form.get('phone')
        current_user.location_name = request.form.get('location_name')

        if 'avatar' in request.files:
            img_url = upload_to_imgbb(request.files['avatar'])
            if img_url: current_user.avatar = img_url
        if 'cover_photo' in request.files:
            cover_url = upload_to_imgbb(request.files['cover_photo'])
            if cover_url: current_user.cover_photo = cover_url
        db.session.commit()
        flash('تم تحديث بروفايلك بنجاح ✅', 'success')
        return redirect(url_for('auth.profile'))

    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    radar_data = cv.radar_scores if cv and cv.radar_scores else [0, 0, 0, 0, 0]
    
    user_link = url_for('auth.user_profile', username=current_user.username, _external=True)
    user_qr_base64 = generate_secure_qr(user_link)
    
    return render_template('profile.html', user_qr=user_qr_base64, cv=cv, radar_data=radar_data)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج. نراك قريباً!', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/user/<path:username>')
def user_profile(username):
    """عرض البروفايل العام مع مؤشر حالة الاتصال (Online Status)"""
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    is_online = (datetime.utcnow() - user.last_seen).total_seconds() < 300 if user.last_seen else False
    last_cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
    radar_data = last_cv.radar_scores if last_cv and last_cv.radar_scores else [50, 50, 50, 50, 50]

    profile_url = url_for('auth.user_profile', username=user.username, _external=True)
    user_qr_base64 = generate_secure_qr(profile_url)
    
    return render_template('user_profile.html', user=user, posts=posts, is_online=is_online, user_qr=user_qr_base64, radar_data=radar_data)

@auth_bp.route('/verify/<username>')
def verify_certificate(username):
    """بوابة التحقق الرسمية من الشهادات والموثوقية"""
    clean_name = urllib.parse.unquote(username).replace('_', ' ')
    user = User.query.filter((User.username.ilike(clean_name)) | (User.full_name.ilike(clean_name))).first()
    if not user: return render_template('errors/404.html'), 404
    
    # حساب قوة الملف رقمياً (Digital Trust Score)
    trust_score = 0
    if user.cvs: trust_score += 50
    if user.agent_enabled: trust_score += 25
    if user.whatsapp_number: trust_score += 25
    
    report = user.last_evaluation or "هذا الملف المهني معتمد وموثق من قبل أنظمة جوبيني السودان لعام 2026."
    return render_template('certificate_verify.html', user=user, evaluation=report, trust_score=trust_score)

@auth_bp.route('/smart-radar')
def smart_radar_landing():
    """صفحة الهبوط الخاصة بتكنولوجيا الرادار الآلي"""
    return render_template('agent_landing.html')
