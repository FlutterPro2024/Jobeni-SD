# ~/jobeni-sD/app/jobs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.models import Job, Application, CV, User, db, Notification
from app.openrouter_ai import openrouter_ai
from app.serper_search import serper_searcher
from app.notifications import send_new_application_email, send_application_status_email, add_notification
from sqlalchemy import text
import re

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/jobs')
def jobs_list():
    query = request.args.get('q', '').strip()
    global_jobs = []

    if query:
        # استخدام فلتر محدد للأعمدة
        jobs = Job.query.with_entities(Job.id, Job.title, Job.company_name, Job.location, Job.description, Job.category, Job.salary, Job.job_type, Job.created_at).filter(
            (Job.title.ilike(f'%{query}%')) |
            (Job.description.ilike(f'%{query}%')) |
            (Job.company_name.ilike(f'%{query}%'))
        ).filter_by(is_active=True).all()

        try:
            res = serper_searcher.search_jobs(query)
            global_jobs = res.get('jobs', [])
        except Exception as e:
            print(f"Serper Error in jobs_list: {e}")
    else:
        # استعلام خام لضمان الاستقرار في العرض العام
        q = text("SELECT id, title, company_name, location, description, category, salary, job_type, created_at FROM job WHERE is_active = true ORDER BY created_at DESC")
        jobs = db.session.execute(q).fetchall()

    return render_template('jobs_list.html', jobs=jobs, global_jobs=global_jobs, query=query)

@jobs_bp.route('/job/<int:job_id>')
def job_detail(job_id):
    # جلب الوظيفة بشكل صريح
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
        # استخدام العمود الجديد user_id
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

        flash('تم نشر الوظيفة بنجاح!', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('add_job.html')

# التعديل هنا لضمان قبول حسابك (باحث عن عمل) بمرونة كاملة
@jobs_bp.route('/job/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_to_job(job_id):
    # تحويل الرتبة لنص صغير لضمان المطابقة مهما كانت حالة الأحرف
    user_role = str(current_user.role).lower().strip()

    # قبول كلاً من 'jobseeker' و 'seeker' كباحث عن عمل
    if user_role not in ['jobseeker', 'seeker']:
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

# --- الدالة الجديدة المضافة لدعم أيقونة العين وعرض السي في ---
@jobs_bp.route('/api/get_cv/<int:user_id>')
@login_required
def get_cv_api(user_id):
    # جلب آخر سيرة ذاتية مرفوعة للمستخدم
    cv = CV.query.filter_by(user_id=user_id).order_by(CV.created_at.desc()).first()
    if cv:
        return jsonify({
            'parsed_text': cv.extracted_text or "لا يوجد نص مستخلص للسيرة الذاتية.",
            'skills': cv.skills if hasattr(cv, 'skills') else [],
            'created_at': cv.created_at.strftime('%Y-%m-%d')
        })
    return jsonify({'error': 'No CV found'}), 404
