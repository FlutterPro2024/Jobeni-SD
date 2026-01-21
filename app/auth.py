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
from app.models import User, Job, CV, Application, db, InterviewReport, Notification, Post

auth_bp = Blueprint('auth', __name__)

def upload_to_imgbb(file):
    """دالة مساعدة لرفع الصور لـ ImgBB واسترجاع الرابط المباشر"""
    api_key = os.environ.get('IMGBB_API_KEY')
    if not api_key:
        return None

    url = "https://api.imgbb.com/1/upload"
    try:
        # قراءة محتوى الملف وتحويله لإرساله
        files = {"image": file.read()}
        params = {"key": api_key}
        response = requests.post(url, params=params, files=files)
        data = response.json()
        if data['status'] == 200:
            return data['data']['url']
    except Exception as e:
        print(f"ImgBB Upload Error: {e}")
    return None

@auth_bp.before_app_request
def update_last_seen():
    """تحديث آخر ظهور مع معالجة أخطاء قاعدة البيانات المكسورة"""
    try:
        if current_user.is_authenticated:
            current_user.last_seen = datetime.utcnow()
            db.session.commit()
    except Exception:
        db.session.rollback()

@auth_bp.route('/')
def index():
    try:
        latest_jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).limit(6).all()
    except Exception as e:
        db.session.rollback()
        latest_jobs = []
    return render_template('index.html', jobs=latest_jobs)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('auth.dashboard'))
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
    if current_user.is_authenticated: return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').lower().strip()
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash('البريد أو المستخدم مسجل مسبقاً.', 'warning')
            return redirect(url_for('auth.register'))
        new_user = User(
            username=username, email=email,
            full_name=request.form.get('full_name', '').strip(),
            password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256'),
            role=request.form.get('role', 'jobseeker'),
            avatar=f"https://ui-avatars.com/api/?name={username}&background=random&color=fff",
            last_seen=datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.commit()
        flash('تم إنشاء الحساب بنجاح!', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم - عرض بيانات الرادار والمؤشر المهني والـ QR الشخصي"""
    if current_user.role == 'employer':
        jobs = Job.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard_employer.html', jobs=jobs)

    recent_apps = Application.query.filter_by(user_id=current_user.id)\
        .order_by(Application.applied_at.desc()).limit(10).all()

    radar_data = Application.query.filter_by(user_id=current_user.id, status='suggested')\
        .order_by(Application.applied_at.desc()).limit(7).all()
    radar_data.reverse()

    chart_labels = [a.applied_at.strftime('%m/%d') for a in radar_data]
    chart_scores = [a.match_score for a in radar_data]

    if not chart_scores:
        chart_labels = ["البداية", "جاري الفحص"]
        chart_scores = [0, 10]

    # توليد QR Code للـ Dashboard
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
                           recent_applications=recent_apps,
                           chart_labels=chart_labels,
                           chart_scores=chart_scores,
                           user_qr=user_qr_base64)

@auth_bp.route('/user/<path:username>')
@login_required
def user_profile(username):
    """عرض الملف الشخصي العام لأي مستخدم مع الـ QR Code الخاص به"""
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()

    is_online = False
    if user.last_seen:
        is_online = (datetime.utcnow() - user.last_seen).total_seconds() < 300
                                                    
    # --- ميزة جديدة: توليد QR Code للمستخدم الذي يتم عرضه حالياً ---
    profile_url = url_for('auth.user_profile', username=user.username, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(profile_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    user_qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    return render_template('user_profile.html',
                           user=user,
                           posts=posts,
                           is_online=is_online,
                           user_qr=user_qr_base64)

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """تعديل الملف الشخصي ورفع الصور السحابية"""
    if request.method == 'POST':
        # تحديث الحقول النصية
        current_user.full_name = request.form.get('full_name')
        current_user.bio = request.form.get('bio')
        current_user.headline = request.form.get('headline')
        current_user.phone = request.form.get('phone')
        current_user.location_name = request.form.get('location_name')

        # معالجة رفع الصور السحابية عبر ImgBB
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '':
                img_url = upload_to_imgbb(file)
                if img_url:
                    current_user.avatar = img_url

        if 'cover_photo' in request.files:
            file = request.files['cover_photo']
            if file and file.filename != '':
                cover_url = upload_to_imgbb(file)
                if cover_url:
                    current_user.cover_photo = cover_url

        db.session.commit()
        flash('تم تحديث الملف الشخصي والبيانات بنجاح', 'success')
        return redirect(url_for('auth.profile'))

    # توليد الـ QR Code للملف الشخصي الخاص
    user_link = url_for('auth.user_profile', username=current_user.username, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(user_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    user_qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    return render_template('profile.html', user_qr=user_qr_base64)

@auth_bp.route('/update_agent_settings', methods=['POST'])
@login_required
def update_agent_settings():
    current_user.agent_enabled = 'agent_enabled' in request.form
    current_user.agent_query = request.form.get('agent_query')
    db.session.commit()
    flash('تم تحديث إعدادات المستشار الذكي بنجاح', 'success')
    return redirect(url_for('auth.dashboard'))

@auth_bp.route('/scanner')
@login_required
def scanner():
    """فتح صفحة الماسح الضوئي للكاميرا"""
    return render_template('scanner.html')

@auth_bp.route('/force_upgrade')
def force_upgrade():
    """رابط طوارئ لإضافة العمود المفقود مباشرة لتجاوز خطأ الـ Favicon والـ Login"""
    try:
        from sqlalchemy import text
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS cover_photo VARCHAR(200)'))
        db.session.commit()
        return "✅ تم إضافة عمود cover_photo بنجاح! يمكنك الآن دخول البروفايل."
    except Exception as e:
        db.session.rollback()
        return f"❌ خطأ في التحديث اليدوي: {str(e)}"

@auth_bp.route('/deploy/upgrade')
def deploy_upgrade():
    """رابط تحديث قاعدة البيانات عبر Flask-Migrate"""
    try:
        from flask_migrate import upgrade
        upgrade()
        return "✅ تم تحديث قاعدة البيانات (Database Migrated) بنجاح!"
    except Exception as e:
        return f"❌ فشل التحديث: {str(e)}"

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/verify/<username>')
def verify_certificate(username):
    """رابط توثيق الشهادات - متاح للجميع"""
    # فك تشفير الاسم وتبديل الشرطات بمسافات
    clean_name = urllib.parse.unquote(username).replace('_', ' ')

    # البحث في قاعدة البيانات
    user = User.query.filter(
        (User.username.ilike(clean_name)) |
        (User.full_name.ilike(clean_name))
    ).first()

    if not user:
        # إذا لم يوجد مستخدم، نعرض رسالة واضحة
        return "<h1>404 - سجل التوثيق غير موجود</h1><p>تأكد من صحة الرابط أو مسح الكود مرة أخرى.</p>", 404

    return render_template('certificate_verify.html', user=user)


#################

@auth_bp.route('/fix-ma-report')
def fix_ma_report():
    user = User.query.filter_by(username='Ma').first()
    if user:
        user.last_evaluation = """
Expert Technical Assessment:
The candidate demonstrates advanced proficiency in AWS Serverless Architectures.
Key Strengths:
- Deep understanding of Event-Driven design using Lambda & DynamoDB.
- Strong knowledge of Cloud Security (IAM, Cognito) and Session Management.
- Excellent ability to balance performance vs cost (Scalability & TTL strategies).
Conclusion: Highly Recommended for Cloud Solution Architect roles.
        """
        db.session.commit()
        return "✅ التقرير تم تحديثه بنجاح لـ Ma!"
    return "❌ المستخدم غير موجود"

