# ~/jobeni-sD/app/applications.py
from flask import Blueprint, request, redirect, url_for, flash, render_template
from flask_login import login_required, current_user
from app.models import Application, Job, CV, db, User
from app.notifications import send_application_status_email
from app.telegram_bot import send_message
from app.openrouter_ai import openrouter_ai

apps_bp = Blueprint('applications', __name__)

# --- أولاً: مسارات الباحث عن عمل (Job Seeker) ---

@apps_bp.route('/my-applications')
@login_required
def my_applications():
    """عرض قائمة بجميع الطلبات التي قدمها المستخدم لمتابعة حالتها"""
    if current_user.role not in ['jobseeker', 'seeker']:
        flash("هذه الصفحة مخصصة للباحثين عن عمل فقط.", "info")
        return redirect(url_for('auth.dashboard'))
    
    apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).all()
    return render_template('my_applications.html', applications=apps)

@apps_bp.route('/apply-local/<int:job_id>', methods=['POST'])
@login_required
def apply_local(job_id):
    """التقديم لوظيفة محلية مع تحليل فوري للمطابقة بالذكاء الاصطناعي"""
    job = db.session.get(Job, job_id)
    if not job:
        flash("الوظيفة غير موجودة.", "danger")
        return redirect(url_for('search.jobs_list'))

    # منع التقديم المكرر
    existing = Application.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    if existing:
        flash("لقد قمت بالتقديم مسبقاً على هذه الوظيفة.", "warning")
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    # التأكد من وجود سيرة ذاتية
    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not user_cv:
        flash("يرجى رفع الـ CV أولاً ليتمكن النظام من تحليل مطابقتك.", "danger")
        return redirect(url_for('cv.upload_cv'))

    # استدعاء الـ AI لتحليل السيرة الذاتية مقابل وصف الوظيفة
    score, reason = openrouter_ai.get_match_score(user_cv.extracted_text or "", f"{job.title} {job.description}")
    
    new_app = Application(
        user_id=current_user.id, 
        job_id=job_id, 
        status='pending', 
        match_score=score, 
        match_explanation=reason
    )
    db.session.add(new_app)
    db.session.commit()

    # إشعار صاحب العمل عبر تلغرام إذا كان مفعلاً
    if job.employer_ref and job.employer_ref.telegram_id:
        try:
            msg = f"🔔 متقدم جديد لـ: {job.title}\n👤 الاسم: {current_user.full_name}\n🎯 نسبة المطابقة: {score}%\n💡 السبب: {reason[:100]}..."
            send_message(job.employer_ref.telegram_id, msg)
        except Exception as e:
            print(f"Telegram Notify Error: {e}")

    flash(f"✅ تم التقديم بنجاح! نسبة مطابقتك هي: {score}%", "success")
    return redirect(url_for('applications.my_applications'))

# --- ثانياً: مسارات صاحب العمل (Employer - Candidate Management) ---



@apps_bp.route('/manage-candidates')
@login_required
def manage_candidates():
    """لوحة تحكم صاحب العمل لمراجعة المتقدمين وفرزهم حسب نسبة المطابقة"""
    if current_user.role != 'employer':
        flash("هذه الصفحة مخصصة لأصحاب العمل فقط.", "danger")
        return redirect(url_for('auth.dashboard'))

    # جلب التقديمات الخاصة بالوظائف التي نشرها صاحب العمل الحالي فقط باستخدام JOIN
    candidates = Application.query.join(Job).filter(Job.user_id == current_user.id).order_by(Application.applied_at.desc()).all()
    return render_template('employer_applications.html', applications=candidates)

@apps_bp.route('/status-update/<int:app_id>', methods=['POST'])
@login_required
def update_status(app_id):
    """تحديث حالة الطلب وإرسال إيميل تلقائي للمتقدم بالنتيجة"""
    app = db.session.get(Application, app_id)
    if not app or app.job.user_id != current_user.id:
        flash("غير مسموح لك بتعديل هذا الطلب.", "danger")
        return redirect(url_for('applications.manage_candidates'))

    new_status = request.form.get('status')
    if new_status in ['accepted', 'rejected', 'pending']:
        app.status = new_status
        db.session.commit()

        # إخطار الباحث عن عمل عبر البريد الإلكتروني
        try:
            send_application_status_email(app.user.email, app.job.title, new_status)
        except Exception as e:
            print(f"Email Notify Error: {e}")

        flash(f"تم تحديث حالة الطلب إلى: {new_status} وإرسال إشعار للمتقدم.", "success")

    return redirect(url_for('applications.manage_candidates'))

# --- ثالثاً: التقديم العالمي (Global Auto-Apply Helper) ---

@apps_bp.route('/auto-apply-global', methods=['POST'])
@login_required
def auto_apply_global():
    """مساعد التقديم التلقائي للوظائف العالمية عبر تحليل السيرة الذاتية"""
    job_title = request.form.get('job_title')
    job_link = request.form.get('job_link')
    company = request.form.get('company')
    
    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    
    if user_cv:
        # برومبت مخصص لتحليل الجاهزية للوظيفة العالمية
        prompt = f"Analyze my CV for the role of {job_title} at {company}. Give me 3 tips to get accepted and a short Sudanese encouragement."
        analysis = openrouter_ai.get_ai_response(prompt)
    else:
        analysis = "يا مكنة، لازم ترفع الـ CV أول عشان نقدر نحلل ليك الفرصة دي!"

    return render_template('global_apply_helper.html', 
                           job_title=job_title, 
                           job_link=job_link, 
                           company=company, 
                           analysis=analysis)
