# ~/jobeni-sD/app/applications.py
from flask import Blueprint, request, redirect, url_for, flash, render_template
from flask_login import login_required, current_user
from app.models import Application, Job, CV, db, User
from app.notifications import send_application_status_email
from app.telegram_bot import send_message
from app.openrouter_ai import openrouter_ai

apps_bp = Blueprint('applications', __name__)

# --- جزء الباحث عن عمل (موجود مسبقاً) ---
@apps_bp.route('/my-applications')
@login_required
def my_applications():
    if current_user.role not in ['jobseeker', 'seeker']:
        flash("هذه الصفحة مخصصة للباحثين عن عمل فقط.", "info")
        return redirect(url_for('auth.dashboard'))
    apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).all()
    return render_template('my_applications.html', applications=apps)

@apps_bp.route('/apply-local/<int:job_id>', methods=['POST'])
@login_required
def apply_local(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        flash("الوظيفة غير موجودة.", "danger")
        return redirect(url_for('search.jobs_list'))

    existing = Application.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    if existing:
        flash("لقد قمت بالتقديم مسبقاً.", "warning")
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not user_cv:
        flash("يرجى رفع الـ CV أولاً.", "danger")
        return redirect(url_for('cv.upload_cv'))

    score, reason = openrouter_ai.get_match_score(user_cv.extracted_text or "", f"{job.title} {job.description}")
    new_app = Application(user_id=current_user.id, job_id=job_id, status='pending', match_score=score, match_explanation=reason)
    db.session.add(new_app)
    db.session.commit()

    if job.employer_ref and job.employer_ref.telegram_id:
        try:
            send_message(job.employer_ref.telegram_id, f"🔔 متقدم جديد لـ: {job.title}\n🎯 المطابقة: {score}%")
        except: pass

    flash(f"✅ تم التقديم! المطابقة: {score}%", "success")
    return redirect(url_for('applications.my_applications'))

# --- الجزء الجديد: إدارة المرشحين (لصاحب العمل) ---

@apps_bp.route('/manage-candidates')
@login_required
def manage_candidates():
    if current_user.role != 'employer':
        flash("هذه الصفحة مخصصة لأصحاب العمل فقط.", "danger")
        return redirect(url_for('auth.dashboard'))
    
    # جلب التقديمات الخاصة بالوظائف التي نشرها صاحب العمل الحالي فقط
    candidates = Application.query.join(Job).filter(Job.employer_id == current_user.id).order_by(Application.applied_at.desc()).all()
    
    return render_template('employer_applications.html', applications=candidates)

@apps_bp.route('/status-update/<int:app_id>', methods=['POST'])
@login_required
def update_status(app_id):
    app = db.session.get(Application, app_id)
    if not app or app.job.employer_id != current_user.id:
        flash("غير مسموح لك بتعديل هذا الطلب.", "danger")
        return redirect(url_for('applications.manage_candidates'))

    new_status = request.form.get('status')
    if new_status in ['accepted', 'rejected', 'pending']:
        app.status = new_status
        db.session.commit()
        
        # إشعار الباحث عن عمل (إيميل أو داخل المنصة)
        try:
            send_application_status_email(app.user.email, app.job.title, new_status)
        except: pass
        
        flash(f"تم تحديث حالة الطلب إلى: {new_status}", "success")
    
    return redirect(url_for('applications.manage_candidates'))

@apps_bp.route('/auto-apply-global', methods=['POST'])
@login_required
def auto_apply_global():
    job_title, job_link, company = request.form.get('job_title'), request.form.get('job_link'), request.form.get('company')
    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    analysis = openrouter_ai._call_ai(f"Analyze CV for {job_title} at {company}") if user_cv else "يرجى رفع CV"
    return render_template('global_apply_helper.html', job_title=job_title, job_link=job_link, company=company, analysis=analysis)
