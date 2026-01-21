# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint, current_app, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
import json
import re
import io
import textwrap
import urllib.parse
from app.models import User, CV, db, Job, Application
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification
from app.serper_search import serper_searcher
from app.telegram_bot import send_message
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests

agent_bp = Blueprint('agent', __name__)

# مصفوفة بيانات متجر المهارات (مصادر التعلم)
SKILLS_RESOURCES = {
    "Python": {"title": "دورة Python كاملة - Elzero", "url": "https://www.youtube.com/playlist?list=PLDoPjvoNmBAyE_gei5dSy8qeBCSuQxe9z"},
    "Excel": {"title": "احترف الإكسيل - نضال الشامي", "url": "https://www.youtube.com/playlist?list=PL0fndWZpS87H97LzCIn6z09T_S9kSInw_"},
    "Management": {"title": "أساسيات الإدارة", "url": "https://www.coursera.org/learn/management-foundations"},
    "English": {"title": "ZAmericanEnglish Course", "url": "https://www.youtube.com/c/ZAmericanEnglish"},
    "Marketing": {"title": "Digital Marketing - Google", "url": "https://learndigital.withgoogle.com/digitalgarage/course/digital-marketing"},
    "Communication": {"title": "مهارات التواصل الفعال", "url": "https://youtu.be/WIdYv86OthY"}
}

class JobeniAgent:

    @staticmethod
    def create_qr_code(link="https://jobeni-sd.vercel.app"):
        """توليد QR Code احترافي"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr

    @staticmethod
    def create_certificate_image(user_name, evaluation_text):
        """توليد صورة شهادة احترافية بالإنجليزية متوافقة مع Vercel وتدعم التوثيق"""
        try:
            width, height = 800, 1100
            # إنشاء خلفية بيضاء
            img = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)

            # إطار فخم بلون كحلي وذهبي
            draw.rectangle([20, 20, 780, 1080], outline=(0, 51, 102), width=15)
            draw.rectangle([35, 35, 765, 1065], outline=(218, 165, 32), width=3)

            # العناوين (ملاحظة: تيرمكس قد يحتاج مسار خطوط محدد، هنا نستخدم الخط الافتراضي)
            draw.text((200, 80), "JOBENI SUDAN - OFFICIAL CERTIFICATE", fill=(0, 51, 102))
            draw.text((60, 180), f"Candidate Name: {user_name}", fill=(0, 0, 0))
            draw.text((60, 210), "Status: AI Verified Expert", fill=(0, 102, 0))

            # خط فاصل ذهبي
            draw.line((60, 240, 740, 240), fill=(218, 165, 32), width=2)

            # تنظيف نص التقييم
            if not evaluation_text or len(evaluation_text) < 20:
                display_eval = ("Verification Summary: This candidate has cleared the Jobeni AI Interview.\n"
                                "Demonstrated proficiency in Industry Standards and Technical Skills.")
            else:
                display_eval = evaluation_text

            # توزيع النص داخل الشهادة مع التفاف الأسطر
            margin, offset = 60, 280
            lines = display_eval.split('\n')
            for line in lines:
                wrapped_lines = textwrap.wrap(line, width=70)
                for w_line in wrapped_lines:
                    if offset > 850: break
                    draw.text((margin, offset), w_line, fill=(0, 0, 0))
                    offset += 25
                offset += 10 

            # ملاحظة التخزين السحابي
            draw.text((60, 880), "Detailed evaluation is securely stored on Jobeni-SD Cloud.", fill=(100, 100, 100))

            # كيو أر التوثيق (Verification QR)
            safe_name = urllib.parse.quote(user_name.replace(" ", "_"))
            # تأكد من تغيير الرابط لرابط موقعك الحقيقي لاحقاً
            verify_url = f"https://jobeni-sd.vercel.app/verify/{safe_name}"

            qr_small_buf = JobeniAgent.create_qr_code(verify_url)
            qr_img = Image.open(qr_small_buf).resize((130, 130))
            img.paste(qr_img, (620, 900))
            draw.text((635, 1035), "Scan to Verify", fill=(0, 51, 102))

            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            return img_byte_arr
        except Exception as e:
            print(f"❌ Error drawing certificate: {e}")
            return None

    @staticmethod
    def calculate_match_percentage(cv_text, job_title, job_desc):
        """تحليل ذكي عميق للمطابقة بين السي في والوظيفة باستخدام AI"""
        prompt = f"""
        Act as an Expert AI Recruiter. Compare this CV with Job Details.
        Job: {job_title} | CV: {cv_text[:1200]}
        Return ONLY JSON: {{"percentage": 0-100, "missing": "skills", "action": "advice", "is_fit": bool}}
        """
        try:
            res = openrouter_ai.get_ai_response(prompt, temperature=0.1)
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match: return json.loads(match.group())
            return {"percentage": 65, "missing": "مهارات تقنية", "action": "حدث سيرتك لتناسب الوصف"}
        except:
            return {"percentage": 50, "missing": "تعذر التحليل", "action": "راجع المتطلبات يدوياً"}

    @staticmethod
    def get_skill_suggestions(missing_text):
        """اقتراح مصادر تعلم بناءً على النواقص"""
        suggestions = []
        for skill, data in SKILLS_RESOURCES.items():
            if skill.lower() in missing_text.lower():
                suggestions.append(data)
        return suggestions[:2]

# --- Routes (المسارات) ---

@agent_bp.route('/get-my-certificate')
@login_required
def get_certificate():
    """توليد وإرسال الشهادة للمستخدم الحالي عبر تليجرام"""
    if not current_user.telegram_id:
        flash("يرجى ربط حساب تليجرام أولاً من لوحة التحكم لتلقي الشهادة.", "warning")
        return redirect(url_for('auth.dashboard'))

    display_name = current_user.full_name or current_user.username
    evaluation = current_user.last_evaluation or ""

    cert_img = JobeniAgent.create_certificate_image(display_name, evaluation)

    if cert_img:
        BOT_TOKEN = "8450110637:AAEMNOzpc8phiBr0Dmjm2UHoEWfKi30Ja_s"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': ('jobeni_certified.png', cert_img, 'image/png')}
        caption = f"📜 تهانينا {display_name}!\nلقد تم إصدار شهادتك الرسمية الموثقة من جوبيني بنجاح.\n\nيمكن لأصحاب العمل مسح الكود للتأكد من صحة بياناتك."
        try:
            requests.post(url, data={'chat_id': current_user.telegram_id, 'caption': caption}, files=files, verify=False)
            flash("تم إرسال الشهادة الموثقة إلى حسابك في تليجرام بنجاح!", "success")
        except Exception as e:
            flash(f"حدث خطأ أثناء الإرسال: {str(e)}", "danger")
    else:
        flash("حدث خطأ أثناء توليد الشهادة، حاول مرة أخرى.", "danger")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/toggle-agent', methods=['POST', 'GET'])
@login_required
def toggle_agent():
    """تفعيل أو إيقاف الوكيل الذكي"""
    current_user.agent_enabled = not current_user.agent_enabled
    db.session.commit()
    status = "تفعيل" if current_user.agent_enabled else "إيقاف"
    add_notification(current_user.id, f"الوكيل الذكي: {status}", f"تم {status} رادار البحث عن وظائف تلقائياً.", "info")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/run-jobs-agent')
def run_agent():
    """تشغيل الوكيل كـ 'رادار عالمي' لجلب وظائف حقيقية ومطابقتها للمستخدمين النشطين"""
    try:
        user = User.query.filter_by(agent_enabled=True).order_by(db.func.random()).first()
        if not user: return "No active agents found.", 200

        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
        if not cv: return f"No CV found for {user.username}.", 200

        profession = user.agent_query or cv.profession or "Professional Jobs"
        search_queries = [f"{profession} jobs worldwide", f"{profession} remote jobs"]

        all_found_jobs = []
        for query in search_queries:
            search_results = serper_searcher.search_jobs(query)
            all_found_jobs.extend(search_results.get('jobs', []))

        # إزالة التكرار وأخذ أول 15 وظيفة
        target_jobs = list({j['link']: j for j in all_found_jobs}.values())[:15]
        processed_count = 0
        for j in target_jobs:
            job_obj = Job.query.filter_by(title=j['title'], company_name=j['company']).first()
            if not job_obj:
                job_obj = Job(
                    title=j['title'],
                    company_name=j['company'],
                    location=j.get('location', 'Remote'),
                    description=f"Job Opportunity found by Jobeni Radar: {j['link']}"
                )
                db.session.add(job_obj)
                db.session.flush()

            if not Application.query.filter_by(user_id=user.id, job_id=job_obj.id).first():
                match = JobeniAgent.calculate_match_percentage(cv.extracted_text, j['title'], j['company'])
                db.session.add(Application(
                    user_id=user.id, job_id=job_obj.id, status='suggested',
                    match_score=match.get('percentage', 60),
                    match_explanation=f"Missing: {match.get('missing')}",
                    applied_at=datetime.utcnow()
                ))
                processed_count += 1

                # إرسال إشعار تليجرام لأول 5 وظائف مناسبة
                if user.telegram_id and processed_count <= 5:
                    job_msg = (f"🎯 <b>فرصة عمل جديدة وجدها الرادار:</b>\n\n"
                               f"🔹 <b>الوظيفة:</b> {j['title']}\n"
                               f"🏢 <b>الشركة:</b> {j['company']}\n"
                               f"📊 <b>نسبة المطابقة:</b> {match.get('percentage', 0)}%")
                    inline_kb = [
                        [{"text": "🔗 عرض وتفاصيل الوظيفة", "url": j['link']}],
                        [{"text": "📱 لوحة تحكم جوبيني", "url": "https://jobeni-sd.vercel.app"}]
                    ]
                    send_message(user.telegram_id, job_msg, reply_markup={"inline_keyboard": inline_kb})

        user.last_agent_run = datetime.utcnow()
        db.session.commit()
        return f"Agent run complete. Processed {processed_count} jobs for {user.username}.", 200
    except Exception as e:
        db.session.rollback()
        return f"Error: {str(e)}", 500
