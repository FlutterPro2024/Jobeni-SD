# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint
from datetime import datetime
from sqlalchemy import text 
import os
from app.openrouter_ai import get_ai_response # استيراد الذكاء الاصطناعي

agent_bp = Blueprint('agent', __name__)

class JobeniAgent:
    """كلاس الوكيل الذكي للتحليل والإرشاد"""
    @staticmethod
    def get_career_advice(query, cv_text=None):
        prompt = f"أنت مستشار مهني خبير في سوق العمل. المستخدم يسأل: {query}."
        if cv_text:
            prompt += f"\nبناءً على سيرته الذاتية التالية: {cv_text}\n قدم نصيحة مخصصة وموجهة."
        return get_ai_response(prompt)

    @staticmethod
    def analyze_cv_deeply(cv_text):
        prompt = f"""
        حلل السيرة الذاتية التالية بدقة واحترافية:
        {cv_text}
        
        المطلوب تقرير يشمل:
        1. نقاط القوة (3 نقاط).
        2. فجوات مهنية تحتاج تطوير (3 نقاط).
        3. كلمات مفتاحية (Keywords) لتحسين الـ ATS.
        4. مسميات وظيفية مقترحة بناءً على الخبرة.
        اجعل الأسلوب مشجعاً ومهنياً.
        """
        return get_ai_response(prompt)

@agent_bp.route('/run-jobs-agent')
def run_agent():
    from app.models import User, CV, db
    from app.serper_search import serper_searcher
    from app.telegram_bot import send_message

    # --- مصلح قاعدة البيانات التلقائي ---
    try:
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
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
            
            if not query:
                query = cv.profession if cv else None

            if not query:
                continue

            # البحث عن وظائف
            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3]

            if jobs:
                # ميزة إضافية: تحليل الوظائف قبل إرسالها (إرشاد)
                ai_advice = ""
                if cv:
                    ai_advice = get_ai_response(f"بناءً على خبرة المرشح في {cv.profession}، قدم نصيحة قصيرة جداً للتقديم على وظيفة {query}.")

                msg = f"🤖 <b>مساعد جوبيني الذكي</b>\n"
                msg += f"لقد وجدت وظائف جديدة لـ: <b>{query}</b>\n"
                if ai_advice:
                    msg += f"💡 <b>نصيحة الوكيل:</b> {ai_advice}\n\n"
                else:
                    msg += "\n"

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
