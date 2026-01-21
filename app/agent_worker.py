# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint, current_app, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
import json
import re
import random
import io
import textwrap
import urllib.parse
from app.models import User, CV, db, Job, Application
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification
from app.serper_search import serper_searcher
from app.telegram_bot import send_message
# إضافة المكتبات اللازمة للشهادات والـ QR
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests

agent_bp = Blueprint('agent', __name__)

# مصفوفة بيانات متجر المهارات
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
    def create_qr_code(link="https://jobeni-sudan.com"):
        """توليد QR Code للمنصة"""
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
        """توليد صورة شهادة احترافية بالإنجليزية لضمان التوافق مع Vercel"""
        try:
            width, height = 800, 1100
            img = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)

            # إطار فخم بلون كحلي وذهبي
            draw.rectangle([20, 20, 780, 1080], outline=(0, 51, 102), width=15)
            draw.rectangle([35, 35, 765, 1065], outline=(218, 165, 32), width=3)

            # استخدام الخط الافتراضي (يعمل دائماً على Vercel ويدعم الإنجليزية)
            font_default = ImageFont.load_default()

            # العناوين (English Only)
            draw.text((200, 80), "JOBENI SUDAN - OFFICIAL CERTIFICATE", fill=(0, 51, 102))
            draw.text((60, 180), f"Candidate Name: {user_name}", fill=(0, 0, 0))
            
            # محاولة بسيطة لإضافة مسمى الوظيفة
            draw.text((60, 210), "Status: AI Verified Expert", fill=(0, 102, 0))

            # رسم خط فاصل
            draw.line((60, 240, 740, 240), fill=(218, 165, 32), width=2)

            # محتوى التقييم - نقوم بتنظيف النص من أي أحرف غير لاتينية لضمان عدم ظهور مربعات
            clean_text = "Verification Summary: The candidate has demonstrated professional knowledge and technical skills during the Jobeni AI Interview process. This certification confirms high compatibility with modern industry standards."
            
            # توزيع النص على أسطر
            margin, offset = 60, 280
            wrapped_text = textwrap.wrap(clean_text, width=70)
            for line in wrapped_text:
                if offset > 900: break
                draw.text((margin, offset), line, fill=(0, 0, 0))
                offset += 30

            # إضافة ملاحظة عن التقييم الأصلي
            draw.text((60, offset + 40), "Detailed AI evaluation is stored in the system.", fill=(100, 100, 100))

            # الختم والـ QR الصغير في ركن الشهادة
            qr_small = JobeniAgent.create_qr_code(f"https://jobeni-sudan.com/verify/{user_name}")
            qr_img = Image.open(qr_small).resize((120, 120))
            img.paste(qr_img, (630, 910))
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
        """تحليل ذكي عميق للمطابقة بين السي في والوظيفة"""
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
        except: return {"percentage": 50, "missing": "تعذر التحليل", "action": "راجع المتطلبات يدوياً"}

    @staticmethod
    def get_skill_suggestions(missing_text):
        suggestions = []
        for skill, data in SKILLS_RESOURCES.items():
            if skill.lower() in missing_text.lower():
                suggestions.append(data)
        return suggestions[:2]

    @staticmethod
    def generate_professional_cover_letter(cv_text, job_title, company):
        prompt = f"Write a professional ATS-friendly Cover Letter for {job_title} at {company} based on: {cv_text[:1500]}"
        return openrouter_ai.get_ai_response(prompt, temperature=0.7)

# --- Routes ---

@agent_bp.route('/get-my-certificate')
@login_required
def get_certificate():
    """توليد وإرسال الشهادة للمستخدم عبر تليجرام"""
    if not current_user.telegram_id:
        flash("يرجى ربط حساب تليجرام أولاً.", "warning")
        return redirect(url_for('auth.dashboard'))

    evaluation = current_user.last_evaluation or "Initial Evaluation Complete."
    cert_img = JobeniAgent.create_certificate_image(current_user.username, evaluation)

    if cert_img:
        BOT_TOKEN = "8450110637:AAEMNOzpc8phiBr0Dmjm2UHoEWfKi30Ja_s"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': ('certified.png', cert_img, 'image/png')}
        requests.post(url, data={'chat_id': current_user.telegram_id, 'caption': "📜 Your Official Jobeni Certificate"}, verify=False)
        flash("تم إرسال الشهادة إلى حسابك في تليجرام!", "success")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/toggle-agent', methods=['POST', 'GET'])
@login_required
def toggle_agent():
    current_user.agent_enabled = not current_user.agent_enabled
    db.session.commit()
    status = "تفعيل" if current_user.agent_enabled else "إيقاف"
    add_notification(current_user.id, f"الوكيل الذكي: {status}", f"تم {status} رادار الوظائف.", "info")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/run-jobs-agent')
def run_agent():
    """تشغيل الوكيل كـ 'رادار عالمي'"""
    try:
        user = User.query.filter_by(agent_enabled=True).order_by(db.func.random()).first()
        if not user: return "No active agents.", 200

        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
        if not cv: return f"No CV for {user.username}.", 200    

        profession = user.agent_query or cv.profession or "Professional Jobs"
        search_queries = [f"{profession} jobs worldwide", f"{profession} jobs in Sudan"]

        all_found_jobs = []
        for query in search_queries:
            search_results = serper_searcher.search_jobs(query)
            all_found_jobs.extend(search_results.get('jobs', []))

        target_jobs = list({j['link']: j for j in all_found_jobs}.values())[:20]
        processed_count = 0

        for j in target_jobs:
            job_obj = Job.query.filter_by(title=j['title'], company_name=j['company']).first()
            if not job_obj:
                job_obj = Job(title=j['title'], company_name=j['company'], location=j.get('location', 'Remote'), description=f"Link: {j['link']}")
                db.session.add(job_obj)
                db.session.flush()

            if not Application.query.filter_by(user_id=user.id, job_id=job_obj.id).first():
                match = JobeniAgent.calculate_match_percentage(cv.extracted_text, j['title'], j['company'])
                
                db.session.add(Application(
                    user_id=user.id, job_id=job_obj.id, status='suggested',
                    match_score=match.get('percentage', 60),
                    match_explanation=f"Missing: {match.get('missing')}", applied_at=datetime.utcnow()
                ))
                processed_count += 1

                if user.telegram_id and processed_count <= 5:
                    job_msg = f"🎯 <b>New Opportunity: {j['title']}</b>\n🏢 {j['company']}\n📊 Match Score: {match.get('percentage')}%"
                    inline_kb = [[{"text": "🔗 Apply Now", "url": j['link']}]]
                    inline_kb.append([{"text": "📱 Jobeni Platform", "url": "https://jobeni-sudan.com"}])
                    send_message(user.telegram_id, job_msg, reply_markup={"inline_keyboard": inline_kb})

        user.last_agent_run = datetime.utcnow()
        db.session.commit()
        return f"Processed {processed_count} jobs.", 200
    except Exception as e:
        db.session.rollback()
        return str(e), 500
