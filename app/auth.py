# ~/jobeni-sD/app/auth.py
import os
import re
import base64
import io
import qrcode
import requests
import urllib.parse
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Job, CV, Application, db, InterviewReport, Notification, Post, JobQuestion, QuizResult, AgentMemory
from app.openrouter_ai import openrouter_ai

auth_bp = Blueprint('auth', __name__)

def upload_to_imgbb(file):
    """دالة مساعدة لرفع الصور لـ ImgBB واسترجاع الرابط المباشر لضمان استقرار الصور"""
    api_key = os.environ.get('IMGBB_API_KEY')
    if not api_key:
        print("⚠️ IMGBB_API_KEY is missing in environment variables")
        return None
    url = "https://api.imgbb.com/1/upload"
    try:
        files = {"image": file.read()}
        params = {"key": api_key}
        response = requests.post(url, params=params, files=files)
        data = response.json()
        if data.get('status') == 200:
            return data['data']['url']
    except Exception as e:
        print(f"❌ ImgBB Upload Error: {e}")
        return None

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
    """لوحة التحكم الذكية: تشمل رادار المهارات، مؤشر ATS، والذاكرة الذكية للأيجنت"""
    if current_user.role == 'employer':
        jobs = Job.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard_employer.html', jobs=jobs)

    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    radar_labels = ["تقني", "تواصل", "خبرة", "قيادة", "إبداع"]
    radar_scores = [50, 50, 50, 50, 50]
    course_suggestions = "ارفع سيرتك الذاتية للحصول على توصيات مخصصة من مستشار AI عالمي."

    if last_cv and last_cv.extracted_text:
        try:
            if last_cv.radar_labels and last_cv.radar_scores:
                radar_labels = last_cv.radar_labels
                radar_scores = last_cv.radar_scores
            else:
                radar_data = openrouter_ai.generate_skills_radar_data(last_cv.extracted_text)
                radar_labels = radar_data.get('labels', radar_labels)
                radar_scores = radar_data.get('scores', radar_scores)
                last_cv.radar_labels = radar_labels
                last_cv.radar_scores = radar_scores
                db.session.commit()
            course_suggestions = openrouter_ai.suggest_courses_for_gaps({"labels": radar_labels, "scores": radar_scores})
        except Exception as e:
            print(f"Radar Generation Error: {e}")

    agent_memories = AgentMemory.query.filter_by(user_id=current_user.id).order_by(AgentMemory.created_at.desc()).limit(10).all()

    # توليد QR الهوية الشخصية المعتمدة
    user_link = url_for('auth.verify_certificate', username=current_user.username, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(user_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    user_qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    return render_template('dashboard.html',
                           radar_labels=radar_labels,
                           radar_scores=radar_scores,
                           course_suggestions=course_suggestions,
                           user_qr=user_qr_base64,
                           agent_memories=agent_memories)

@auth_bp.route('/update_agent_settings', methods=['POST'])
@login_required
def update_agent_settings():
    """تحديث إعدادات الوكيل الذكي (النوع، النسبة، الموقع) والواتساب"""
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
                    welcome_msg = (
                        f"مرحباً بك يا *{current_user.full_name or current_user.username}* في جوبيني! 🤖✨\n\n"
                        f"تم ربط رادارك الذكي بالواتساب بنجاح. سأقوم بمراقبة الفرص التي تطابق شغفك بنسبة *{current_user.agent_target_score}%*.\n\n"
                        f"🇸🇩 جوبيني: نصنع مستقبلك بذكاء."
                    )
                    send_whatsapp_via_whapi(clean_wa, welcome_msg)
                except Exception: pass
        
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
    """إرسال رسالة اختبار فورية للتأكد من ربط الواتساب بـ Whapi"""
    if not current_user.whatsapp_number:
        return jsonify({'status': 'error', 'message': 'يرجى حفظ رقم الواتساب أولاً'}), 400

    from app.agent_worker import send_whatsapp_via_whapi
    test_msg = (
        f"🔔 *إشعار اختبار الرادار الذكي* 🚀\n\n"
        f"يا {current_user.full_name or current_user.username}، مبروك! الاتصال بين جوبيني وجوالك مستقر 100%.\n\n"
        f"🤖 *حالة الوكيل:* نشط وجاهز للقنص.\n"
        f"🌍 *المجال المستهدف:* {current_user.agent_query or 'غير محدد'}"
    )
    res = send_whatsapp_via_whapi(current_user.whatsapp_number, test_msg)
    is_success = res and ('id' in str(res) or 'sent' in str(res).lower())

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if is_success:
            return jsonify({'status': 'success', 'message': 'وصلت رسالة الاختبار! ✅'})
        return jsonify({'status': 'error', 'message': 'فشل الاتصال بـ API الواتساب'}), 500

    if is_success: flash('وصلت رسالة الاختبار! ✅', 'success')
    else: flash('فشل الإرسال. تأكد من إعدادات API.', 'danger')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/generate_interview_prep')
@login_required
def generate_interview_prep():
    """توليد أسئلة مقابلة ذكية بناءً على ملف المستخدم"""
    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not last_cv or not last_cv.extracted_text:
        return jsonify({'status': 'error', 'message': 'يرجى رفع سيرتك الذاتية أولاً.'}), 400

    try:
        questions = openrouter_ai.generate_interview_simulation(last_cv.profession or "متخصص", last_cv.extracted_text)
        memory = AgentMemory(user_id=current_user.id, action='interview_prep', feedback_notes="توليد جلسة محاكاة")
        db.session.add(memory)
        db.session.commit()
        return jsonify({'status': 'success', 'questions': questions})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/force_upgrade')
def force_upgrade():
    """تحديث قاعدة البيانات لإضافة الأعمدة السيادية 2026 المطابقة لنسخة السيرفر العالمي"""
    try:
        from sqlalchemy import text
        # قائمة الأعمدة الجديدة المطلوبة لمواكبة نسخة Vercel
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

        # تحديث جداول التطبيقات والـ CV والمجتمع
        updates = [
            'ALTER TABLE "application" ADD COLUMN IF NOT EXISTS quiz_score INTEGER',
            'ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS radar_labels JSON',
            'ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS radar_scores JSON',
            'ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS course_recommendations TEXT',
            'ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS profession VARCHAR(100)',
            'ALTER TABLE "post" ADD COLUMN IF NOT EXISTS image_file VARCHAR(100)',
            'ALTER TABLE "post" ADD COLUMN IF NOT EXISTS video_file VARCHAR(100)',
            'ALTER TABLE "notification" ADD COLUMN IF NOT EXISTS sender_id INTEGER',
            'ALTER TABLE "notification" ADD COLUMN IF NOT EXISTS post_id INTEGER'
        ]
        
        for sql in updates:
            try:
                db.session.execute(text(sql))
                db.session.commit()
            except Exception: db.session.rollback()

        return """<div style='direction:rtl;text-align:center;padding:50px;font-family:sans-serif;'>
                  <h1 style='color:green;'>✅ تم التحديث بنجاح!</h1>
                  <p>قاعدة البيانات الآن متوافقة تماماً مع نسخة Vercel 2026.</p>
                  <a href='/dashboard'>الذهاب للوحة التحكم</a></div>"""
    except Exception as e:
        db.session.rollback()
        return f"<h1>❌ فشل التحديث</h1><p>{str(e)}</p>"

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.bio = request.form.get('bio')
        current_user.headline = request.form.get('headline')
        current_user.phone = request.form.get('phone')
        current_user.location_name = request.form.get('location_name')
        
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '':
                img_url = upload_to_imgbb(file)
                if img_url: current_user.avatar = img_url

        if 'cover_photo' in request.files:
            file = request.files['cover_photo']
            if file and file.filename != '':
                cover_url = upload_to_imgbb(file)
                if cover_url: current_user.cover_photo = cover_url

        db.session.commit()
        flash('تم تحديث بروفايلك بنجاح ✅', 'success')
        return redirect(url_for('auth.profile'))

    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    radar_data = cv.radar_scores if cv and cv.radar_scores else [0, 0, 0, 0, 0]
    
    user_link = url_for('auth.user_profile', username=current_user.username, _external=True)
    qr = qrcode.QRCode(version=1, box_size=5, border=1)
    qr.add_data(user_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    user_qr_base64 = base64.b64encode(buffered.getvalue()).decode()
                                                                
    return render_template('profile.html', user_qr=user_qr_base64, cv=cv, radar_data=radar_data)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج. نراك قريباً!', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/user/<path:username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    is_online = (datetime.utcnow() - user.last_seen).total_seconds() < 300 if user.last_seen else False
    last_cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
    radar_data = last_cv.radar_scores if last_cv and last_cv.radar_scores else [50, 50, 50, 50, 50]
    
    profile_url = url_for('auth.user_profile', username=user.username, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(profile_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    user_qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return render_template('user_profile.html', user=user, posts=posts, is_online=is_online, user_qr=user_qr_base64, radar_data=radar_data)

@auth_bp.route('/verify/<username>')
def verify_certificate(username):
    clean_name = urllib.parse.unquote(username).replace('_', ' ')
    user = User.query.filter((User.username.ilike(clean_name)) | (User.full_name.ilike(clean_name))).first()
    if not user:
        return render_template('errors/404.html'), 404
    report = user.last_evaluation or "هذا الملف المهني معتمد وموثق من قبل أنظمة جوبيني السودان لعام 2026."
    return render_template('certificate_verify.html', user=user, evaluation=report)

@auth_bp.route('/smart-radar')
def smart_radar_landing():
    return render_template('agent_landing.html')
