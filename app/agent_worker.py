# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint
from datetime import datetime
import os

# تعريف البلوبرنت
agent_bp = Blueprint('agent', __name__)

@agent_bp.route('/run-jobs-agent')
def run_agent():
    # استيراد الموديلات داخل الدالة لكسر التعارض (Circular Import)
    from app.models import User, CV, db
    from app.serper_search import serper_searcher
    from app.telegram_bot import send_message

    try:
        # جلب المستخدمين الذين فعلوا الوكيل الذكي
        users = User.query.filter_by(agent_enabled=True).all()
        
        if not users:
            return "No active agents found in database", 200

        for user in users:
            # تخطي المستخدم إذا لم يربط تلجرام
            if not user.telegram_id:
                continue

            # تحديد استعلام البحث (من الإعدادات أو التخصص في CV)
            query = user.agent_query
            if not query:
                cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
                query = cv.profession if cv else None
            
            if not query:
                continue

            # تنفيذ البحث عبر Serper API
            results = serper_searcher.search_jobs(query)
            jobs = results.get('jobs', [])[:3]  # نأخذ أفضل 3 نتائج فقط

            if jobs:
                msg = f"🤖 <b>مساعد جوبيني الذكي</b>\n"
                msg += f"لقد وجدت وظائف جديدة لـ: <b>{query}</b>\n\n"
                
                for j in jobs:
                    msg += f"📍 {j.get('title')}\n"
                    msg += f"🏢 {j.get('company')}\n"
                    msg += f"🔗 <a href='{j.get('link')}'>تقديم الآن</a>\n"
                    msg += "------------------\n"
                
                # إرسال الرسالة للمستخدم عبر بوت تلجرام
                send_message(user.telegram_id, msg)
                
                # تحديث وقت آخر تشغيل للوكيل
                user.last_agent_run = datetime.utcnow()
                db.session.commit()

        return "Agent execution finished successfully", 200
    except Exception as e:
        return f"Agent Error: {str(e)}", 500
