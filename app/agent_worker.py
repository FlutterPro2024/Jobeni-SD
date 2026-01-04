# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint
from datetime import datetime
from sqlalchemy import text # استيراد لتنفيذ أوامر مباشرة
import os

agent_bp = Blueprint('agent', __name__)

@agent_bp.route('/run-jobs-agent')
def run_agent():
    from app.models import User, CV, db
    from app.serper_search import serper_searcher
    from app.telegram_bot import send_message

    # --- مصلح قاعدة البيانات التلقائي ---
    try:
        # محاولة إضافة الأعمدة الجديدة يدوياً في حال لم تكن موجودة
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_query VARCHAR(255)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_agent_run TIMESTAMP'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Schema Update Note: {e}") 
    # ----------------------------------

    try:
        users = User.query.filter_by(agent_enabled=True).all()
        
        if not users:
            return "No active agents found in database", 200

        for user in users:
            if not user.telegram_id:
                continue

            query = user.agent_query
            if not query:
                cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
                query = cv.profession if cv else None
            
            if not query:
                continue

            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3]

            if jobs:
                msg = f"🤖 <b>مساعد جوبيني الذكي</b>\n"
                msg += f"لقد وجدت وظائف جديدة لـ: <b>{query}</b>\n\n"
                
                for j in jobs:
                    msg += f"📍 {j.get('title')}\n"
                    msg += f"🏢 {j.get('company')}\n"
                    msg += f"🔗 <a href='{j.get('link')}'>تقديم الآن</a>\n"
                    msg += "------------------\n"
                
                send_message(user.telegram_id, msg)
                user.last_agent_run = datetime.utcnow()
                db.session.commit()

        return "Agent execution finished successfully", 200
    except Exception as e:
        return f"Agent Error: {str(e)}", 500
