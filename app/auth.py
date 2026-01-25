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
from app.models import User, Job, CV, Application, db, InterviewReport, Notification, Post, JobQuestion, QuizResult
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
        flash('تم إنشاء الحساب بنجاح! مرحباً بك في جوبني.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم الذكية: تشمل رادار المهارات، مؤشر ATS، والـ QR الهوية"""
    if current_user.role == 'employer':
        jobs = Job.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard_employer.html', jobs=jobs)

    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    radar_labels = ["تقني", "شخصي", "خبرة", "تعليم", "مشاريع"]
    radar_scores = [50, 50, 50, 50, 50]
    course_suggestions = "ارفع سيرتك الذاتية للحصول على توصيات مخصصة من مستشار AI."

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

    radar_history = Application.query.filter_by(user_id=current_user.id, status='suggested')\
        .order_by(Application.applied_at.desc()).limit(7).all()
    radar_history.reverse()

    chart_labels = [a.applied_at.strftime('%m/%d') for a in radar_history]
    chart_scores = [a.match_score for a in radar_history]

    if not chart_scores:
        chart_labels = ["البداية", "جاري الفحص"]
        chart_scores = [0, 10]

    user_link = url_for('auth.user_profile', username=current_user.username, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(user_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    user_qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    return render_template('dashboard.html',
                           cvs=current_user.cvs,
                           chart_labels=chart_labels,
                           chart_scores=chart_scores,
                           radar_labels=radar_labels,
                           radar_scores=radar_scores,
                           course_suggestions=course_suggestions,
                           user_qr=user_qr_base64)

@auth_bp.route('/update_agent_settings', methods=['POST'])
@login_required
def update_agent_settings():
    """تحديث إعدادات الرادار الذكي ورقم الواتساب مع إرسال رسالة ترحيبية"""
    try:
        current_user.agent_enabled = 'agent_enabled' in request.form
        current_user.agent_query = request.form.get('agent_query')

        whatsapp = request.form.get('whatsapp_number')
        if whatsapp:
            clean_wa = whatsapp.strip().replace('+', '').replace(' ', '').replace('-', '')

            if clean_wa != current_user.whatsapp_number:
                current_user.whatsapp_number = clean_wa
                try:
                    from app.agent_worker import send_whatsapp_via_whapi
                    welcome_msg = (
                        f"مرحباً بك يا *{current_user.full_name or current_user.username}* في جوبيني! 🤖✨\n\n"
                        f"تم تفعيل الرادار الوظيفي بنجاح. من الآن وصاعداً، حتصلك هنا أفضل الوظائف العالمية والمحلية المناسبة لمهاراتك.\n\n"
                        f"🇸🇩 صنع بكل فخر في السودان"
                    )
                    send_whatsapp_via_whapi(clean_wa, welcome_msg)
                except Exception as e:
                    print(f"WhatsApp Welcome Error: {e}")

        db.session.commit()
        flash('تم تحديث إعدادات الرادار والواتساب بنجاح ✅', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في الحفظ: {str(e)}', 'danger')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/test_whatsapp_agent', methods=['POST', 'GET'])
@login_required
def test_whatsapp_agent():
    """إرسال رسالة اختبار فورية للتأكد من ربط الواتساب بـ Whapi"""
    if not current_user.whatsapp_number:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'يرجى حفظ رقم الواتساب أولاً'}), 400
        flash('يرجى حفظ رقم الواتساب أولاً', 'warning')
        return redirect(url_for('auth.dashboard'))

    from app.agent_worker import send_whatsapp_via_whapi
    test_msg = (
        f"🔔 *إشعار اختبار الرادار* 🚀\n\n"
        f"يا {current_user.full_name or current_user.username}، مبروك! السيستم اتصل بجوالك بنجاح.\n\n"
        f"🤖 *حالة الأيجنت:* جاهز للعمل\n"
        f"من الآن وصاعداً، لو لقينا أي وظيفة تطابق خبرتك، حنرسل ليك التفاصيل هنا طوالي. 🇸🇩"
    )

    res = send_whatsapp_via_whapi(current_user.whatsapp_number, test_msg)
    
    # التحقق من نجاح الإرسال حسب رد Whapi
    is_success = res and ('id' in str(res) or 'sent' in str(res).lower())
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if is_success:
            return jsonify({'status': 'success', 'message': 'تم إرسال رسالة الاختبار بنجاح ✅'})
        return jsonify({'status': 'error', 'message': f'فشل الإرسال: {res}'}), 500
    
    if is_success:
        flash('وصلت رسالة الاختبار لواتسابك! ✅', 'success')
    else:
        flash(f'فشل الإرسال. تأكد من التوكن في Vercel. الرد: {res}', 'danger')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/force_upgrade')
def force_upgrade():
    """تحديث قاعدة البيانات لإضافة الأعمدة الجديدة"""
    try:
        from sqlalchemy import text
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(20)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_query VARCHAR(200)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS cover_photo VARCHAR(200)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_evaluation TEXT'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS qr_code_key VARCHAR(50)'))
        db.session.execute(text('ALTER TABLE "application" ADD COLUMN IF NOT EXISTS quiz_score INTEGER'))
        db.session.execute(text('ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS radar_labels JSON'))
        db.session.execute(text('ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS radar_scores JSON'))
        db.session.execute(text('ALTER TABLE "cv" ADD COLUMN IF NOT EXISTS course_recommendations TEXT'))
        db.session.commit()
        return "<h1>✅ تم تحديث النظام بنجاح!</h1>"
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
        flash('تم تحديث الملف الشخصي بنجاح', 'success')
        return redirect(url_for('auth.profile'))

    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    applications = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).all()
    radar_data = cv.radar_scores if cv and cv.radar_scores else [0, 0, 0, 0, 0]

    user_link = url_for('auth.user_profile', username=current_user.username, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(user_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    user_qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    return render_template('profile.html', user_qr=user_qr_base64, cv=cv, applications=applications, radar_data=radar_data)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/user/<path:username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    is_online = False
    if user.last_seen:
        is_online = (datetime.utcnow() - user.last_seen).total_seconds() < 300
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

@auth_bp.route('/scanner')
@login_required
def scanner():
    return render_template('scanner.html')

@auth_bp.route('/verify/<username>')
def verify_certificate(username):
    clean_name = urllib.parse.unquote(username).replace('_', ' ')
    user = User.query.filter((User.username.ilike(clean_name)) | (User.full_name.ilike(clean_name))).first()
    if not user:
        return render_template('errors/404.html'), 404
    report = user.last_evaluation or "Expert Technical Assessment Verified."
    return render_template('certificate_verify.html', user=user, evaluation=report)

@auth_bp.route('/smart-radar')
def smart_radar_landing():
    """عرض صفحة الهبوط الخاصة بالرادار الذكي"""
    return render_template('agent_landing.html')
