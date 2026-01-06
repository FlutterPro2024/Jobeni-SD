# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint
from datetime import datetime
from sqlalchemy import text
import os
import json
from app.openrouter_ai import get_ai_response

agent_bp = Blueprint('agent', __name__)

class JobeniAgent:
    """كلاس الوكيل الذكي المطور للتحليل والمطابقة الذكية"""

    def __init__(self, user_cv_text=None):
        self.cv_text = user_cv_text

    @staticmethod
    def get_career_advice(query, cv_text=None):
        prompt = f"""
        أنت 'مساعد جوبيني الذكي'، مستشار مهني عالمي.
        المستخدم يسأل: {query}
        """
        if cv_text:
            prompt += f"\nبناءً على سيرته الذاتية التالية: {cv_text}\n"

        prompt += """
        المطلوب: تقديم نصيحة شاملة (عن بعد، محلي، دولي) بنقاط واضحة وبدون رموز تقنية.
        """
        return get_ai_response(prompt)

    @staticmethod
    def calculate_match_percentage(cv_text, job_title, company):
        """دالة متطورة لحساب نسبة المطابقة وتحليل المهارات الناقصة"""
        prompt = f"""
        بصفتك خبير توظيف (Recruiter)، قارن السيرة الذاتية التالية مع الوظيفة المتاحة.

        السيرة الذاتية: {cv_text}
        الوظيفة: {job_title} في شركة {company}

        المطلوب رد بتنسيق JSON حصراً يحتوي على:
        1. "percentage": رقم يمثل نسبة المطابقة (0-100).
        2. "missing": نص قصير جداً (أهم مهارة ناقصة).
        3. "action": نصيحة سريعة لزيادة فرصة القبول.

        تنسيق الرد:
        {{"percentage": 85, "missing": "مهارة X", "action": "افعل كذا"}}
        """
        raw_response = get_ai_response(prompt)
        try:
            # محاولة استخراج JSON من الرد
            start = raw_response.find('{')
            end = raw_response.rfind('}') + 1
            return json.loads(raw_response[start:end])
        except:
            return {"percentage": 0, "missing": "غير محدد", "action": "حدث بياناتك لنتائج أفضل"}

@agent_bp.route('/run-jobs-agent')
def run_agent():
    from app.models import User, CV, db
    from app.serper_search import serper_searcher
    from app.telegram_bot import send_message

    # --- مصلح قاعدة البيانات التلقائي (Schema Fix) ---
    try:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_query VARCHAR(255)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_agent_run TIMESTAMP'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Schema Update Note: {e}")

    try:
        users = User.query.filter_by(agent_enabled=True).all()
        if not users:
            return "No active agents found in database", 200

        for user in users:
            if not user.telegram_id:
                continue

            # الحصول على السيرة الذاتية الأخيرة للمستخدم
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
            
            # تحديد استعلام البحث (المسمى الوظيفي)
            query = user.agent_query or (cv.profession if cv else None)
            if not query:
                continue

            # البحث عن وظائف عبر Serper
            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3]

            if jobs:
                # رسالة ترحيبية عامة قبل سرد الوظائف
                intro_msg = f"🎯 <b>قناص الوظائف الذكي - Jobeni</b>\n"
                intro_msg += f"تم العثور على فرص جديدة لاهتماماتك: <b>{query}</b>\n\n"
                send_message(user.telegram_id, intro_msg)

                for j in jobs:
                    title = j.get('title')
                    company = j.get('company')
                    link = j.get('link')

                    # ميزة المطابقة الذكية وتحليل AI
                    match_data = {"percentage": 0, "missing": "غير متاح", "action": "تأكد من تحديث السي في"}
                    if cv and cv.extracted_text:
                        match_data = JobeniAgent.calculate_match_percentage(cv.extracted_text, title, company)

                    # اختيار إيموجي وحالة بناءً على النسبة
                    p = match_data.get('percentage', 0)
                    score_emoji = "🔥" if p >= 80 else "✅" if p >= 50 else "⚠️"

                    # بناء نص الرسالة للوظيفة الواحدة
                    job_msg = f"📍 <b>{title}</b>\n"
                    job_msg += f"🏢 <b>الشركة:</b> {company}\n"
                    job_msg += f"📊 <b>نسبة المطابقة:</b> {p}% {score_emoji}\n"
                    
                    if p > 0:
                        job_msg += f"💡 <b>ينقصك:</b> {match_data.get('missing')}\n"
                        job_msg += f"🚀 <b>نصيحة:</b> {match_data.get('action')}\n"
                    
                    # إنشاء الأزرار التفاعلية (Inline Keyboard)
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "🔗 تقديم الآن", "url": link},
                                {"text": "🎙️ مقابلة سريعة", "callback_data": f"start_int_{title[:20]}"}
                            ]
                        ]
                    }

                    # إرسال الوظيفة مع الأزرار
                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

                # تحديث وقت التشغيل الأخير
                user.last_agent_run = datetime.utcnow()
                db.session.commit()

        return "Agent execution finished successfully with Match Analysis and Buttons", 200
    except Exception as e:
        db.session.rollback()
        return f"Agent Error: {str(e)}", 500
