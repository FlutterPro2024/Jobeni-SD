# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint
from datetime import datetime
from sqlalchemy import text
import os
import json
# ربطناه بالمحرك الجديد والقوي مباشرة
from app.openrouter_ai import openrouter_ai 

agent_bp = Blueprint('agent', __name__)

class JobeniAgent:
    """كلاس الوكيل الذكي المطور للتحليل والمطابقة الذكية"""

    def __init__(self, user_cv_text=None):
        self.cv_text = user_cv_text

    @staticmethod
    def get_career_advice(query, cv_text=None):
        # برومبت صارم يمنع التخريف ويفرض الاحترافية
        prompt = f"""
        بصفتك 'مساعد جوبيني الذكي'، خبير الموارد البشرية (HR) العالمي:
        المستخدم يسأل: "{query}"
        
        السياق (سيرة المستخدم):
        {cv_text if cv_text else "لا توجد سيرة حالياً، قدم نصيحة عامة."}

        المطلوب:
        1. رد مهني مباشر باللهجة السودانية المهذبة أو لغة عربية بيضاء.
        2. قدم حلولاً لـ (العمل عن بعد، السوق المحلي، والخليج).
        3. لا تتحدث أبداً في مواضيع خارج المسار المهني (ممنوع الهلوسة).
        4. اجعل النقاط محفزة وعملية.
        """
        # استخدام الموديلات القوية مباشرة
        return openrouter_ai._call_ai(prompt, temperature=0.7)

    @staticmethod
    def calculate_match_percentage(cv_text, job_title, company):
        """دالة متطورة لحساب نسبة المطابقة وتحليل المهارات الناقصة"""
        prompt = f"""
        بصفتك ATS Analyzer خبير، قارن السيرة الذاتية مع الوظيفة.
        الوظيفة: {job_title}
        الشركة: {company}
        السيرة: {cv_text[:2000]}

        أعطني النتيجة بتنسيق JSON حصراً كالتالي:
        {{
            "percentage": (رقم من 0 لـ 100),
            "missing": "أهم مهارة تقنية ناقصة فقط",
            "action": "نصيحة مهنية قصيرة جداً"
        }}
        """
        raw_response = openrouter_ai._call_ai(prompt, temperature=0.3)
        try:
            # تنظيف الرد من أي زيادات قبل التحويل لـ JSON
            start = raw_response.find('{')
            end = raw_response.rfind('}') + 1
            return json.loads(raw_response[start:end])
        except:
            # لو الـ AI فشل، نرجع قيم افتراضية منطقية
            return {"percentage": 50, "missing": "تحليل جارٍ", "action": "حدث سيرتك لمطابقة أدق"}

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
        # جلب المستخدمين المفعلين لخاصية القناص
        users = User.query.filter_by(agent_enabled=True).all()
        if not users:
            return "No active agents found in database", 200

        for user in users:
            if not user.telegram_id:
                continue

            # الحصول على السيرة الذاتية الأخيرة
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
            
            # تحديد استعلام البحث (المسمى الوظيفي)
            query = user.agent_query or (cv.profession if cv else "وظائف تكنولوجية")
            
            # البحث عن وظائف حقيقية عبر محرك Serper (Google Jobs)
            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3]

            if jobs:
                intro_msg = f"🎯 <b>قناص الوظائف الذكي - Jobeni</b>\n"
                intro_msg += f"يا {user.username}، لقيت ليك فرص جديدة في مجال: <b>{query}</b>\n\n"
                send_message(user.telegram_id, intro_msg)

                for j in jobs:
                    title = j.get('title')
                    company = j.get('company')
                    link = j.get('link')

                    # التحليل الذكي للمطابقة لكل وظيفة بطلع من البحث
                    match_data = {"percentage": 0, "missing": "غير متاح", "action": "تأكد من تحديث السي في"}
                    if cv and cv.extracted_text:
                        match_data = JobeniAgent.calculate_match_percentage(cv.extracted_text, title, company)

                    p = match_data.get('percentage', 0)
                    score_emoji = "🔥" if p >= 80 else "✅" if p >= 50 else "⚠️"

                    # بناء نص الرسالة الاحترافي لتليجرام
                    job_msg = f"📍 <b>{title}</b>\n"
                    job_msg += f"🏢 <b>الشركة:</b> {company}\n"
                    job_msg += f"📊 <b>المطابقة:</b> {p}% {score_emoji}\n"
                    
                    if p > 0:
                        job_msg += f"💡 <b>ينقصك:</b> {match_data.get('missing')}\n"
                        job_msg += f"🚀 <b>نصيحة:</b> {match_data.get('action')}\n"

                    # أزرار تليجرام التفاعلية
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "🔗 تقديم الآن", "url": link},
                                {"text": "🎙️ مقابلة تجريبية", "callback_data": f"start_int_{title[:20]}"}
                            ]
                        ]
                    }

                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

                # تحديث وقت التشغيل لعدم تكرار الإرسال بكثافة
                user.last_agent_run = datetime.utcnow()
                db.session.commit()

        return "Agent execution finished successfully", 200
    except Exception as e:
        db.session.rollback()
        return f"Agent Error: {str(e)}", 500
