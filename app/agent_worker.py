from flask import Blueprint, current_app, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
import json
import re
import urllib.parse
from app.models import User, CV, db, Job, Application
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification
from app.serper_search import serper_searcher
from app.telegram_bot import send_message

agent_bp = Blueprint('agent', __name__)

class JobeniAgent:
    @staticmethod
    def calculate_match_percentage(cv_text, job_title, company):
        prompt = f"""
        Compare CV with Job. Return ONLY JSON:
        {{"percentage": 0-100, "missing": "Short missing skill in Arabic", "action": "Advice in Arabic"}}
        Job: {job_title} | Company: {company} | CV: {cv_text[:1000]}
        """
        try:
            res = openrouter_ai.get_ai_response(prompt, temperature=0.1)
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match: return json.loads(match.group())
            return {"percentage": 60, "missing": "غير محدد", "action": "راجع الوظيفة"}
        except:
            return {"percentage": 50, "missing": "تعذر التحليل", "action": "تأكد يدوياً"}

@agent_bp.route('/toggle-agent', methods=['POST', 'GET'])
@login_required
def toggle_agent():
    try:
        current_user.agent_enabled = not current_user.agent_enabled
        db.session.commit()
        status = "تفعيل" if current_user.agent_enabled else "إيقاف"
        flash(f"تم {status} الوكيل بنجاح.", "success")
    except:
        db.session.rollback()
        flash("خطأ في تغيير الحالة.", "danger")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/run-jobs-agent')
def run_agent():
    """تشغيل الوكيل - نسخة محسنة للسرعة لمنع الـ 504 Timeout"""
    try:
        # معالجة مستخدم واحد نشط عشوائي في كل طلب لضمان السرعة في Vercel
        user = User.query.filter_by(agent_enabled=True).order_by(db.func.random()).first()
        if not user: return "No active agents", 200

        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
        query = user.agent_query or (cv.profession if cv else "وظائف في السودان")

        results = serper_searcher.search_jobs(query)
        jobs = results.get('jobs', [])[:3] # تقليل العدد لـ 3 لضمان سرعة التنفيذ

        rtl = "\u200f"
        processed_count = 0

        for j in jobs:
            existing_job = Job.query.filter_by(title=j['title'], company_name=j['company']).first()
            if not existing_job:
                new_job = Job(title=j['title'], company_name=j['company'], 
                              location=j.get('location', 'Sudan'), description=f"المصدر: {j['link']}")
                db.session.add(new_job)
                db.session.flush()
                target_job_id = new_job.id
            else:
                target_job_id = existing_job.id

            existing_app = Application.query.filter_by(user_id=user.id, job_id=target_job_id).first()
            if not existing_app:
                cv_content = cv.extracted_text if cv else "لا توجد سيرة"
                match = JobeniAgent.calculate_match_percentage(cv_content, j['title'], j['company'])
                
                new_app = Application(
                    user_id=user.id, job_id=target_job_id, status='suggested',
                    match_score=match.get('percentage', 50),
                    match_explanation=f"نواقص: {match.get('missing')} | نصيحة: {match.get('action')}",
                    applied_at=datetime.utcnow()
                )
                db.session.add(new_app)
                processed_count += 1

                if user.telegram_id:
                    job_msg = f"{rtl}🎯 <b>وظيفة جديدة: {j['title']}</b>\n🏢 {j['company']}\n📊 مطابقة: {match.get('percentage')}%"
                    keyboard = {"inline_keyboard": [[{"text": "🔗 التفاصيل", "url": j['link']}]]}
                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

        user.last_agent_run = datetime.utcnow()
        db.session.commit()
        return f"Done: Processed {processed_count} jobs for {user.username}", 200
    except Exception as e:
        db.session.rollback()
        return f"Error: {str(e)}", 500

@agent_bp.route('/generate-cover-letter/<int:cv_id>/<string:job_title>')
def generate_cover_letter(cv_id, job_title):
    # يبقى كما هو
    return "Cover Letter Generation Logic Here"
