# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint
from datetime import datetime
from sqlalchemy import text
import os
import json
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification 

agent_bp = Blueprint('agent', __name__)

class JobeniAgent:
    def __init__(self, user_cv_text=None):
        self.cv_text = user_cv_text

    @staticmethod
    def get_career_advice(query, cv_text=None):
        """مستشار مهني ذكي يستخدم الـ Fallback System"""
        prompt = f"""
        بصفتك 'مساعد جوبيني الذكي'، خبير الموارد البشرية العالمي:
        المستخدم يسأل: "{query}"
        السياق (سيرة المستخدم): {cv_text if cv_text else "لا توجد سيرة حالياً."}

        المطلوب:
        1. رد مهني مباشر بلغة عربية بيضاء مفهومة.
        2. استخدم النقاط (•) بدلاً من الداشات (-) في أي قائمة.
        3. قدم حلولاً عملية (العمل عن بعد، الخليج، والسوق المحلي).
        """
        return openrouter_ai.get_ai_response(prompt, temperature=0.7)

    @staticmethod
    def calculate_match_percentage(cv_text, job_title, company):
        """مطابقة ذكية للوظائف مع تجنب لخبطة الاتجاهات"""
        prompt = f"""
        Compare CV with Job.
        Job: {job_title} | Company: {company}
        Return ONLY a JSON object:
        {{
            "percentage": (0-100),
            "missing": "Short missing skill with •",
            "action": "Short advice with •"
        }}
        CV: {cv_text[:2000]}
        """
        raw_response = openrouter_ai.get_ai_response(prompt, temperature=0.2)
        try:
            # استخراج الـ JSON بدقة
            start = raw_response.find('{')
            end = raw_response.rfind('}') + 1
            data = json.loads(raw_response[start:end])
            return data
        except:
            return {"percentage": 50, "missing": "• مهارات تقنية متقدمة", "action": "• حدث سيرتك لمطابقة أدق"}

@agent_bp.route('/run-jobs-agent')
def run_agent():
    from app.models import User, CV, db
    from app.serper_search import serper_searcher
    from app.telegram_bot import send_message

    # صيانة وتحديث جداول قاعدة البيانات (لضمان عمل الوكيل)
    try:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_query VARCHAR(255)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_agent_run TIMESTAMP'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    try:
        # جلب المستخدمين الذين فعلوا "قناص الوظائف"
        users = User.query.filter_by(agent_enabled=True).all()
        if not users:
            return "No active agents found", 200

        for user in users:
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
            # استخدام استعلام المستخدم أو تخصص السي في ككلمة بحث
            query = user.agent_query or (cv.profession if cv else "وظائف تكنولوجية")

            # البحث عن وظائف عبر Serper
            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3] # نأخذ أفضل 3 نتائج لضمان جودة التحليل

            if jobs:
                # 1. إشعار في لوحة تحكم المنصة
                add_notification(
                    user.id,
                    "🔥 قناص جوبيني وجد فرصاً جديدة!",
                    f"لقد وجدنا {len(jobs)} وظائف في مجال {query} تطابق مهاراتك.",
                    "job_alert",
                    "/dashboard"
                )

                # 2. إرسال الرسائل إلى تلجرام بتنسيق RTL احترافي
                rtl = "\u200f" # رمز إجبار الاتجاه من اليمين لليسار
                intro_msg = f"{rtl}🎯 <b>قناص الوظائف الذكي - Jobeni</b>\n{rtl}يا {user.username}، لقيت ليك فرص جديدة في مجال: <b>{query}</b>\n\n"
                send_message(user.telegram_id, intro_msg)

                for j in jobs:
                    title = j.get('title')
                    company = j.get('company')
                    link = j.get('link')

                    # تحليل المطابقة بالـ AI
                    match_data = {"percentage": 0, "missing": "غير متاح", "action": "تأكد من تحديث السي في"}
                    if cv and cv.extracted_text:
                        match_data = JobeniAgent.calculate_match_percentage(cv.extracted_text, title, company)

                    p = match_data.get('percentage', 0)
                    score_emoji = "🔥" if p >= 80 else "✅" if p >= 50 else "⚠️"

                    # بناء رسالة الوظيفة بتنسيق يمنع تداخل العربي والإنجليزي
                    job_msg = (
                        f"{rtl}📍 <b>{title}</b>\n"
                        f"{rtl}🏢 <b>الشركة:</b> {company}\n"
                        f"{rtl}📊 <b>المطابقة:</b> {p}% {score_emoji}\n"
                    )
                    
                    if p > 0:
                        job_msg += f"{rtl}💡 <b>ينقصك:</b> {match_data.get('missing')}\n"
                        job_msg += f"{rtl}🚀 <b>نصيحة:</b> {match_data.get('action')}\n"

                    # إضافة أزرار تفاعلية تحت كل وظيفة
                    keyboard = {
                        "inline_keyboard": [[
                            {"text": "🔗 تقديم الآن", "url": link},
                            {"text": "🎙️ مقابلة تجريبية", "callback_data": f"start_int_{user.id}"}
                        ]]
                    }
                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

                # تحديث وقت آخر تشغيل للوكيل
                user.last_agent_run = datetime.utcnow()
                db.session.commit()

        return "Agent execution finished successfully", 200
    except Exception as e:
        db.session.rollback()
        return f"Agent Error: {str(e)}", 500
