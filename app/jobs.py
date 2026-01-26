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

# استيراد دالة إرسال رسالة المقابلة الآلية من ملف الدردشة لضمان التواصل المباشر
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
    location_query = request.args.get('location', '').strip()
    global_jobs = []

    # بناء الاستعلام المحلي (قاعدة البيانات الخاصة بنا)
    base_query = Job.query.filter_by(is_active=True)

    if query:
        base_query = base_query.filter(
            (Job.title.ilike(f'%{query}%')) |
            (Job.description.ilike(f'%{query}%')) |
            (Job.company_name.ilike(f'%{query}%'))
        )

        # جلب وظائف عالمية عبر Serper إذا طلب المستخدم البحث
        try:
            res = serper_searcher.search_jobs(f"{query} {location_query}")
            global_jobs = res.get('jobs', [])
        except Exception as e:
            print(f"Serper Search Error: {e}")

    if location_query:
        base_query = base_query.filter(Job.location.ilike(f'%{location_query}%'))

    jobs = base_query.order_by(Job.created_at.desc()).all()

    return render_template('search_results.html',
                           jobs=jobs,
                           global_jobs=global_jobs,
                           search_query=query,
                           location_query=location_query)

@jobs_bp.route('/job/<int:job_id>')
def job_detail(job_id):
    """تفاصيل الوظيفة مع التحقق من وجود اختبار تقييمي وحالة التقديم"""
    job = Job.query.get_or_404(job_id)
    application = None
    if current_user.is_authenticated:
        application = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()

    user_cvs = CV.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    has_quiz = JobQuestion.query.filter_by(job_id=job.id).first() is not None

    return render_template('job_detail.html', job=job, application=application, user_cvs=user_cvs, has_quiz=has_quiz)

# --- نظام المطابقة الذكية (Smart Match) ---

@jobs_bp.route('/smart-match')
@login_required
def smart_match_jobs():
    """البحث عن الوظائف المطابقة للسيرة الذاتية باستخدام الكلمات المفتاحية والذكاء الاصطناعي"""
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()

    if not cv:
        flash("يرجى رفع سيرة ذاتية أولاً لتفعيل البحث الذكي.", "warning")
        return redirect(url_for('cv.upload_cv'))

    all_jobs = Job.query.filter_by(is_active=True).all()
    matched_jobs = []

    # استخدام المهارات المستخرجة أو المسمى الوظيفي ككلمات مفتاحية للبحث الأولي
    keywords = cv.skills if (hasattr(cv, 'skills') and cv.skills) else (cv.profession.split() if cv.profession else [])

    for job in all_jobs:
        score = 0
        job_content = (job.title + " " + job.description).lower()
        for skill in keywords:
            if str(skill).lower() in job_content:
                score += 1
        if score > 0:
            matched_jobs.append({'job': job, 'match_count': score})

    matched_jobs = sorted(matched_jobs, key=lambda x: x['match_count'], reverse=True)
    return render_template('smart_results.html', jobs=matched_jobs, cv_profession=cv.profession)

# --- إدارة الوظائف (لأصحاب العمل) ---

@jobs_bp.route('/job/add', methods=['GET', 'POST'])
@login_required
def create_job():
    """نشر وظيفة جديدة مع إعداد الموقع الجغرافي والأسئلة التقييمية"""
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
        db.session.flush() # للحصول على id الوظيفة قبل الـ commit النهائي

        # معالجة الأسئلة التقييمية المضافة
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
    """التقديم على وظيفة مع تحليل المطابقة عبر AI وحساب درجات الاختبار التقييمي"""
    job = Job.query.get_or_404(job_id)
    questions = JobQuestion.query.filter_by(job_id=job_id).all()

    # فحص إذا كان هناك اختبار تقييمي ولم يتم إرسال الإجابات بعد
    if questions and 'answers[]' not in request.form:
        return render_template('take_quiz.html', job=job, questions=questions)

    quiz_score = 0
    if questions:
        user_answers = request.form.getlist('answers[]')
        for i, q in enumerate(questions):
            if i < len(user_answers) and user_answers[i] == q.correct_answer:
                quiz_score += q.points

    cv_id = request.form.get('cv_id')
    if not cv_id:
        flash('يرجى اختيار سيرة ذاتية للتقديم.', 'warning')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    if Application.query.filter_by(user_id=current_user.id, job_id=job_id).first():
        flash('لقد قمت بالتقديم مسبقاً على هذه الوظيفة.', 'info')
        return redirect(url_for('jobs.job_detail', job_id=job_id))

    user_cv = CV.query.get(cv_id)
    match_score = 60 # قيمة افتراضية في حال فشل الـ AI
    explanation = "تقييم ذكي بناءً على الكلمات المفتاحية المتطابقة."

    # استخدام OpenRouter AI لمقارنة السيرة بالوظيفة
    if user_cv:
        try:
            prompt = (f"قارن بين الوظيفة: ({job.title}) والسيرة الذاتية: ({user_cv.extracted_text[:700]}). "
                      f"أعطني نسبة المطابقة برقم فقط متبوعاً بتحليل سوداني قصير جداً.")
            ai_res = openrouter_ai.get_ai_response(prompt)
            # استخراج الرقم من رد الـ AI
            match_score = int(re.search(r'\d+', ai_res).group()) if re.search(r'\d+', ai_res) else 60
            explanation = ai_res
        except: pass

    new_app = Application(
        user_id=current_user.id,
        job_id=job_id,
        cv_id=cv_id,
        match_score=match_score,
        match_explanation=explanation,
        quiz_score=quiz_score,
        status='pending'
    )
    db.session.add(new_app)

    # إشعار لصاحب العمل إذا كانت المطابقة عالية جداً
    if match_score >= 80:
        add_notification(job.user_id, f"🔥 مرشح قوي لوظيفة {job.title}", f"المتقدم {current_user.username} حقق مطابقة {match_score}%", "warning")

    db.session.commit()
    flash('تم إرسال طلبك بنجاح! 🚀 تابع حالة طلبك من لوحة التحكم.', 'success')
    return redirect(url_for('auth.dashboard'))

# --- إدارة المتقدمين والتحليلات ---

@jobs_bp.route('/job/<int:job_id>/candidates')
@login_required
def view_candidates(job_id):
    """عرض قائمة المرشحين مرتبة حسب نسبة المطابقة للأفضلية"""
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id: abort(403)
    apps = Application.query.filter_by(job_id=job_id).order_by(Application.match_score.desc()).all()
    return render_template('view_candidates.html', job=job, applications=apps)

@jobs_bp.route('/job/status/<int:app_id>', methods=['POST'])
@login_required
def update_application_status(app_id):
    """تحديث حالة الطلب (قبول، رفض، تحديد مقابلة) وإخطار المتقدم"""
    application = Application.query.get_or_404(app_id)
    job = Job.query.get(application.job_id)
    if job.user_id != current_user.id: abort(403)

    new_status = request.form.get('status')
    details = request.form.get('interview_details', '')
    application.status = new_status

    if new_status == 'interview':
        add_notification(application.user_id, f"📅 موعد مقابلة: {job.title}", f"التفاصيل: {details}", "primary")
        send_automated_interview_message(sender_id=current_user.id, recipient_id=application.user_id, job_id=job.id, details=details)
    elif new_status == 'accepted':
        add_notification(application.user_id, f"✅ تم قبولك!", f"مبروك! تم قبولك في وظيفة {job.title}", "success")
    elif new_status == 'rejected':
        add_notification(application.user_id, f"❌ بخصوص طلبك لـ {job.title}", "نأسف لعدم اختيارك هذه المرة، نتمنى لك التوفيق.", "secondary")

    db.session.commit()
    flash('تم تحديث حالة المتقدم وإرسال الإشعارات.', 'success')
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/evaluate/<int:app_id>', methods=['POST'])
@login_required
def evaluate_candidate(app_id):
    """دالة لتقييم المتقدم النهائي (Decision-making)"""
    application = Application.query.get_or_404(app_id)
    job = Job.query.get(application.job_id)
    if job.user_id != current_user.id: abort(403)

    decision = request.form.get('decision')
    if decision:
        application.status = decision
        if decision == 'accepted':
            add_notification(application.user_id, f"✅ مبروك! تم قبولك نهائياً في وظيفة {job.title}", "success")
        else:
            add_notification(application.user_id, f"❌ نعتذر، لم يتم اختيارك لوظيفة {job.title}", "secondary")
        db.session.commit()
        flash('تم حفظ التقييم والقرار النهائي بنجاح.', 'success')
    
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/<int:job_id>/analytics')
@login_required
def job_analytics(job_id):
    """توليد بيانات تحليلية شاملة للوظيفة والمتقدمين للرسوم البيانية"""
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id: abort(403)
    
    apps = Application.query.filter_by(job_id=job_id).all()
    
    # توزيع حالات المتقدمين
    status_counts = {'pending': 0, 'accepted': 0, 'rejected': 0, 'interview': 0}
    # أداء الاختبار (ناجح/راسب) - نفترض أن 50% هي درجة النجاح
    passed_quiz = 0
    failed_quiz = 0
    
    total_points = sum(q.points for q in job.questions) if job.questions else 100

    for a in apps:
        if a.status in status_counts: 
            status_counts[a.status] += 1
        
        if a.quiz_score is not None:
            if a.quiz_score >= (total_points / 2):
                passed_quiz += 1
            else:
                failed_quiz += 1

    data = {
        'status_labels': ['انتظار', 'مقبول', 'مرفوض', 'مقابلة'],
        'status_values': [status_counts['pending'], status_counts['accepted'], status_counts['rejected'], status_counts['interview']],
        'quiz_counts': [passed_quiz, failed_quiz]
    }
    
    return render_template('job_analytics.html', job=job, total=len(apps), data=data)

@jobs_bp.route('/job/delete/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    """حذف الوظيفة وجميع الطلبات المرتبطة بها"""
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id: abort(403)
    db.session.delete(job)
    db.session.commit()
    flash('تم حذف الوظيفة بنجاح.', 'info')
    return redirect(url_for('auth.dashboard'))

@jobs_bp.route('/api/get_cv/<int:user_id>')
@login_required
def get_cv_api(user_id):
    """API لاستدعاء بيانات السيرة الذاتية وعرضها في المودال للمدراء"""
    cv = CV.query.filter_by(user_id=user_id).order_by(CV.created_at.desc()).first()
    if cv:
        radar_data = openrouter_ai.generate_skills_radar_data(cv.extracted_text or "")
        return jsonify({
            'parsed_text': cv.extracted_text or "لا يوجد نص مستخلص.",
            'skills': cv.skills if hasattr(cv, 'skills') else [],
            'radar': radar_data,
            'created_at': cv.created_at.strftime('%Y-%m-%d')
        })
    return jsonify({'error': 'No CV found'}), 404
