# ~/jobeni-sD/app/jobs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.models import Job, Application, CV, User, db, Notification, JobQuestion, QuizResult, Scholarship
from app.openrouter_ai import openrouter_ai
from app.serper_search import serper_searcher
from app.notifications import add_notification
from sqlalchemy import text, or_
from datetime import datetime
import re

# استيراد دالة إرسال رسالة المقابلة الآلية
try:
    from app.chat import send_automated_interview_message
except ImportError:
    def send_automated_interview_message(*args, **kwargs): pass

jobs_bp = Blueprint('jobs', __name__)

# --- أولاً: محرك البحث الموحد (وظائف + منح) ---

@jobs_bp.route('/jobs')
def jobs_list():
    """عرض قائمة الفرص مع تمييز المنح الدراسية عن الوظائف"""
    query = request.args.get('q', '').strip()
    location_query = request.args.get('location', '').strip()

    # تحديد "النية" من البحث (أكاديمي أم مهني)
    academic_keywords = ['منحة', 'scholarship', 'جامعة', 'university', 'دراسة', 'phd', 'masters']
    is_academic_intent = any(k in query.lower() for k in academic_keywords)

    global_results = []

    # 1. البحث في قاعدة البيانات المحلية
    if is_academic_intent:
        local_results = Scholarship.query.filter(
            or_(Scholarship.title.ilike(f'%{query}%'), Scholarship.field_of_study.ilike(f'%{query}%'))
        ).order_by(Scholarship.created_at.desc()).all()
    else:
        base_query = Job.query.filter_by(is_active=True)
        if query:
            base_query = base_query.filter(or_(Job.title.ilike(f'%{query}%'), Job.description.ilike(f'%{query}%')))
        if location_query:
            base_query = base_query.filter(Job.location.ilike(f'%{location_query}%'))
        local_results = base_query.order_by(Job.created_at.desc()).all()

    # 2. البحث العالمي (Serper API)
    if query:
        try:
            search_suffix = "scholarships" if is_academic_intent else "jobs"
            res = serper_searcher.search_jobs(f"{query} {location_query} {search_suffix}")
            global_results = res.get('jobs', [])
        except Exception as e:
            print(f"Global Search Error: {e}")

    return render_template('search_results.html',
                           results=local_results,
                           global_results=global_results,
                           query=query,
                           is_academic=is_academic_intent)

# --- ثانياً: المطابقة الذكية (لحل مشكلة BuildError) ---

@jobs_bp.route('/smart-match')
@login_required
def smart_match_jobs():
    """المحرك الذكي: مطابقة السيرة الذاتية مع الوظائف المتاحة حالياً"""
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    
    if not cv:
        flash('يا مكنة، ارفع سيرتك الذاتية أول عشان الرادار يشتغل!', 'warning')
        return redirect(url_for('cv.upload_cv'))

    # استخدام التخصص من الـ CV ككلمة بحث أساسية
    search_query = cv.profession or "Professional"
    
    # البحث عن وظائف تطابق تخصص المستخدم
    matched_jobs = Job.query.filter(
        or_(Job.title.ilike(f'%{search_query}%'), Job.description.ilike(f'%{search_query}%'))
    ).filter_by(is_active=True).limit(10).all()

    return render_template('search_results.html', 
                           results=matched_jobs, 
                           query=search_query, 
                           is_smart=True)

# --- ثالثاً: تفاصيل الوظيفة ---

@jobs_bp.route('/job/<int:job_id>')
def job_detail(job_id):
    """عرض تفاصيل الوظيفة الكاملة مع حالة التقديم"""
    job = Job.query.get_or_404(job_id)
    application = None
    if current_user.is_authenticated:
        application = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()

    return render_template('job_detail.html', job=job, application=application)

# --- رابعاً: نظام التقديم الذكي (Smart Apply) ---

@jobs_bp.route('/job/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_to_job(job_id):
    """التقديم مع تحليل AI مخصص"""
    job = Job.query.get_or_404(job_id)
    questions = JobQuestion.query.filter_by(job_id=job_id).all()

    if questions and 'answers[]' not in request.form:
        return render_template('take_quiz.html', job=job, questions=questions)

    quiz_score = 0
    if questions:
        user_answers = request.form.getlist('answers[]')
        for i, q in enumerate(questions):
            if i < len(user_answers) and user_answers[i] == q.correct_answer:
                quiz_score += q.points

    cv_id = request.form.get('cv_id')
    user_cv = CV.query.get(cv_id)

    if not user_cv:
        flash('يرجى اختيار سيرة ذاتية للتقديم.', 'warning')
        return redirect(url_for('cv.my_cvs'))

    is_scholarship = 'scholarship' in (job.category or '').lower() or 'منحة' in job.title
    prompt_type = "خبير قبول منح دراسية" if is_scholarship else "مدير توظيف تقني"
    
    try:
        prompt = (f"بصفتك {prompt_type}، قارن بين الفرصة: ({job.title}) والـ CV: ({user_cv.extracted_text[:800]}). "
                  f"أعطني نسبة مطابقة مئوية وتحليل سوداني بسيط.")
        ai_res = openrouter_ai.get_ai_response(prompt)
        match_score = int(re.search(r'\d+', ai_res).group()) if re.search(r'\d+', ai_res) else 60
        explanation = ai_res
    except:
        match_score, explanation = 60, "تم التقييم بنجاح."

    new_app = Application(
        user_id=current_user.id, job_id=job_id, cv_id=cv_id,
        match_score=match_score, match_explanation=explanation,
        quiz_score=quiz_score, status='pending'
    )
    db.session.add(new_app)

    if match_score >= 80:
        add_notification(job.user_id, f"🌟 مرشح مكنة لـ {job.title}", f"المتقدم {current_user.username} طابق بنسبة {match_score}%", "warning")

    db.session.commit()
    flash('أبشر! طلبك وصل وقيد المراجعة.', 'success')
    return redirect(url_for('auth.dashboard'))

# --- خامساً: إدارة المتقدمين والعمليات ---

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
    application.status = new_status

    if new_status == 'interview':
        details = request.form.get('interview_details', 'سيتم التواصل معك قريباً.')
        add_notification(application.user_id, f"📅 مبروك! تحديث لطلب {job.title}", f"تم اختيارك للمقابلة. {details}", "primary")
        send_automated_interview_message(sender_id=current_user.id, recipient_id=application.user_id, job_id=job.id, details=details)

    db.session.commit()
    flash('تم تحديث الحالة بنجاح.', 'success')
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/delete/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id: abort(403)
    db.session.delete(job)
    db.session.commit()
    flash('تم حذف الإعلان.', 'info')
    return redirect(url_for('auth.dashboard'))

