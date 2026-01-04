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
        flash("لقد قمت بالتقديم على هذه الوظيفة مسبقاً.", "warning")
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not user_cv:
        flash("عذراً، يجب عليك رفع سيرتك الذاتية أولاً لتفعيل المطابقة الذكية.", "danger")
        return redirect(url_for('cv.upload_cv'))

    cv_text = user_cv.extracted_text or ""
    job_full_text = f"Title: {job.title} Description: {job.description}"
    score, reason = openrouter_ai.get_match_score(cv_text, job_full_text)

    new_app = Application(
        user_id=current_user.id,
        job_id=job_id,
        status='pending',
        match_score=score,
        match_explanation=reason
    )
    db.session.add(new_app)
    db.session.commit()

    if job.employer_ref and job.employer_ref.telegram_id:
        try:
            msg = f"🔔 متقدم جديد لـ: {job.title}\n👤 الإسم: {current_user.username}\n🎯 المطابقة: {score}%\n📝 السبب: {reason[:100]}..."
            send_message(job.employer_ref.telegram_id, msg)
        except: pass

    flash(f"✅ تم التقديم! نسبة المطابقة الذكية: {score}%", "success")
    return redirect(url_for('applications.my_applications'))

@apps_bp.route('/auto-apply-global', methods=['POST'])
@login_required
def auto_apply_global():
    """التقديم الذكي للوظائف الخارجية عبر تحليل الـ CV"""
    job_title = request.form.get('job_title')
    job_link = request.form.get('job_link')
    company = request.form.get('company')

    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not user_cv:
        flash("يرجى رفع الـ CV أولاً ليقوم الذكاء الاصطناعي بمساعدتك في التقديم.", "warning")
        return redirect(url_for('cv.upload_cv'))

    prompt = f"Analyze if candidate CV ({user_cv.profession}) matches global job ({job_title}) at ({company}). Answer briefly in Arabic."
    analysis = openrouter_ai._call_ai(prompt)

    return render_template('global_apply_helper.html',
                           job_title=job_title,
                           job_link=job_link,
                           company=company,
                           analysis=analysis)
