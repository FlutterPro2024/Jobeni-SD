# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint, current_app, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import json
import re
import urllib.parse
from app.models import User, CV, db, Job, Application
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification
from app.serper_search import serper_searcher
from app.telegram_bot import send_message

agent_bp = Blueprint('agent', __name__)

class JobeniAgent:
    @staticmethod
    def calculate_match_percentage(cv_text, job_title, job_desc):
        """تحليل ذكي عميق للمطابقة بين السي في والوظيفة"""
        prompt = f"""
        Act as an Expert AI Recruiter. 
        Compare this CV with the Job Details.
        Job Title: {job_title}
        Description: {job_desc[:500]}
        CV Content: {cv_text[:1200]}
        
        Return ONLY a JSON object:
        {{
            "percentage": 0-100,
            "missing": "أهم المهارات الناقصة بالعربية",
            "action": "نصيحة ذهبية للمرشح بالعربية",
            "is_fit": true/false
        }}
        """
        try:
            res = openrouter_ai.get_ai_response(prompt, temperature=0.2)
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"percentage": 60, "missing": "غير محدد", "action": "راجع المتطلبات"}
        except:
            return {"percentage": 50, "missing": "تعذر التحليل", "action": "تأكد يدوياً"}

    @staticmethod
    def generate_professional_cover_letter(cv_text, job_title, company):
        """توليد خطاب تغطية احترافي مخصص"""
        prompt = f"""
        Write a professional Cover Letter (English) for:
        Job: {job_title} | Company: {company}
        Based on this CV: {cv_text[:1500]}
        Keep it concise, powerful, and ATS-friendly.
        """
        return openrouter_ai.get_ai_response(prompt, temperature=0.7)

@agent_bp.route('/toggle-agent', methods=['POST', 'GET'])
@login_required
def toggle_agent():
    """تفعيل أو إيقاف الوكيل الذكي"""
    try:
        current_user.agent_enabled = not current_user.agent_enabled
        db.session.commit()
        status = "تفعيل" if current_user.agent_enabled else "إيقاف"
        add_notification(current_user.id, f"الوكيل الذكي: {status}", f"تم {status} رادار الوظائف بنجاح.", "info")
        flash(f"تم {status} الوكيل بنجاح.", "success")
    except:
        db.session.rollback()
        flash("خطأ في تغيير الحالة.", "danger")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/run-jobs-agent')
def run_agent():
    """تشغيل الوكيل لمسح السوق وجلب الوظائف (Optimized for Vercel 10s)"""
    try:
        # اختيار مستخدم نشط عشوائي لتوزيع الحمل
        user = User.query.filter_by(agent_enabled=True).order_by(db.func.random()).first()
        if not user: 
            return "No active agents found.", 200

        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
        # تحديد كلمات البحث (الذكاء الاصطناعي يحددها بناءً على التخصص)
        query = user.agent_query or (cv.profession if cv else "وظائف في السودان")

        # تشغيل الرادار (Search Engine)
        results = serper_searcher.search_jobs(query)
        jobs = results.get('jobs', [])[:3] # جلب أفضل 3 وظائف فقط لضمان السرعة

        processed_count = 0
        rtl_char = "\u200f" # لضبط اللغة العربية في تليجرام

        for j in jobs:
            # 1. فحص هل الوظيفة موجودة في نظامنا؟
            job_obj = Job.query.filter_by(title=j['title'], company_name=j['company']).first()
            if not job_obj:
                job_obj = Job(
                    title=j['title'], 
                    company_name=j['company'],
                    location=j.get('location', 'السودان'), 
                    description=f"وظيفة مكتشفة عبر الوكيل الذكي.\nالمصدر: {j['link']}"
                )
                db.session.add(job_obj)
                db.session.flush()

            # 2. فحص هل تم تقديم/اقتراح هذه الوظيفة لهذا المستخدم؟
            existing_app = Application.query.filter_by(user_id=user.id, job_id=job_obj.id).first()
            if not existing_app:
                # 3. تحليل المطابقة بالذكاء الاصطناعي
                cv_content = cv.extracted_text if cv else "لا توجد سيرة"
                match = JobeniAgent.calculate_match_percentage(cv_content, j['title'], j['company'])

                # 4. حفظ الاقتراح الذكي
                new_app = Application(
                    user_id=user.id, 
                    job_id=job_obj.id, 
                    status='suggested',
                    match_score=match.get('percentage', 50),
                    match_explanation=f"نواقص: {match.get('missing')} | نصيحة: {match.get('action')}",
                    applied_at=datetime.utcnow()
                )
                db.session.add(new_app)
                processed_count += 1

                # 5. إرسال تنبيه تليجرام فوري (الوكيل يتحدث)
                if user.telegram_id:
                    job_msg = (
                        f"{rtl_char}🤖 <b>رادار جوبيني وجد لك فرصة!</b>\n\n"
                        f"💼 <b>الوظيفة:</b> {j['title']}\n"
                        f"🏢 <b>الشركة:</b> {j['company']}\n"
                        f"📊 <b>نسبة المطابقة:</b> {match.get('percentage')}%\n"
                        f"💡 <b>نصيحة الوكيل:</b> {match.get('action')}"
                    )
                    keyboard = {
                        "inline_keyboard": [[
                            {"text": "🔗 تفاصيل الوظيفة", "url": j['link']},
                            {"text": "📄 عرض في المنصة", "url": f"https://jobeni-sd.com/view-job/{job_obj.id}"}
                        ]]
                    }
                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

        user.last_agent_run = datetime.utcnow()
        db.session.commit()
        return f"Agent Logic Completed. Processed {processed_count} jobs for {user.username}.", 200
    except Exception as e:
        db.session.rollback()
        return f"Agent Error: {str(e)}", 500

@agent_bp.route('/generate-cover-letter/<int:cv_id>/<string:job_title>')
@login_required
def generate_cover_letter_view(cv_id, job_title):
    """واجهة توليد خطاب التغطية آلياً"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    
    letter = JobeniAgent.generate_professional_cover_letter(cv.extracted_text, job_title, "الجهة الموظفة")
    return jsonify({"cover_letter": letter})

