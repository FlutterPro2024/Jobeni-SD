# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint, current_app, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
import json
import re
import random
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
        """تحليل ذكي عميق للمطابقة بين السي في والوظيفة باستخدام AI"""
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
            res = openrouter_ai.get_ai_response(prompt, temperature=0.1)
            # فك التعليقة لو الرد فيه رسالة الضغط
            if "تحت ضغط شديد" in res:
                return {"percentage": 70, "missing": "جاري التحليل لاحقاً", "action": "الوكيل يرى أن تخصصك مناسب، قدم الآن!"}
            
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"percentage": 65, "missing": "مهارات تقنية محددة", "action": "حدث سيرتك لتناسب الوصف"}
        except:
            return {"percentage": 50, "missing": "تعذر التحليل", "action": "راجع المتطلبات يدوياً"}

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
    """تشغيل الوكيل كـ 'رادار عالمي' (20 وظيفة: السودان + الخليج + عالمي)"""
    try:
        # اختيار مستخدم عشوائي مفعل لديه الوكيل
        user = User.query.filter_by(agent_enabled=True).order_by(db.func.random()).first()
        if not user:
            return "No active agents found.", 200

        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
        if not cv:
            return f"User {user.username} has no CV.", 200

        # تحديد الكلمات البحثية (تخصص المستخدم)
        profession = user.agent_query or cv.profession or "وظائف احترافية"

        # مصفوفة البحث المتعدد (عالمي + إقليمي + محلي)
        search_queries = [
            f"{profession} jobs remote worldwide",
            f"{profession} jobs in UAE Saudi Arabia Qatar",
            f"{profession} jobs in Sudan"
        ]

        all_found_jobs = []
        for query in search_queries:
            search_results = serper_searcher.search_jobs(query)
            all_found_jobs.extend(search_results.get('jobs', []))

        # إزالة التكرار بناءً على الرابط وجلب أول 20 فقط
        unique_jobs = {j['link']: j for j in all_found_jobs}.values()
        target_jobs = list(unique_jobs)[:20]

        processed_count = 0
        rtl_char = "\u200f" # لضبط العربي في تليجرام

        for j in target_jobs:
            # 1. فحص هل الوظيفة موجودة في قاعدة البيانات؟
            job_obj = Job.query.filter_by(title=j['title'], company_name=j['company']).first()
            if not job_obj:
                job_location = j.get('location', 'Global/Remote')
                job_obj = Job(
                    title=j['title'],
                    company_name=j['company'],
                    location=job_location,
                    description=f"مصدر الوظيفة: {j['link']}"
                )
                db.session.add(job_obj)
                db.session.flush()

            # 2. فحص هل تم اقتراح الوظيفة للمستخدم سابقاً؟
            existing_app = Application.query.filter_by(user_id=user.id, job_id=job_obj.id).first()
            if not existing_app:
                # 3. تحليل المطابقة السريع
                match = JobeniAgent.calculate_match_percentage(cv.extracted_text, j['title'], j['company'])

                # 4. حفظ الاقتراح
                new_app = Application(
                    user_id=user.id,
                    job_id=job_obj.id,
                    status='suggested',
                    match_score=match.get('percentage', 60),
                    match_explanation=f"نواقص: {match.get('missing')} | نصيحة: {match.get('action')}",
                    applied_at=datetime.utcnow()
                )
                db.session.add(new_app)
                processed_count += 1

                # 5. تنبيه تليجرام (نرسل تفاصيل أول 5 والبقية كإشعار إجمالي لتجنب الحظر)
                if user.telegram_id and processed_count <= 5:
                    flag = "🇸🇩" if "Sudan" in job_obj.location else "🌎"
                    job_msg = (
                        f"{rtl_char}🎯 <b>فرصة عمل {flag}: {j['title']}</b>\n"
                        f"🏢 <b>الشركة:</b> {j['company']}\n"
                        f"📍 <b>الموقع:</b> {job_obj.location}\n"
                        f"📊 <b>المطابقة:</b> {match.get('percentage')}%\n"
                        f"💡 <b>نصيحة:</b> {match.get('action')}"
                    )
                    keyboard = {
                        "inline_keyboard": [[
                            {"text": "🔗 التقديم الآن", "url": j['link']},
                            {"text": "📄 لوحة التحكم", "url": f"https://jobeni-sd.vercel.app/dashboard"}
                        ]]
                    }
                    send_message(user.telegram_id, job_msg, reply_markup=keyboard)

        # رسالة ختامية لتليجرام إذا وجدت وظائف كثيرة
        if user.telegram_id and processed_count > 5:
            send_message(user.telegram_id, f"✅ تم العثور على {processed_count - 5} وظائف إضافية تناسبك عالمياً ومحلياً. راجع المنصة!")

        user.last_agent_run = datetime.utcnow()
        db.session.commit()
        return f"Done: Processed {processed_count} global/local jobs for {user.username}.", 200

    except Exception as e:
        db.session.rollback()
        return f"Agent Error: {str(e)}", 500

@agent_bp.route('/generate-cover-letter/<int:cv_id>/<string:job_title>')
@login_required
def generate_cover_letter_view(cv_id, job_title):
    """توليد الـ Cover Letter بناءً على السي في المرفوع"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    letter = JobeniAgent.generate_professional_cover_letter(cv.extracted_text, job_title, "الجهة الموظفة")
    return jsonify({"cover_letter": letter})
