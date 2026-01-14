# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint, current_app, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
import json
import re
import urllib.parse
from app.models import User, CV, db, Job, Application  # أضفنا Application
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification
from app.serper_search import serper_searcher
from app.telegram_bot import send_message

agent_bp = Blueprint('agent', __name__)

class JobeniAgent:
    @staticmethod
    def calculate_match_percentage(cv_text, job_title, company):
        """تحليل التوافق بين السيرة الذاتية والوظيفة باستخدام AI"""
        prompt = f"""
        Compare CV with Job. Return ONLY JSON:
        {{
          "percentage": 0-100,
          "missing": "Short missing skill in Arabic",
          "action": "Advice in Arabic"
        }}
        Job: {job_title} | Company: {company} | CV: {cv_text[:1500]}
        """
        try:
            res = openrouter_ai.get_ai_response(prompt, temperature=0.1)
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"percentage": 50, "missing": "غير محدد بدقة", "action": "تأكد من توافق المهارات الأساسية"}
        except Exception as e:
            print(f"AI Match Error: {e}")
            return {"percentage": 50, "missing": "تعذر التحليل حالياً", "action": "راجع تفاصيل الوظيفة يدوياً"}

@agent_bp.route('/toggle-agent', methods=['POST'])
@login_required
def toggle_agent():
    """تبديل حالة الوكيل الذكي من الـ Dashboard"""
    try:
        current_user.agent_enabled = not current_user.agent_enabled
        db.session.commit()
        status = "تفعيل" if current_user.agent_enabled else "إيقاف"
        flash(f"تم {status} الوكيل الذكي بنجاح.", "success")
    except Exception as e:
        db.session.rollback()
        flash("حدث خطأ أثناء تغيير حالة الوكيل.", "danger")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/run-jobs-agent')
def run_agent():
    """تشغيل الوكيل للبحث عن وظائف وإرسالها للمستخدمين وحفظها في الداتابيز"""
    try:
        users = User.query.filter_by(agent_enabled=True).all()
        if not users:
            return "No active agents", 200

        for user in users:
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
            query = user.agent_query or (cv.profession if cv else "وظائف تقنية في السودان")
            
            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:5]

            if jobs:
                rtl = "\u200f"
                if user.telegram_id:
                    send_message(user.telegram_id, f"{rtl}🎯 <b>يا {user.username}، الرادار وجد فرصاً جديدة تناسبك وحفظتها لك في المنصة!</b>")

                for j in jobs:
                    cv_content = cv.extracted_text if cv else "لا توجد سيرة ذاتية مرفوعة"
                    match = JobeniAgent.calculate_match_percentage(cv_content, j['title'], j['company'])
                    
                    p = match.get('percentage', 0)
                    missing = match.get('missing')
                    action = match.get('action')
                    
                    # --- التحديث الجديد: حفظ الوظيفة والمطابقة في الداتابيز ---
                    # التأكد من عدم تكرار الوظيفة
                    existing_job = Job.query.filter_by(title=j['title'], company_name=j['company']).first()
                    if not existing_job:
                        new_job = Job(
                            title=j['title'],
                            company_name=j['company'],
                            location=j.get('location', 'Remote'),
                            description=f"المصدر: {j['link']}",
                            created_at=datetime.utcnow()
                        )
                        db.session.add(new_job)
                        db.session.flush()
                        target_job_id = new_job.id
                    else:
                        target_job_id = existing_job.id

                    # حفظ النتيجة في التطبيقات بصفة 'suggested'
                    existing_app = Application.query.filter_by(user_id=user.id, job_id=target_job_id).first()
                    if not existing_app:
                        new_app = Application(
                            user_id=user.id,
                            job_id=target_job_id,
                            status='suggested',
                            match_score=p,
                            match_explanation=f"نواقص: {missing} | نصيحة: {action}",
                            applied_at=datetime.utcnow()
                        )
                        db.session.add(new_app)
                    # -------------------------------------------------------

                    if user.telegram_id:
                        emoji = "🔥" if p > 75 else "✅"
                        job_msg = (
                            f"{rtl}📍 <b>{j['title']}</b>\n"
                            f"{rtl}🏢 {j['company']}\n"
                            f"{rtl}📊 مطابقة: {p}% {emoji}\n"
                            f"{rtl}💡 ينقصك: {missing}\n"
                            f"{rtl}🚀 نصيحة: {action}"
                        )
                        
                        encoded_job_title = urllib.parse.quote(j['title'])
                        base_site_url = "https://jobeni-sd.vercel.app"
                        cv_id = cv.id if cv else 0

                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "🔗 عرض وتفاصيل التقديم", "url": j['link']}],
                                [{"text": "📝 تجهيز رسالة التقديم (AI)", "url": f"{base_site_url}/agent/generate-cover-letter/{cv_id}/{encoded_job_title}"}]
                            ]
                        }
                        send_message(user.telegram_id, job_msg, reply_markup=keyboard)

                user.last_agent_run = datetime.utcnow()
                db.session.commit()

        return "تم تشغيل الوكيل وحفظ الوظائف بنجاح.", 200
    except Exception as e:
        db.session.rollback()
        print(f"Agent Error: {e}")
        return f"Error: {str(e)}", 500

@agent_bp.route('/generate-cover-letter/<int:cv_id>/<string:job_title>')
def generate_cover_letter(cv_id, job_title):
    # (يبقى كما هو بدون تغيير)
    ...
