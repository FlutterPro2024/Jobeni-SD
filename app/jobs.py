# ~/jobeni-sD/app/jobs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Job, Application, CV, User, db, Notification
from app.openrouter_ai import openrouter_ai
from app.serper_search import serper_searcher
from app.notifications import send_new_application_email, send_application_status_email, add_notification
import re

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/jobs')
def jobs_list():
    query = request.args.get('q', '').strip()
    global_jobs = []
    
    if query:
        # 1. البحث المحلي
        jobs = Job.query.filter(
            (Job.title.ilike(f'%{query}%')) |
            (Job.description.ilike(f'%{query}%')) |
            (Job.company_name.ilike(f'%{query}%'))
        ).filter_by(is_active=True).all()
        
        # 2. البحث العالمي التلقائي (الرادار)
        try:
            res = serper_searcher.search_jobs(query)
            global_jobs = res.get('jobs', [])
        except Exception as e:
            print(f"Serper Error in jobs_list: {e}")
    else:
        jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).all()

    return render_template('jobs_list.html', jobs=jobs, global_jobs=global_jobs, query=query)

@jobs_bp.route('/job/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    application = None
    if current_user.is_authenticated:
        application = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()

    user_cvs = CV.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    return render_template('job_detail.html', job=job, application=application, user_cvs=user_cvs)

@jobs_bp.route('/job/add', methods=['GET', 'POST'])
@login_required
def add_job():
    if current_user.role != 'employer':
        flash('عذراً، هذه الصفحة مخصصة لأصحاب العمل فقط.', 'danger')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        new_job = Job(
            title=request.form.get('title'),
            company_name=request.form.get('company_name'),
            location=request.form.get('location'),
            latitude=request.form.get('latitude'),
            longitude=request.form.get('longitude'),
            description=request.form.get('description'),
            salary=request.form.get('salary'),
            job_type=request.form.get('job_type'),
            user_id=current_user.id
        )
        db.session.add(new_job)
        db.session.commit()

        add_notification(
            current_user.id,
            "تم نشر الوظيفة بنجاح 🚀",
            f"وظيفتك الجديدة '{new_job.title}' متاحة الآن للباحثين عن عمل.",
            "success",
            url_for('jobs.job_detail', job_id=new_job.id)
        )

        flash('تم نشر الوظيفة بنجاح!', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('add_job.html')

@jobs_bp.route('/job/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_to_job(job_id):
    if current_user.role != 'jobseeker':
        flash('يجب أن يكون نوع حسابك "باحث عن عمل" لتتمكن من التقديم.', 'warning')
        return redirect(url_for('auth.dashboard'))

    cv_id = request.form.get('cv_id')
    if not cv_id:
        flash('يرجى اختيار سيرة ذاتية للتقديم.', 'warning')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    job = Job.query.get_or_404(job_id)

    if Application.query.filter_by(user_id=current_user.id, job_id=job_id).first():
        flash('لقد قمت بالتقديم على هذه الوظيفة مسبقاً.', 'info')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    user_cv = CV.query.filter_by(id=cv_id, user_id=current_user.id).first()

    match_score = 50 
    explanation = "تم التقييم بناءً على المهارات العامة."

    if user_cv and user_cv.extracted_text:
        try:
            prompt = (
                f"حلل بدقة المطابقة بين الوظيفة: ({job.title} - {job.description[:500]}) "
                f"والسيرة الذاتية: ({user_cv.extracted_text[:1000]}). "
                f"أعطني النسبة المئوية للمطابقة كأول كلمة في ردك (مثال: 85%) ثم اشرح السبب باختصار."
            )
            ai_res = openrouter_ai.get_ai_response(prompt)
            score_match = re.search(r'\d+', ai_res)
            if score_match:
                match_score = int(score_match.group())
            explanation = ai_res
        except Exception as e:
            print(f"AI Match Error: {e}")

    new_app = Application(
        user_id=current_user.id,
        job_id=job_id,
        match_score=match_score,
        match_explanation=explanation,
        status='pending'
    )
    db.session.add(new_app)
    db.session.commit()

    employer = User.query.get(job.user_id)
    if employer:
        add_notification(
            employer.id,
            "متقدم جديد 👤",
            f"هناك طلب جديد لوظيفة '{job.title}' بنسبة مطابقة {match_score}%",
            "primary",
            url_for('jobs.view_candidates', job_id=job.id)
        )
        try:
            send_new_application_email(employer, job, current_user, match_score)
        except: pass

    flash(f'تم التقديم بنجاح! نسبة المطابقة الذكية: {match_score}%', 'success')
    return redirect(url_for('auth.dashboard'))

@jobs_bp.route('/job/<int:job_id>/candidates')
@login_required
def view_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        abort(403)

    apps = Application.query.filter_by(job_id=job_id).order_by(Application.match_score.desc()).all()
    return render_template('view_candidates.html', job=job, applications=apps)

@jobs_bp.route('/job/status/<int:app_id>', methods=['POST'])
@login_required
def update_application_status(app_id):
    application = Application.query.get_or_404(app_id)
    job = Job.query.get(application.job_id)

    if job.user_id != current_user.id:
        abort(403)

    new_status = request.form.get('status')
    application.status = new_status
    db.session.commit()

    applicant = User.query.get(application.user_id)
    if applicant:
        status_ar = "مقبول مبدئياً ✅" if new_status == 'accepted' else "نعتذر منك ❌"
        add_notification(
            applicant.id,
            "تحديث حالة الطلب",
            f"تم تحديث حالة طلبك لوظيفة '{job.title}' إلى: {status_ar}",
            "info",
            url_for('auth.dashboard')
        )
        try:
            send_application_status_email(applicant, job.title, new_status)
        except: pass

    flash(f'تم تحديث الحالة بنجاح.', 'success')
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/delete/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        abort(403)

    db.session.delete(job)
    db.session.commit()

    flash('تم حذف الوظيفة نهائياً.', 'info')
    return redirect(url_for('auth.dashboard'))
