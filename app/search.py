# ~/jobeni-sD/app/search.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Job, CV, Application, InterviewSession, db
from app.openrouter_ai import openrouter_ai
from app.serper_search import serper_searcher
from app.telegram_bot import send_message

search_bp = Blueprint('search', __name__)

@search_bp.route('/jobs/search')
def jobs_list():
    """البحث الموحد عن الوظائف محلياً وعالمياً"""
    q = request.args.get('q', '').strip()
    loc = request.args.get('location', '').strip()

    # البحث المحلي في قاعدة البيانات
    try:
        query = Job.query.filter_by(is_active=True)
        if q:
            query = query.filter(Job.title.ilike(f'%{q}%') | Job.description.ilike(f'%{q}%'))
        if loc:
            query = query.filter(Job.location.ilike(f'%{loc}%'))
        local_jobs = query.all()
    except:
        local_jobs = []

    # البحث العالمي عبر Serper API
    global_jobs = []
    if q:
        try:
            full_query = f"{q} {loc}".strip()
            results = serper_searcher.search_jobs(full_query)
            global_jobs = results.get('jobs', []) if results else []
        except Exception as e:
            print(f"Middleware Global Search Error: {e}")
            global_jobs = []

    return render_template('search_results.html',
                           jobs=local_jobs,
                           global_jobs=global_jobs,
                           search_query=q,
                           location_query=loc)

@search_bp.route('/skill-analysis')
@login_required
def skill_analysis():
    """المستشار الذكي: تحليل المهارات بناءً على الـ CV"""
    # تم تصحيح order_at إلى order_by هنا
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not cv:
        flash('يرجى رفع سيرتك الذاتية أولاً لتفعيل المستشار الذكي.', 'info')
        return redirect(url_for('cv.upload_cv'))

    skills_list = cv.skills if isinstance(cv.skills, list) else []
    skills_data = []
    for s in skills_list:
        skills_data.append({
            "name": s,
            "url": f"https://www.youtube.com/results?search_query=learn+{s.replace(' ', '+')}",
            "prep_url": url_for('search.interview_prep', skill=s)
        })

    return render_template('skill_analysis.html',
                           profession=cv.profession or "متخصص",
                           skills_data=skills_data,
                           cv_score=cv.score or 0,
                           cv_id=cv.id)

@search_bp.route('/interview-prep/<skill>')
@login_required
def interview_prep(skill):
    """توليد أسئلة مقابلة ذكية بناءً على التخصص"""
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    profession = cv.profession if cv else "متخصص"

    prompt = (f"أنت خبير توظيف تقني. قدم 5 أسئلة مقابلة ذكية مع إجاباتها النموذجية "
              f"لمتخصص في ({profession}) حول مهارة ({skill}) بالعربية.")

    content = openrouter_ai._call_ai(prompt, temperature=0.7)

    if content:
        try:
            new_session = InterviewSession(
                user_id=current_user.id,
                skill_name=skill,
                questions_content=content
            )
            db.session.add(new_session)
            db.session.commit()

            if current_user.telegram_id:
                msg = f"🧠 <b>جلسة تدريب جاهزة!</b>\n\nلقد تم توليد أسئلة مقابلة لمهارة: <b>{skill}</b>"
                send_message(current_user.telegram_id, msg)
        except:
            db.session.rollback()

        return render_template('interview_prep_view.html', skill=skill, content=content)

    flash('المحرك مشغول حالياً، جرب مهارة أخرى.', 'warning')
    return redirect(url_for('search.skill_analysis'))

@search_bp.route('/session/delete/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    session = InterviewSession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        abort(403)
    db.session.delete(session)
    db.session.commit()
    return redirect(url_for('auth.dashboard'))

def calculate_match_score(cv_text, job_desc):
    if not cv_text or not job_desc:
        return 0
    try:
        score, explanation = openrouter_ai.get_match_score(cv_text, job_desc)
        return score
    except:
        return 50
