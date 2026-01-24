# ~/jobeni-sD/app/search.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.models import Job, CV, Application, InterviewSession, User, db
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
        # البحث في كافة الحقول النصية للمستخدم لضمان دقة النتائج
        search_filter = or_(
            User.username.ilike(f'%{query}%'),
            User.full_name.ilike(f'%{query}%'),
            User.headline.ilike(f'%{query}%'),
            User.bio.ilike(f'%{query}%')
        )
        users = User.query.filter(search_filter).filter(User.id != current_user.id).limit(20).all()
    else:
        # اقتراح مستخدمين عشوائيين أو جدد عند عدم وجود بحث
        users = User.query.filter(User.id != current_user.id).order_by(db.func.random()).limit(12).all()

    return render_template('search_users.html', 
                           users=users, 
                           query=query, 
                           utcnow=datetime.utcnow())

# --- ثانياً: كود البحث عن الوظائف (محلي + عالمي AI) ---
@search_bp.route('/jobs/search')
def jobs_list():
    """محرك بحث هجين يجمع بين قاعدة بيانات جوبيني والبحث العالمي عبر AI"""
    q = request.args.get('q', '').strip()
    loc = request.args.get('location', '').strip()
    
    # 1. البحث المحلي في السودان
    query = Job.query.filter_by(is_active=True)
    if q:
        query = query.filter(or_(Job.title.ilike(f'%{q}%'), Job.description.ilike(f'%{q}%')))
    if loc:
        query = query.filter(Job.location.ilike(f'%{loc}%'))
    
    local_jobs = query.order_by(Job.created_at.desc()).all()
    
    # 2. البحث العالمي باستخدام Serper API (إذا كان هناك مسمى وظيفي)
    global_jobs_data = []
    if q:
        search_term = f"{q} remote jobs" if not loc else f"{q} jobs in {loc}"
        try:
            results = serper_searcher.search_jobs(search_term)
            global_jobs_data = results.get('jobs', [])
        except Exception as e:
            print(f"Global Search Error: {e}")
            global_jobs_data = []

    return render_template('search_results.html',
                           jobs=local_jobs,
                           global_jobs=global_jobs_data,
                           search_query=q,
                           location_query=loc)

# --- ثالثاً: تحليل المهارات والتحضير الذكي للمقابلات ---
@search_bp.route('/skill-analysis')
@login_required
def skill_analysis():
    """تحليل متقدم لنقاط القوة والضعف بناءً على السيرة الذاتية"""
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not cv:
        flash('يجب رفع سيرتك الذاتية أولاً لتفعيل نظام التحليل الذكي.', 'info')
        return redirect(url_for('cv.upload_cv'))

    # استخراج المهارات ومعالجتها
    skills_list = cv.skills if isinstance(cv.skills, list) else []
    
    # بناء بيانات المهارات مع روابط التعلم والتحضير
    skills_data = [
        {
            "name": s,
            "url": f"https://www.youtube.com/results?search_query=learn+{s}+course",
            "prep_url": url_for('search.interview_prep', skill=s)
        } for s in skills_list
    ]
    
    # تجهيز بيانات رادار المهارات (Radar Chart) للتحليل المرئي
    radar_labels = ["التقنية", "التواصل", "الخبرة", "التعليم", "القيادة"]
    # محاولة جلب السكور من الـ AI أو استخدام قيم افتراضية مبنية على سكور الـ CV
    base_score = cv.score or 50
    radar_scores = [base_score, min(100, base_score+10), base_score, max(0, base_score-10), base_score]

    return render_template('skill_analysis.html',
                           profession=cv.profession or "متخصص مهني",
                           skills_data=skills_data,
                           cv_score=cv.score or 0,
                           cv_id=cv.id,
                           radar_labels=radar_labels,
                           radar_scores=radar_scores)

@search_bp.route('/interview-prep/<skill>')
@login_required
def interview_prep(skill):
    """توليد أسئلة مقابلة مخصصة لكل مهارة باستخدام OpenRouter AI"""
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    
    # بناء برومبت دقيق للـ AI
    prompt = (f"أنت خبير موارد بشرية عالمي. قم بتوليد 5 أسئلة مقابلة عمل احترافية مع "
              f"نصائح للإجابة عنها لمهارة ({skill}) لشخص يعمل كـ ({cv.profession if cv else 'متخصص'}). "
              f"اللغة: العربية.")
    
    content = openrouter_ai._call_ai(prompt)
    
    if content:
        try:
            # حفظ جلسة التحضير في قاعدة البيانات للرجوع إليها
            session = InterviewSession(
                user_id=current_user.id, 
                skill_name=skill, 
                questions_content=content
            )
            db.session.add(session)
            db.session.commit()
            
            # إرسال إشعار تليجرام إذا كان البوت مفعلاً
            if current_user.telegram_id:
                try:
                    send_message(current_user.telegram_id, f"🧠 مبروك! جلسة التحضير لمهارة ({skill}) جاهزة الآن في ملفك الشخصي.")
                except: pass
                
        except Exception as e:
            print(f"Session DB Error: {e}")
            db.session.rollback()
            
        return render_template('interview_prep_view.html', skill=skill, content=content)
    
    flash('فشل في توليد الأسئلة، يرجى المحاولة لاحقاً.', 'danger')
    return redirect(url_for('search.skill_analysis'))

@search_bp.route('/session/delete/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    """حذف جلسة تحضير مقابلة"""
    session = InterviewSession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        abort(403)
    try:
        db.session.delete(session)
        db.session.commit()
        flash('تم حذف جلسة التحضير.', 'info')
    except:
        db.session.rollback()
    return redirect(url_for('auth.dashboard'))
