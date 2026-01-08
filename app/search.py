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
    q, loc = request.args.get('q', '').strip(), request.args.get('location', '').strip()
    query = Job.query.filter_by(is_active=True)
    if q: query = query.filter(Job.title.ilike(f'%{q}%') | Job.description.ilike(f'%{q}%'))
    if loc: query = query.filter(Job.location.ilike(f'%{loc}%'))
    local_jobs = query.all()

    global_jobs = serper_searcher.search_jobs(f"{q} {loc}") if q else {"jobs": []}
    return render_template('search_results.html', jobs=local_jobs, global_jobs=global_jobs.get('jobs', []), search_query=q, location_query=loc)

@search_bp.route('/skill-analysis')
@login_required
def skill_analysis():
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not cv:
        flash('يرجى رفع الـ CV أولاً.', 'info')
        return redirect(url_for('cv.upload_cv'))
    skills_list = cv.skills if isinstance(cv.skills, list) else []
    skills_data = [{"name": s, "url": f"https://www.youtube.com/results?search_query=learn+{s}", "prep_url": url_for('search.interview_prep', skill=s)} for s in skills_list]
    return render_template('skill_analysis.html', profession=cv.profession or "متخصص", skills_data=skills_data, cv_score=cv.score or 0, cv_id=cv.id)

@search_bp.route('/interview-prep/<skill>')
@login_required
def interview_prep(skill):
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    prompt = f"قدم 5 أسئلة مقابلة لمهارة ({skill}) لمتخصص ({cv.profession if cv else 'تقني'}) بالعربية."
    content = openrouter_ai._call_ai(prompt)
    if content:
        try:
            db.session.add(InterviewSession(user_id=current_user.id, skill_name=skill, questions_content=content))
            db.session.commit()
            if current_user.telegram_id: send_message(current_user.telegram_id, f"🧠 جلسة تحضير {skill} جاهزة!")
        except: db.session.rollback()
        return render_template('interview_prep_view.html', skill=skill, content=content)
    return redirect(url_for('search.skill_analysis'))

@search_bp.route('/session/delete/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    session = InterviewSession.query.get_or_404(session_id)
    if session.user_id != current_user.id: abort(403)
    db.session.delete(session)
    db.session.commit()
    return redirect(url_for('auth.dashboard'))
