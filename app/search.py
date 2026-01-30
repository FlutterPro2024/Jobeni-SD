# ~/jobeni-sD/app/search.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.models import Job, CV, Application, InterviewSession, User, db, Scholarship
from app.openrouter_ai import openrouter_ai
from app.serper_search import serper_searcher
from app.telegram_bot import send_message
from sqlalchemy import or_
from datetime import datetime, timedelta

search_bp = Blueprint('search', __name__)

# --- أولاً: كود البحث عن المستخدمين (نظام استكشاف الزملاء) ---
@search_bp.route('/users')
@login_required
def search_users():
    """بحث متقدم عن المستخدمين والزملاء مع دعم حالة الاتصال"""
    query = request.args.get('q', '').strip()
    users = []

    if query:
        search_filter = or_(
            User.username.ilike(f'%{query}%'),
            User.full_name.ilike(f'%{query}%'),
            User.headline.ilike(f'%{query}%'),
            User.bio.ilike(f'%{query}%')
        )
        users = User.query.filter(search_filter).filter(User.id != current_user.id).limit(20).all()
    else:
        users = User.query.filter(User.id != current_user.id).order_by(db.func.random()).limit(12).all()

    return render_template('search_users.html', users=users, query=query, utcnow=datetime.utcnow())

# --- ثانياً: كود البحث عن الوظائف والمنح (محرك هجين ذكي) ---
@search_bp.route('/jobs/search')
def jobs_list():
    """محرك بحث ذكي يكتشف تلقائياً إذا كان البحث عن وظيفة أو منحة"""
    q = request.args.get('q', '').strip()
    loc = request.args.get('location', '').strip()
    
    # تحديد نوع البحث بناءً على الكلمات المفتاحية أو دور المستخدم
    is_scholarship_query = any(word in q.lower() for word in ['منحة', 'scholarship', 'study', 'university', 'phd', 'masters'])
    if current_user.is_authenticated and current_user.role == 'scholarship_seeker':
        is_scholarship_query = True

    local_results = []
    global_results = []

    if is_scholarship_query:
        # 1. البحث في قاعدة بيانات المنح المحلية (إذا توفرت)
        local_results = Scholarship.query.filter(
            or_(Scholarship.title.ilike(f'%{q}%'), Scholarship.field_of_study.ilike(f'%{q}%'))
        ).limit(10).all()
        
        # 2. البحث العالمي عن المنح عبر Serper
        if q:
            try:
                # نمرر الاستعلام لـ Serper ليقوم بالترجمة والبحث الأكاديمي
                res = serper_searcher.search_jobs(f"{q} scholarship")
                global_results = res.get('jobs', [])
            except: pass
            
        return render_template('search_results.html', 
                               scholarships=local_results, 
                               global_scholarships=global_results, 
                               search_query=q, 
                               mode='scholarship')

    else:
        # 1. البحث المحلي في الوظائف
        query = Job.query.filter_by(is_active=True)
        if q:
            query = query.filter(or_(Job.title.ilike(f'%{q}%'), Job.description.ilike(f'%{q}%')))
        if loc:
            query = query.filter(Job.location.ilike(f'%{loc}%'))
        local_results = query.order_by(Job.created_at.desc()).all()

        # 2. البحث العالمي في الوظائف
        if q:
            search_term = f"{q} remote jobs" if not loc else f"{q} jobs in {loc}"
            try:
                results = serper_searcher.search_jobs(search_term)
                global_results = results.get('jobs', [])
            except: pass

        return render_template('search_results.html',
                               jobs=local_results,
                               global_jobs=global_results,
                               search_query=q,
                               location_query=loc,
                               mode='job')

# --- ثالثاً: تحليل المهارات والتحضير الذكي (مهني/أكاديمي) ---
@search_bp.route('/skill-analysis')
@login_required
def skill_analysis():
    """تحليل متقدم لنقاط القوة والضعف (يدعم المسار الأكاديمي والمهني)"""
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not cv:
        flash('يجب رفع سيرتك الذاتية أولاً لتفعيل نظام التحليل الذكي.', 'info')
        return redirect(url_for('cv.upload_cv'))

    skills_list = cv.skills if isinstance(cv.skills, list) else []
    skills_data = [
        {
            "name": s,
            "url": f"https://www.youtube.com/results?search_query=learn+{s}+course",
            "prep_url": url_for('search.interview_prep', skill=s)
        } for s in skills_list
    ]

    # تخصيص تصنيفات الرادار بناءً على نوع المستخدم
    if current_user.role == 'scholarship_seeker':
        radar_labels = ["البحث العلمي", "اللغات", "المعدل GPA", "العمل التطوعي", "المشاريع"]
    else:
        radar_labels = ["التقنية", "التواصل", "الخبرة", "التعليم", "القيادة"]

    base_score = cv.score or 50
    radar_scores = [base_score, min(100, base_score+10), base_score, max(0, base_score-10), base_score]

    return render_template('skill_analysis.html',
                           profession=cv.profession or "متخصص",
                           skills_data=skills_data,
                           cv_score=cv.score or 0,
                           radar_labels=radar_labels,
                           radar_scores=radar_scores)

@search_bp.route('/interview-prep/<skill>')
@login_required
def interview_prep(skill):
    """توليد أسئلة (مقابلة عمل) أو (مقابلة منحة) مخصصة"""
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    
    if current_user.role == 'scholarship_seeker':
        prompt = (f"أنت خبير في لجان قبول المنح العالمية. قم بتوليد 5 أسئلة مقابلة أكاديمية "
                  f"لتقييم مهارة ({skill}) لمتقدم يسعى للحصول على منحة دراسية. اللغة: العربية.")
    else:
        prompt = (f"أنت خبير موارد بشرية عالمي. قم بتوليد 5 أسئلة مقابلة عمل احترافية مع "
                  f"نصائح للإجابة عنها لمهارة ({skill}) لشخص يعمل كـ ({cv.profession if cv else 'متخصص'}). اللغة: العربية.")

    content = openrouter_ai._call_ai(prompt)

    if content:
        try:
            session = InterviewSession(user_id=current_user.id, skill_name=skill, questions_content=content)
            db.session.add(session)
            db.session.commit()
            if current_user.telegram_id:
                send_message(current_user.telegram_id, f"🧠 جلسة التحضير لـ ({skill}) جاهزة!")
        except:
            db.session.rollback()

        return render_template('interview_prep_view.html', skill=skill, content=content)

    flash('فشل في توليد الأسئلة، يرجى المحاولة لاحقاً.', 'danger')
    return redirect(url_for('search.skill_analysis'))

@search_bp.route('/session/delete/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    session = InterviewSession.query.get_or_404(session_id)
    if session.user_id != current_user.id: abort(403)
    try:
        db.session.delete(session)
        db.session.commit()
        flash('تم حذف جلسة التحضير.', 'info')
    except: db.session.rollback()
    return redirect(url_for('auth.dashboard'))

