# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint, current_app
from datetime import datetime
import json
import re
from app.models import User, CV, db, Job
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification
from app.serper_search import serper_searcher # تأكد أن الكائن بهذا الاسم في ملفه
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
            # استخدام درجة حرارة منخفضة لضمان استقرار المخرجات (JSON)
            res = openrouter_ai.get_ai_response(prompt, temperature=0.1)
            # استخراج الـ JSON من داخل النص (للوقاية من هوذرة الذكاء الاصطناعي)
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"percentage": 50, "missing": "غير محدد بدقة", "action": "تأكد من توافق المهارات الأساسية"}
        except Exception as e:
            print(f"AI Match Error: {e}")
            return {"percentage": 50, "missing": "تعذر التحليل حالياً", "action": "راجع تفاصيل الوظيفة يدوياً"}

@agent_bp.route('/run-jobs-agent')
def run_agent():
    """تشغيل الوكيل للبحث عن وظائف وإرسالها للمستخدمين المشتركين"""
    try:
        # البحث فقط عن المستخدمين الذين فعلوا خيار الوكيل
        users = User.query.filter_by(agent_enabled=True).all()
        if not users: 
            return "No active agents", 200

        for user in users:
            # جلب السيرة الذاتية لغرض المطابقة
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
            
            # تحديد استعلام البحث: إما استعلام مخصص أو بناءً على المهنة في السيرة الذاتية
            query = user.agent_query or (cv.profession if cv else "وظائف تقنية في السودان")

            # استدعاء محرك البحث
            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:5] # جلب أفضل 5 نتائج

            if jobs and user.telegram_id:
                # علامة الـ RTL لضمان تنسيق اللغة العربية في تليجرام
                rtl = "\u200f"
                send_message(user.telegram_id, f"{rtl}🎯 <b>يا {user.username}، الرادار وجد فرصاً جديدة تناسبك!</b>")

                for j in jobs:
                    # حساب نسبة المطابقة لكل وظيفة
                    cv_content = cv.extracted_text if cv else "لا توجد سيرة ذاتية مرفوعة"
                    match = JobeniAgent.calculate_match_percentage(cv_content, j['title'], j['company'])
                    
                    p = match.get('percentage', 0)
                    emoji = "🔥" if p > 75 else "✅"
                    
                    job_msg = (
                        f"{rtl}📍 <b>{j['title']}</b>\n"
                        f"{rtl}🏢 {j['company']}\n"
                        f"{rtl}📊 مطابقة: {p}% {emoji}\n"
                        f"{rtl}💡 ينقصك: {match.get('missing')}\n"
                        f"{rtl}🚀 نصيحة: {match.get('action')}"
                    )
                    
                    # إنشاء زر التقديم
                    keyboard = {
                        "inline_keyboard": [[
                            {"text": "🔗 عرض وتفاصيل التقديم", "url": j['link']}
                        ]]
                    }
                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

                # تحديث وقت آخر تشغيل
                user.last_agent_run = datetime.utcnow()
                db.session.commit()
                
        return "تم تشغيل الوكيل بنجاح وإرسال التنبيهات.", 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Agent Error: {e}")
        return f"Error: {str(e)}", 500
