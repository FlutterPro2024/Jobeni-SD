# ~/jobeni-sD/app/jobs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.models import Job, Application, CV, User, db, Notification, JobQuestion, QuizResult
from app.openrouter_ai import openrouter_ai
from app.serper_search import serper_searcher
from app.notifications import add_notification
from sqlalchemy import text
from datetime import datetime
import re

# استيراد دالة إرسال رسالة المقابلة الآلية من ملف الدردشة
try:
    from app.chat import send_automated_interview_message
except ImportError:
    def send_automated_interview_message(*args, **kwargs): pass

jobs_bp = Blueprint('jobs', __name__)

# --- المسارات الأساسية للوظائف ---

@jobs_bp.route('/jobs')
def jobs_list():
    """عرض قائمة الوظائف مع دعم البحث المحلي والبحث العالمي عبر Serper"""
    query = request.args.get('q', '').strip()
    global_jobs = []

    if query:
        jobs = Job.query.with_entities(
            Job.id, Job.title, Job.company_name, Job.location,
            Job.description, Job.category, Job.salary, Job.job_type, Job.created_at
        ).filter(
            (Job.title.ilike(f'%{query}%')) |
            (Job.description.ilike(f'%{query}%')) |
            (Job.company_name.ilike(f'%{query}%'))
        ).filter_by(is_active=True).all()

        try:
            res = serper_searcher.search_jobs(query)
            global_jobs = res.get('jobs', [])
        except Exception as e:
            print(f"Serper Error: {e}")
    else:
        q = text("SELECT id, title, company_name, location, description, category, salary, job_type, created_at FROM job WHERE is_active = true ORDER BY created_at DESC")
        jobs = db.session.execute(q).fetchall()

    return render_template('jobs_list.html', jobs=jobs, global_jobs=global_jobs, query=query)

@jobs_bp.route('/job/<int:job_id>')
def job_detail(job_id):
    """تفاصيل الوظيفة مع التحقق من وجود اختبار تقييمي"""
    job = Job.query.get_or_404(job_id)
    application = None
    if current_user.is_authenticated:
        application = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()

    user_cvs = CV.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    has_quiz = JobQuestion.query.filter_by(job_id=job.id).first() is not None

    return render_template('job_detail.html', job=job, application=application, user_cvs=user_cvs, has_quiz=has_quiz)

# --- نظام المطابقة الذكية (Smart Match) الجديد ---

@jobs_bp.route('/smart-match')
@login_required
def smart_match_jobs():
    """البحث عن الوظائف المطابقة للسيرة الذاتية المحسنة بالذكاء الاصطناعي"""
    # جلب السيرة الذاتية المحسنة (التي تحتوي على مهارات وكلمات مفتاحية أقوى)
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    
    if not cv:
        flash("يرجى رفع سيرة ذاتية أولاً لتفعيل البحث الذكي.", "warning")
        return redirect(url_for('cv.upload_cv'))

    # جلب الوظائف النشطة
    all_jobs = Job.query.filter_by(is_active=True).all()
    matched_jobs = []

    # مهارات المستخدم المستخرجة من الـ AI
    user_skills = cv.skills if cv.skills else []
    
    # تحويل النص المحسن إلى كلمات مفتاحية بسيطة إذا لم تتوفر مهارات
    keywords = user_skills if user_skills else cv.profession.split()

    for job in all_jobs:
        score = 0
        job_content = (job.title + " " + job.description).lower()
        
        for skill in keywords:
            if skill.lower() in job_content:
                score += 1
        
        if score > 0:
            matched_jobs.append({
                'job': job,
                'match_count': score
            })

    # ترتيب النتائج حسب جودة التطابق
    matched_jobs = sorted(matched_jobs, key=lambda x: x['match_count'], reverse=True)

    return render_template('smart_results.html', jobs=matched_jobs, cv_profession=cv.profession)

# --- إدارة الوظائف (لأصحاب العمل) ---

@jobs_bp.route('/job/add', methods=['GET', 'POST'])
@login_required
def create_job():
    """نشر وظيفة جديدة مع إعداد الموقع والأسئلة التقييمية"""
    if current_user.role != 'employer':
        flash('عذراً، هذه الصفحة مخصصة لأصحاب العمل فقط.', 'danger')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')

        new_job = Job(
            title=request.form.get('title'),
            company_name=request.form.get('company_name') or current_user.full_name or current_user.username,
            location=request.form.get('location'),
            latitude=float(lat) if lat and lat.strip() else None,
            longitude=float(lng) if lng and lng.strip() else None,
            description=request.form.get('description'),
            salary=request.form.get('salary'),
            job_type=request.form.get('job_type'),
            user_id=current_user.id
        )
        db.session.add(new_job)
        db.session.flush()

        # معالجة الأسئلة
        q_texts = request.form.getlist('q_text[]')
        if q_texts:
            q_as = request.form.getlist('q_a[]')
            q_bs = request.form.getlist('q_b[]')
            q_cs = request.form.getlist('q_c[]')
            q_ds = request.form.getlist('q_d[]')
            q_corrects = request.form.getlist('q_correct[]')
            q_points = request.form.getlist('q_points[]')

            for i in range(len(q_texts)):
                if q_texts[i].strip():
                    new_q = JobQuestion(
                        job_id=new_job.id,
                        question_text=q_texts[i],
                        option_a=q_as[i] if i < len(q_as) else "",
                        option_b=q_bs[i] if i < len(q_bs) else "",
                        option_c=q_cs[i] if i < len(q_cs) else None,
                        option_d=q_ds[i] if i < len(q_ds) else None,
                        correct_answer=q_corrects[i] if i < len(q_corrects) else "A",
                        points=int(q_points[i]) if i < len(q_points) and q_points[i] else 10
                    )
                    db.session.add(new_q)

        db.session.commit()
        flash('تم نشر الوظيفة بنجاح! 🚀', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('create_job.html')

# --- التقديم على الوظائف ---

@jobs_bp.route('/job/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_to_job(job_id):
    """التقديم على وظيفة مع تحليل المطابقة عبر AI وحساب درجات الاختبار"""
    user_role = str(current_user.role).lower().strip()
    if user_role not in ['jobseeker', 'seeker']:
        flash('يجب أن يكون نوع حسابك "باحث عن عمل".', 'warning')
        return redirect(url_for('auth.dashboard'))

    job = Job.query.get_or_404(job_id)
    questions = JobQuestion.query.filter_by(job_id=job_id).all()

    # فحص إذا كان هناك اختبار تقييمي
    if questions and 'answers[]' not in request.form:
        return render_template('take_quiz.html', job=job, questions=questions)

    quiz_score = None
    if questions:
        user_answers = request.form.getlist('answers[]')
        total_score = 0
        for i, q in enumerate(questions):
            if i < len(user_answers) and user_answers[i] == q.correct_answer:
                total_score += q.points
        quiz_score = total_score

    cv_id = request.form.get('cv_id')
    if not cv_id:
        flash('يرجى اختيار سيرة ذاتية للتقديم.', 'warning')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    if Application.query.filter_by(user_id=current_user.id, job_id=job_id).first():
        flash('لقد قمت بالتقديم مسبقاً.', 'info')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    user_cv = CV.query.filter_by(id=cv_id, user_id=current_user.id).first()
    match_score = 50
    explanation = "تم التقييم بناءً على المهارات العامة."

    if user_cv:
        # استخدام النص المحسن للتقييم إذا وجد، وإلا استخدام النص الأصلي
        source_text = user_cv.optimized_text if (hasattr(user_cv, 'optimized_text') and user_cv.optimized_text) else user_cv.extracted_text
        try:
            prompt = (
                f"حلل المطابقة بين الوظيفة: ({job.title} - {job.description[:400]}) "
                f"والسيرة الذاتية: ({source_text[:800]}). "
                f"أعطني نسبة مئوية (رقم فقط) متبوعاً بشرح قصير جداً باللهجة السودانية."
            )
            ai_res = openrouter_ai.get_ai_response(prompt)
            score_match = re.search(r'\d+', ai_res)
            if score_match: match_score = int(score_match.group())
            explanation = ai_res
        except Exception as e:
            print(f"AI Match Error: {e}")

    new_app = Application(
        user_id=current_user.id,
        job_id=job_id,
        match_score=match_score,
        match_explanation=explanation,
        quiz_score=quiz_score,
        status='pending'
    )
    db.session.add(new_app)

    if match_score >= 85:
        employer_msg = f"🚀 مرشح لقطة! {current_user.full_name or current_user.username} قدم لوظيفة {job.title} بنسبة {match_score}%."
        add_notification(job.user_id, employer_msg, 'warning')

    db.session.commit()
    flash(f'تم التقديم بنجاح! نسبة المطابقة الذكية: {match_score}%', 'success')
    return redirect(url_for('auth.dashboard'))

# --- إدارة المتقدمين والتحليلات ---

@jobs_bp.route('/job/<int:job_id>/candidates')
@login_required
def view_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id: abort(403)
    apps = Application.query.filter_by(job_id=job_id).order_by(Application.match_score.desc()).all()
    return render_template('view_candidates.html', job=job, applications=apps)

@jobs_bp.route('/job/status/<int:app_id>', methods=['POST'])
@login_required
def update_application_status(app_id):
    application = Application.query.get_or_404(app_id)
    job = Job.query.get(application.job_id)
    if job.user_id != current_user.id: abort(403)

    new_status = request.form.get('status')
    interview_details = request.form.get('interview_details', '').strip()
    application.status = new_status

    if new_status == 'interview':
        msg = f"🚀 تم اختيارك لمقابلة لوظيفة {job.title}."
        if interview_details: msg += f" التفاصيل: {interview_details}"
        add_notification(application.user_id, msg, 'info')
        send_automated_interview_message(sender_id=current_user.id, recipient_id=application.user_id, job_id=job.id, details=interview_details)
    elif new_status == 'accepted':
        add_notification(application.user_id, f"✅ مبروك! تم قبولك نهائياً في وظيفة {job.title}.", 'success')
    elif new_status == 'rejected':
        add_notification(application.user_id, f"نعتذر، لم يتم اختيارك لوظيفة {job.title}.", 'secondary')

    db.session.commit()
    flash(f'تم تحديث حالة المتقدم إلى {new_status}.', 'success')
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/<int:job_id>/analytics')
@login_required
def job_analytics(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id: abort(403)

    apps = Application.query.filter_by(job_id=job_id).all()
    questions = JobQuestion.query.filter_by(job_id=job_id).all()
    total_q_points = sum(q.points for q in questions) if questions else 100
    pass_mark = total_q_points * 0.5

    pass_count = len([a for a in apps if a.quiz_score is not None and a.quiz_score >= pass_mark])
    fail_count = len([a for a in apps if a.quiz_score is not None and a.quiz_score < pass_mark])

    status_counts = {'pending': 0, 'accepted': 0, 'rejected': 0, 'interview': 0}
    for a in apps:
        if a.status in status_counts: status_counts[a.status] += 1

    analytics_data = {
        'quiz_counts': [pass_count, fail_count],
        'labels': ['ناجح', 'راسب'],
        'status_labels': ['قيد الانتظار', 'مقبول', 'مرفوض', 'مقابلة'],
        'status_values': [status_counts['pending'], status_counts['accepted'], status_counts['rejected'], status_counts['interview']]
    }
    return render_template('job_analytics.html', job=job, total=len(apps), data=analytics_data)

@jobs_bp.route('/job/delete/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id: abort(403)
    db.session.delete(job)
    db.session.commit()
    flash('تم حذف الوظيفة.', 'info')
    return redirect(url_for('auth.dashboard'))

@jobs_bp.route('/api/get_cv/<int:user_id>')
@login_required
def get_cv_api(user_id):
    """API لجلب بيانات الرادار والـ CV للمتقدمين"""
    cv = CV.query.filter_by(user_id=user_id).order_by(CV.created_at.desc()).first()
    if cv:
        radar_data = openrouter_ai.generate_skills_radar_data(cv.extracted_text or "")
        return jsonify({
            'parsed_text': cv.extracted_text or "لا يوجد نص.",
            'skills': cv.skills if hasattr(cv, 'skills') else [],
            'radar': radar_data,
            'created_at': cv.created_at.strftime('%Y-%m-%d')
        })
    return jsonify({'error': 'No CV found'}), 404
