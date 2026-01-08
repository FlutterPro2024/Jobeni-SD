# ~/jobeni-sD/app/jobs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Job, Application, CV, User, Message, db
from app.openrouter_ai import openrouter_ai
from app.notifications import send_new_application_email, send_application_status_email, add_notification
from app.telegram_bot import send_message # تم تعديل الاستدعاء لضمان العمل

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/jobs')
def jobs_list():
    query = request.args.get('q', '')
    if query:
        jobs = Job.query.filter(Job.title.contains(query) | Job.description.contains(query)).all()
    else:
        jobs = Job.query.filter_by(is_active=True).all()
    return render_template('jobs_list.html', jobs=jobs)

@jobs_bp.route('/job/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    application = None
    if current_user.is_authenticated:
        application = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    return render_template('job_detail.html', job=job, application=application)

@jobs_bp.route('/job/add', methods=['GET', 'POST'])
@login_required
def add_job():
    if current_user.role != 'employer':
        flash('هذه الصفحة لأصحاب العمل فقط.', 'danger')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        title = request.form.get('title')
        company = request.form.get('company_name')
        location = request.form.get('location')
        
        new_job = Job(
            title=title,
            company_name=company,
            location=location,
            description=request.form.get('description'),
            salary=request.form.get('salary'),
            job_type=request.form.get('job_type'),
            user_id=current_user.id # ربط الوظيفة بصاحب العمل
        )
        db.session.add(new_job)
        db.session.commit()

        # إشعار الجرس لصاحب العمل
        add_notification(current_user.id, "تم نشر الوظيفة 🚀", f"وظيفتك '{title}' متاحة الآن للتقديم.", "success")

        flash('تم نشر الوظيفة بنجاح!', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('add_job.html')

@jobs_bp.route('/job/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_to_job(job_id):
    if current_user.role != 'jobseeker':
        flash('يجب أن يكون حسابك "باحث عن عمل" للتقديم.', 'warning')
        return redirect(url_for('auth.dashboard'))

    cv_id = request.form.get('cv_id')
    job = Job.query.get_or_404(job_id)

    if Application.query.filter_by(user_id=current_user.id, job_id=job_id).first():
        flash('لقد قدمت مسبقاً على هذه الوظيفة.', 'info')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    user_cv = CV.query.filter_by(id=cv_id, user_id=current_user.id).first()
    
    # تحليل المطابقة بالذكاء الاصطناعي
    match_score = 50 # افتراضي
    if user_cv:
        try:
            prompt = f"قارن بين السيرة الذاتية: {user_cv.extracted_text[:1000]} ووصف الوظيفة: {job.description[:1000]}. أعطني نسبة مطابقة كرقم فقط من 100."
            response = openrouter_ai.get_ai_response(prompt)
            match_score = int(''.join(filter(str.isdigit, response)))
        except:
            pass

    new_app = Application(
        user_id=current_user.id,
        job_id=job_id,
        match_score=match_score,
        status='pending'
    )
    db.session.add(new_app)
    db.session.commit()

    # إشعارات لصاحب العمل
    employer = User.query.get(job.user_id)
    if employer:
        send_new_application_email(employer, job, current_user, match_score)

    add_notification(current_user.id, "تم التقديم بنجاح ✅", f"قدمت على '{job.title}' بنسبة مطابقة {match_score}%", "info")

    flash(f'تم التقديم بنجاح! نسبة مطابقتك الذكية: {match_score}%', 'success')
    return redirect(url_for('jobs.job_detail', job_id=job_id))

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

    # إخطار المتقدم
    applicant = User.query.get(application.user_id)
    if applicant:
        send_application_status_email(applicant, job.title, new_status)

    flash(f'تم تحديث الحالة إلى {new_status} وإشعار المتقدم.', 'success')
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/<int:job_id>/candidates')
@login_required
def view_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        abort(403)
    apps = Application.query.filter_by(job_id=job_id).order_by(Application.match_score.desc()).all()
    return render_template('view_candidates.html', job=job, applications=apps)
