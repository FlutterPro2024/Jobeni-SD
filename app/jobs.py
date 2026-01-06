# ~/jobeni-sD/app/jobs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Job, Application, CV, User, Message, db
from app.openrouter_ai import openrouter_ai
from app.telegram_bot import notify_employer_new_app, notify_status_update, broadcast_new_job

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
        # البحث عن تقديم مسبق للمستخدم لهذه الوظيفة
        application = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    return render_template('job_detail.html', job=job, application=application)

@jobs_bp.route('/job/add', methods=['GET', 'POST'])
@login_required
def add_job():
    if current_user.role != 'employer':
        flash('هذه الصفحة لأصحاب العمل فقط.', 'danger')
        return redirect(url_for('auth.dashboard'))
        
    if request.method == 'POST':
        lat_val = request.form.get('latitude')
        lng_val = request.form.get('longitude')
        try:
            lat = float(lat_val) if lat_val and lat_val.strip() else None
            lng = float(lng_val) if lng_val and lng_val.strip() else None
        except ValueError:
            lat, lng = None, None

        title = request.form.get('title')
        company = request.form.get('company_name')
        location = request.form.get('location')
        category = request.form.get('category', 'عام')

        new_job = Job(
            title=title,
            company_name=company,
            location=location,
            description=request.form.get('description'),
            category=category,
            latitude=lat,
            longitude=lng,
            employer_id=current_user.id
        )
        db.session.add(new_job)
        db.session.commit()

        # إرسال تنبيه عبر التليجرام لكل الباحثين عن وظائف
        try:
            broadcast_new_job(title, company, location, category)
        except Exception as e:
            print(f"Broadcast Error: {e}")

        flash('تم نشر الوظيفة بنجاح وإرسال تنبيهات للمشتركين!', 'success')
        return redirect(url_for('auth.dashboard'))
    return render_template('add_job.html')

@jobs_bp.route('/job/delete/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.employer_id != current_user.id:
        abort(403)
    try:
        # حذف الرسائل والطلبات المرتبطة بالوظيفة أولاً (أمان إضافي)
        Message.query.filter_by(job_id=job.id).delete()
        Application.query.filter_by(job_id=job.id).delete()
        db.session.delete(job)
        db.session.commit()
        flash('تم حذف الوظيفة وكافة البيانات المرتبطة بها بنجاح.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء الحذف: {str(e)}', 'danger')
    return redirect(url_for('auth.dashboard'))

@jobs_bp.route('/job/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_to_job(job_id):
    # التأكد من أن الدور هو باحث عن عمل
    if current_user.role not in ['seeker', 'jobseeker']:
        flash('يجب أن يكون حسابك "باحث عن عمل" للتقديم.', 'warning')
        return redirect(url_for('auth.dashboard'))

    # استقبال الـ cv_id المختار من قائمة المستخدم
    cv_id = request.form.get('cv_id')
    job = Job.query.get_or_404(job_id)

    # التحقق من وجود الـ CV وأنه ملك للمستخدم الحالي
    user_cv = CV.query.filter_by(id=cv_id, user_id=current_user.id).first()
    if not user_cv:
        flash('يرجى اختيار سيرة ذاتية صالحة من قائمتك.', 'danger')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    # منع التكرار
    if Application.query.filter_by(user_id=current_user.id, job_id=job_id).first():
        flash('لقد قدمت مسبقاً على هذه الوظيفة.', 'info')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    # إجراء تحليل المطابقة بالذكاء الاصطناعي بناءً على الـ CV المختار
    try:
        match_score, match_explanation = openrouter_ai.get_match_score(user_cv.extracted_text, job.description)
    except:
        match_score, match_explanation = 50, "تعذر إجراء تحليل دقيق حالياً، سيتم مراجعة طلبك يدوياً."

    new_app = Application(
        user_id=current_user.id,
        job_id=job_id,
        cv_id=user_cv.id,
        match_score=int(match_score),
        match_explanation=match_explanation,
        status='pending'
    )

    db.session.add(new_app)
    db.session.commit()

    # إشعار صاحب العمل عبر تليجرام
    employer = User.query.get(job.employer_id)
    if employer and employer.telegram_id:
        try:
            notify_employer_new_app(employer.telegram_id, current_user.username, job.title, match_score)
        except: pass

    flash(f'تم التقديم بنجاح باستخدام سيرة ({user_cv.profession})! نسبة المطابقة: {match_score}%', 'success')
    return redirect(url_for('jobs.job_detail', job_id=job_id))

@jobs_bp.route('/job/status/<int:app_id>', methods=['POST'])
@login_required
def update_application_status(app_id):
    application = Application.query.get_or_404(app_id)
    job = Job.query.get(application.job_id)
    # التأكد أن من يغير الحالة هو صاحب الوظيفة
    if job.employer_id != current_user.id: 
        abort(403)

    new_status = request.form.get('status')
    if new_status in ['accepted', 'rejected', 'interview', 'pending']:
        application.status = new_status
        db.session.commit()

        # إخطار المتقدم بتغيير حالة طلبه
        applicant = User.query.get(application.user_id)
        if applicant and applicant.telegram_id:
            try:
                notify_status_update(applicant.telegram_id, job.title, new_status)
            except: pass

        flash(f'تم تحديث حالة الطلب إلى ({new_status}) وإرسال تنبيه للمتقدم.', 'success')
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/<int:job_id>/candidates')
@login_required
def view_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    if job.employer_id != current_user.id: 
        abort(403)
    # جلب الطلبات مرتبة بالأعلى مطابقة
    apps = Application.query.filter_by(job_id=job_id).order_by(Application.match_score.desc()).all()
    return render_template('view_candidates.html', job=job, applications=apps)

@jobs_bp.route('/job/generate-questions/<int:app_id>')
@login_required
def generate_interview_questions(app_id):
    application = Application.query.get_or_404(app_id)
    job = Job.query.get(application.job_id)
    if job.employer_id != current_user.id: 
        abort(403)

    user_cv = CV.query.get(application.cv_id)
    prompt = f"قم بتوليد 5 أسئلة مقابلة تقنية لمرشح لوظيفة {job.title} بناءً على خبرته في {user_cv.profession}. النص المستخرج: {user_cv.extracted_text[:800]}"

    try:
        questions = openrouter_ai.generate_improved_text(prompt)
        # تحديث الحالة تلقائياً إلى "مقابلة" عند توليد الأسئلة
        application.status = 'interview'
        db.session.commit()

        applicant = User.query.get(application.user_id)
        if applicant and applicant.telegram_id:
            try:
                notify_status_update(applicant.telegram_id, job.title, 'interview')
            except: pass

        return render_template('interview_questions.html', questions=questions, app=application, job=job)
    except:
        flash('فشل توليد الأسئلة، يرجى المحاولة لاحقاً.', 'danger')
        return redirect(url_for('jobs.view_candidates', job_id=job.id))
