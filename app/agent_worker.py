# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint, current_app
from datetime import datetime
from sqlalchemy import text
import json
from app.models import User, CV, db
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
        {{"percentage": 0-100, "missing": "Short missing skill", "action": "Advice"}}
        Job: {job_title} | Company: {company} | CV: {cv_text[:1500]}
        """
        try:
            res = openrouter_ai.get_ai_response(prompt, temperature=0.1)
            return json.loads(re.search(r'\{.*\}', res, re.DOTALL).group())
        except:
            return {"percentage": 50, "missing": "مهارات تقنية", "action": "حدث سيرتك"}

@agent_bp.route('/run-jobs-agent')
def run_agent():
    try:
        users = User.query.filter_by(agent_enabled=True).all()
        if not users: return "No active agents", 200

        for user in users:
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
            query = user.agent_query or (cv.profession if cv else "Jobs in Sudan")
            
            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3]

            if jobs and user.telegram_id:
                rtl = "\u200f"
                send_message(user.telegram_id, f"{rtl}🎯 <b>يا {user.username}، لقيت ليك فرص جديدة!</b>")

                for j in jobs:
                    match = JobeniAgent.calculate_match_percentage(cv.extracted_text if cv else "", j['title'], j['company'])
                    p = match.get('percentage', 0)
                    job_msg = (
                        f"{rtl}📍 <b>{j['title']}</b>\n"
                        f"{rtl}🏢 {j['company']}\n"
                        f"{rtl}📊 مطابقة: {p}%\n"
                        f"{rtl}🚀 نصيحة: {match.get('action')}"
                    )
                    keyboard = {"inline_keyboard": [[{"text": "🔗 التقديم", "url": j['link']}]]}
                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

                user.last_agent_run = datetime.utcnow()
                db.session.commit()
        return "Done", 200
    except Exception as e:
        return f"Error: {str(e)}", 500
