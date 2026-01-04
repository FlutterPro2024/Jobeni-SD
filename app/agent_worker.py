# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint
# حذفنا استيراد db و User من هنا عشان نمنع الـ Circular Import
from app.serper_search import serper_searcher
from app.telegram_bot import send_message
from datetime import datetime

agent_bp = Blueprint('agent', __name__)

@agent_bp.route('/run-jobs-agent')
def run_agent():
    # استيراد الموديلات داخل الدالة (Lazy Import)
    from app.models import User, CV, db
    
    try:
        users = User.query.filter_by(agent_enabled=True).all()
        if not users:
            return "No users with active agent found", 200

        for user in users:
            if not user.telegram_id: continue

            query = user.agent_query
            if not query:
                cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
                query = cv.profession if cv else None

            if not query: continue

            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3]

            if jobs:
                msg = f"🤖 <b>مساعد جوبيني الذكي</b>\nبحثت لك عن: <b>{query}</b>\n\n"
                for j in jobs:
                    msg += f"📍 {j.get('title')}\n🏢 {j.get('company')}\n🔗 <a href='{j.get('link')}'>تقديم</a>\n---\n"

                send_message(user.telegram_id, msg)
                user.last_agent_run = datetime.utcnow()
                db.session.commit()

        return "Agent Done", 200
    except Exception as e:
        return f"Error: {str(e)}", 500
