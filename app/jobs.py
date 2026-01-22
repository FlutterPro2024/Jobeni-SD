# ~/jobeni-sD/app/jobs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.models import Job, Application, CV, User, db, Notification, JobQuestion, QuizResult
from app.openrouter_ai import openrouter_ai
from app.serper_search import serper_searcher
from app.notifications import send_new_application_email, send_application_status_email, add_notification
from sqlalchemy import text
from datetime import datetime
import re

# استيراد دالة إرسال رسالة المقابلة الآلية من ملف الدردشة
try:
    from app.chat import send_automated_interview_message
except ImportError:
    def send_automated_interview_message(*args, **kwargs): pass

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/jobs')
def jobs_list():
    query = request.args.get('q', '').strip()
    global_jobs = []

    if query:
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
        q = text("SELECT id, title, company_name, location, description, category, salary, job_type, created_at FROM job WHERE is_active = true ORDER BY created_at DESC")
        jobs = db.session.execute(q).fetchall()

    return render_template('jobs_list.html', jobs=jobs, global_jobs=global_jobs, query=query)

@jobs_bp.route('/job/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    application = None
    if current_user.is_authenticated:
        application = Application.query.filter_by(user_id=current_user.id, job_id=job.id).first()

    user_cvs = CV.query.filter_by(user_id=current_user.id).all() if current_user.is_authenticated else []
    has_quiz = JobQuestion.query.filter_by(job_id=job.id).first() is not None

    return render_template('job_detail.html', job=job, application=application, user_cvs=user_cvs, has_quiz=has_quiz)

@jobs_bp.route('/job/add', methods=['GET', 'POST'])
@login_required
def create_job():
    if current_user.role != 'employer':
        flash('عذراً، هذه الصفحة مخصصة لأصحاب العمل فقط.', 'danger')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        new_job = Job(
            title=request.form.get('title'),
            company_name=request.form.get('company_name'),
            location=request.form.get('location'),
            description=request.form.get('description'),
            salary=request.form.get('salary'),
            job_type=request.form.get('job_type'),
            user_id=current_user.id
        )
        db.session.add(new_job)
        db.session.flush()

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
                        option_a=q_as[i],
                        option_b=q_bs[i],
                        option_c=q_cs[i] if i < len(q_cs) else None,
                        option_d=q_ds[i] if i < len(q_ds) else None,
                        correct_answer=q_corrects[i],
                        points=int(q_points[i]) if q_points[i] else 10
                    )
                    db.session.add(new_q)

        db.session.commit()
        flash('تم نشر الوظيفة مع الاختبار التقييمي بنجاح!', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('create_job.html')

@jobs_bp.route('/job/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_to_job(job_id):
    user_role = str(current_user.role).lower().strip()
    if user_role not in ['jobseeker', 'seeker']:
        flash('يجب أن يكون نوع حسابك "باحث عن عمل" لتتمكن من التقديم.', 'warning')
        return redirect(url_for('auth.dashboard'))

    job = Job.query.get_or_404(job_id)
    questions = JobQuestion.query.filter_by(job_id=job_id).all()

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
        quiz_score=quiz_score,
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
    """تحديث حالة الطلب مع نظام إشعارات ورسائل مقابلة آلية"""
    application = Application.query.get_or_404(app_id)
    job = Job.query.get(application.job_id)

    if job.user_id != current_user.id:
        abort(403)

    new_status = request.form.get('status')
    interview_details = request.form.get('interview_details', '').strip()

    application.status = new_status

    if new_status == 'interview':
        msg = f"🚀 خبر رائع! تم اختيارك لمقابلة لوظيفة {job.title}."
        if interview_details:
            msg += f" تفاصيل الموعد: {interview_details}"

        add_notification(application.user_id, msg, 'info')

        send_automated_interview_message(
            sender_id=current_user.id,
            recipient_id=application.user_id,
            job_id=job.id,
            details=interview_details
        )

        flash('تم إرسال دعوة المقابلة وتفاصيل الموعد وبدء دردشة مع المتقدم.', 'success')

    elif new_status == 'accepted':
        add_notification(application.user_id, f"✅ مبروك! تم قبولك مبدئياً لوظيفة {job.title}.", 'success')
        flash('تم تحديث الحالة إلى مقبول بنجاح.', 'success')

    elif new_status == 'rejected':
        add_notification(application.user_id, f"نعتذر، لم يتم اختيارك لوظيفة {job.title} هذه المرة. نتمنى لك التوفيق.", 'secondary')
        flash('تم تحديث الحالة إلى مرفوض.', 'info')

    db.session.commit()
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/evaluate/<int:app_id>', methods=['POST'])
@login_required
def evaluate_candidate(app_id):
    """تقييم المتقدم بعد المقابلة وإصدار القرار النهائي"""
    application = Application.query.get_or_404(app_id)
    job = Job.query.get(application.job_id)

    if job.user_id != current_user.id:
        abort(403)

    technical_score = int(request.form.get('technical_score', 0))
    soft_skills_score = int(request.form.get('soft_skills_score', 0))
    final_notes = request.form.get('final_notes', '')
    decision = request.form.get('decision')

    avg_score = (technical_score + soft_skills_score) / 2
    application.match_explanation += f"\n\n--- تقييم المقابلة ---\nالدرجة: {avg_score}/5\nالملاحظات: {final_notes}"
    application.status = decision

    if decision == 'accepted':
        msg = f"🎊 مبروك! بعد تقييم المقابلة، تم قبولك نهائياً لوظيفة {job.title}. سيتواصل معك قسم الموارد البشرية."
        category = 'success'
    else:
        msg = f"نعتذر، لم يتم اختيارك لوظيفة {job.title} بعد مرحلة المقابلة. نتمنى لك التوفيق في فرص قادمة."
        category = 'secondary'

    add_notification(application.user_id, msg, category)
    db.session.commit()

    flash('تم تسجيل التقييم وإرسال القرار النهائي للمتقدم.', 'success')
    return redirect(url_for('jobs.view_candidates', job_id=job.id))

@jobs_bp.route('/job/<int:job_id>/analytics')
@login_required
def job_analytics(job_id):
    """لوحة تحكم التحليلات والرسوم البيانية للوظيفة"""
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        abort(403)

    total_apps = Application.query.filter_by(job_id=job_id).count()
    accepted = Application.query.filter_by(job_id=job_id, status='accepted').count()
    rejected = Application.query.filter_by(job_id=job_id, status='rejected').count()
    pending = Application.query.filter_by(job_id=job_id, status='pending').count()
    interviewing = Application.query.filter_by(job_id=job_id, status='interview').count()

    questions = JobQuestion.query.filter_by(job_id=job_id).all()
    max_score = sum(q.points for q in questions) if questions else 100
    pass_mark = max_score * 0.5

    apps_with_quiz = Application.query.filter(
        Application.job_id == job_id,
        Application.quiz_score.isnot(None)
    ).all()

    passed_quiz = len([a for a in apps_with_quiz if a.quiz_score >= pass_mark])
    failed_quiz = len(apps_with_quiz) - passed_quiz

    # تم تغيير التسمية هنا لتجنب التعارض مع دوال القواميس الأصلية
    chart_data = {
        "labels": ["ناجح", "راسب"],
        "quiz_counts": [passed_quiz, failed_quiz],
        "status_labels": ["مقبول", "مرفوض", "مقابلة", "قيد الانتظار"],
        "status_values": [accepted, rejected, interviewing, pending]
    }

    return render_template('job_analytics.html', job=job, data=chart_data, total=total_apps)

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

@jobs_bp.route('/api/get_cv/<int:user_id>')
@login_required
def get_cv_api(user_id):
    cv = CV.query.filter_by(user_id=user_id).order_by(CV.created_at.desc()).first()
    if cv:
        return jsonify({
            'parsed_text': cv.extracted_text or "لا يوجد نص مستخلص.",
            'skills': cv.skills if hasattr(cv, 'skills') else [],
            'created_at': cv.created_at.strftime('%Y-%m-%d')
        })
    return jsonify({'error': 'No CV found'}), 404
