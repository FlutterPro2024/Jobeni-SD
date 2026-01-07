# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint
from datetime import datetime
from sqlalchemy import text
import os
import json
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification # إضافة الإشعارات

agent_bp = Blueprint('agent', __name__)

class JobeniAgent:
    def __init__(self, user_cv_text=None):
        self.cv_text = user_cv_text

    @staticmethod
    def get_career_advice(query, cv_text=None):
        prompt = f"""
        بصفتك 'مساعد جوبيني الذكي'، خبير الموارد البشرية (HR) العالمي:
        المستخدم يسأل: "{query}"
        السياق (سيرة المستخدم): {cv_text if cv_text else "لا توجد سيرة حالياً."}

        المطلوب:
        1. رد مهني مباشر باللهجة السودانية المهذبة أو لغة عربية بيضاء.
        2. قدم حلولاً لـ (العمل عن بعد، السوق المحلي، والخليج).
        3. لا تتحدث أبداً في مواضيع خارج المسار المهني.
        """
        return openrouter_ai._call_ai(prompt, temperature=0.7)

    @staticmethod
    def calculate_match_percentage(cv_text, job_title, company):
        prompt = f"""
        بصفتك ATS Analyzer خبير، قارن السيرة الذاتية مع الوظيفة.
        الوظيفة: {job_title} | الشركة: {company} | السيرة: {cv_text[:2000]}

        أعطني النتيجة بتنسيق JSON حصراً كالتالي:
        {{
            "percentage": (رقم من 0 لـ 100),
            "missing": "أهم مهارة تقنية ناقصة فقط",
            "action": "نصيحة مهنية قصيرة جداً"
        }}
        """
        raw_response = openrouter_ai._call_ai(prompt, temperature=0.3)
        try:
            start = raw_response.find('{')
            end = raw_response.rfind('}') + 1
            return json.loads(raw_response[start:end])
        except:
            return {"percentage": 50, "missing": "تحليل جارٍ", "action": "حدث سيرتك لمطابقة أدق"}

@agent_bp.route('/run-jobs-agent')
def run_agent():
    from app.models import User, CV, db
    from app.serper_search import serper_searcher
    from app.telegram_bot import send_message

    # صيانة قاعدة البيانات
    try:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_query VARCHAR(255)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_agent_run TIMESTAMP'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    try:
        users = User.query.filter_by(agent_enabled=True).all()
        if not users:
            return "No active agents found", 200

        for user in users:
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
            query = user.agent_query or (cv.profession if cv else "وظائف تكنولوجية")

            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3]

            if jobs:
                # 1. إرسال إشعار الجرس (Dashboard Notification)
                add_notification(
                    user.id,
                    "قناص جوبيني لقى ليك وظيفة! 🔥",
                    f"تم العثور على {len(jobs)} وظائف جديدة في مجال {query} تناسبك.",
                    "job_alert",
                    "/dashboard"
                )

                # 2. إرسال رسائل التلجرام
                intro_msg = f"🎯 <b>قناص الوظائف الذكي - Jobeni</b>\nيا {user.username}، لقيت ليك فرص جديدة في مجال: <b>{query}</b>\n\n"
                send_message(user.telegram_id, intro_msg)

                for j in jobs:
                    title = j.get('title')
                    company = j.get('company')
                    link = j.get('link')

                    match_data = {"percentage": 0, "missing": "غير متاح", "action": "تأكد من تحديث السي في"}
                    if cv and cv.extracted_text:
                        match_data = JobeniAgent.calculate_match_percentage(cv.extracted_text, title, company)

                    p = match_data.get('percentage', 0)
                    score_emoji = "🔥" if p >= 80 else "✅" if p >= 50 else "⚠️"

                    job_msg = f"📍 <b>{title}</b>\n🏢 <b>الشركة:</b> {company}\n📊 <b>المطابقة:</b> {p}% {score_emoji}\n"
                    if p > 0:
                        job_msg += f"💡 <b>ينقصك:</b> {match_data.get('missing')}\n🚀 <b>نصيحة:</b> {match_data.get('action')}\n"

                    keyboard = {"inline_keyboard": [[{"text": "🔗 تقديم الآن", "url": link}, {"text": "🎙️ مقابلة تجريبية", "callback_data": f"start_int_{title[:20]}"}]]}
                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

                user.last_agent_run = datetime.utcnow()
                db.session.commit()

        return "Agent execution finished successfully", 200
    except Exception as e:
        db.session.rollback()
        return f"Agent Error: {str(e)}", 500
