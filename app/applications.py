# ~/jobeni-sD/app/applications.py
from flask import Blueprint, request, redirect, url_for, flash, render_template
from flask_login import login_required, current_user
from app.models import Application, Job, CV, db
from app.notifications import send_application_status_email
from app.telegram_bot import send_message
from app.openrouter_ai import openrouter_ai 

apps_bp = Blueprint('applications', __name__)

@apps_bp.route('/my-applications')
@login_required
def my_applications():
    """عرض كافة الطلبات التي قدمها الباحث عن عمل"""
    if current_user.role != 'jobseeker':
        flash("هذه الصفحة مخصصة للباحثين عن عمل فقط.", "info")
        return redirect(url_for('auth.dashboard'))

    apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).all()
    return render_template('my_applications.html', applications=apps)

@apps_bp.route('/apply-local/<int:job_id>', methods=['POST'])
@login_required
def apply_local(job_id):
    """التقديم على وظيفة داخل المنصة مع تحليل ذكي صارم"""
    job = db.session.get(Job, job_id)
    if not job:
        flash("الوظيفة غير موجودة.", "danger")
        return redirect(url_for('search.jobs_list'))

    existing = Application.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    if existing:
        flash("لقد قمت بالتقديم على هذه الوظيفة مسبقاً.", "warning")
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    # جلب آخر سيرة ذاتية للمستخدم
    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    cv_text = user_cv.extracted_text if user_cv else ""
    job_full_text = f"Title: {job.title} Description: {job.description}"

    # حساب النسبة والتفسير من الـ AI
    score, reason = openrouter_ai.get_match_score(cv_text, job_full_text)

    new_app = Application(
        user_id=current_user.id, 
        job_id=job_id, 
        status='pending',
        match_score=score,
        match_explanation=reason  # حفظ التفسير في الحقل الجديد
    )
    db.session.add(new_app)
    db.session.commit()

    # إرسال إشعار لصاحب العمل عبر تلغرام
    if job.employer and job.employer.telegram_id:
        send_message(job.employer.telegram_id, f"🔔 متقدم جديد! {current_user.username} قدم على: {job.title}\nنسبة المطابقة: {score}%")

    flash(f"✅ تم التقديم بنجاح! نسبة المطابقة الذكية: {score}%", "success")
    return redirect(url_for('applications.my_applications'))

@apps_bp.route('/auto-apply-global', methods=['POST'])
@login_required
def auto_apply_global():
    """ميزة التقديم التلقائي الذكي للوظائف العالمية"""
    job_title = request.form.get('job_title')
    job_link = request.form.get('job_link')
    company = request.form.get('company')

    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not cv:
        flash("يرجى رفع سيرتك الذاتية أولاً.", "warning")
        return redirect(url_for('cv.upload_cv'))

    prompt = f"Write a professional cover letter for {job_title} at {company}. Skills: {cv.skills}"
    cover_letter = openrouter_ai.generate_improved_text(prompt)

    return render_template('global_apply_helper.html', job_title=job_title, job_link=job_link, company=company, cover_letter=cover_letter)

@apps_bp.route('/application/<int:app_id>/update-status', methods=['POST'])
@login_required
def update_status(app_id):
    """تحديث حالة الطلب وإخطار المتقدم"""
    application = db.session.get(Application, app_id)
    if not application or application.job.employer_id != current_user.id:
        flash("غير مصرح لك.", "danger")
        return redirect(url_for('auth.dashboard'))

    new_status = request.form.get('status')
    if new_status in ['accepted', 'interview', 'rejected']:
        application.status = new_status
        db.session.commit()
        try:
            send_application_status_email(application.applicant.email, application.applicant.username, application.job.title, new_status)
        except: pass
        flash("تم تحديث الحالة ✅", "success")

    return redirect(url_for('jobs.view_candidates', job_id=application.job_id))
