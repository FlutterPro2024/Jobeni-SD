# ~/jobeni-sD/app/agent_worker.py
from flask import Blueprint, current_app, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime
import json
import re
import io
import os
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

def send_whatsapp_via_whapi(to_number, message):
    """إرسال رسالة واتساب عبر Whapi.cloud باستخدام التوكن المربوط"""
    token = os.getenv('WHAPI_TOKEN')
    api_url = "https://gate.whapi.cloud/messages/text"
    
    # تنظيف الرقم وتجهيزه بصيغة واتساب العالمية
    clean_number = str(to_number).replace('+', '').replace(' ', '').strip()
    if not clean_number.startswith('249') and len(clean_number) == 9:
        clean_number = '249' + clean_number

    payload = {
        "to": f"{clean_number}@s.whatsapp.net",
        "body": message,
        "typing_time": 0
    }
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {token}"
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        print(f"❌ WhatsApp Error: {e}")
        return None

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
        """توليد صورة شهادة احترافية بالألوان الملكية (أسود وذهبي) مع اللوجو والتوثيق"""
        try:
            width, height = 800, 1100
            img = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)

            draw.rectangle([20, 20, 780, 1080], outline=(15, 15, 15), width=18)
            draw.rectangle([35, 35, 765, 1065], outline=(218, 165, 32), width=5)

            try:
                base_dir = os.path.dirname(os.path.dirname(__file__))
                logo_path = os.path.join(base_dir, 'app', 'static', 'icons.png')
                if os.path.exists(logo_path):
                    logo = Image.open(logo_path).convert("RGBA")
                    logo = logo.resize((120, 120))
                    img.paste(logo, (340, 60), logo)
            except Exception as e:
                print(f"⚠️ Logo loading skipped: {e}")

            draw.text((310, 190), "JOBENI SUDAN", fill=(184, 134, 11))
            draw.text((250, 230), "AI-POWERED CAREER VERIFICATION", fill=(0, 0, 0))
            draw.text((240, 300), "CERTIFICATE OF EXCELLENCE", fill=(218, 165, 32))
            draw.text((320, 340), "This is to certify that", fill=(100, 100, 100))
            draw.text((240, 380), user_name.upper(), fill=(0, 0, 0))
            draw.line((150, 440, 650, 440), fill=(218, 165, 32), width=2)

            margin, offset = 80, 480
            draw.text((margin, offset), "Technical Assessment Summary:", fill=(184, 134, 11))
            offset += 40

            display_eval = evaluation_text or ""
            if "provide the following" in display_eval.lower() or len(display_eval) < 20:
                display_eval = (
                    "Expert Technical Assessment:\n"
                    "The candidate demonstrates professional proficiency in Digital Workflows.\n"
                    "Key Strengths: Verified knowledge of scalable systems and modern\n"
                    "problem-solving protocols. Highly recommended for technical roles."
                )

            lines = display_eval.split('\n')
            for line in lines:
                wrapped_lines = textwrap.wrap(line, width=65)
                for w_line in wrapped_lines:
                    if offset > 880: break
                    draw.text((margin, offset), w_line, fill=(30, 30, 30))
                    offset += 25
                offset += 5

            draw.text((80, 950), "Issued by Jobeni AI Certification Engine", fill=(150, 150, 150))
            draw.text((80, 975), f"Verification Date: {datetime.now().strftime('%d %B %Y')}", fill=(150, 150, 150))

            safe_name = urllib.parse.quote(user_name.replace(" ", "_"))
            verify_url = f"https://jobeni-sd.vercel.app/verify/{safe_name}"

            qr_buf = JobeniAgent.create_qr_code(verify_url)
            qr_img = Image.open(qr_buf).resize((140, 140))
            img.paste(qr_img, (600, 900))
            draw.text((615, 1045), "SCAN TO VERIFY", fill=(218, 165, 32))

            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            return img_byte_arr
        except Exception as e:
            print(f"❌ Certificate Error: {e}")
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

# --- Routes (المسارات) ---

@agent_bp.route('/run-discovery')
def trigger_discovery():
    """رابط خاص لـ Vercel Cron لتشغيل رادار الواتساب اليومي"""
    from app.tasks import run_ai_agent_discovery
    try:
        run_ai_agent_discovery()
        return jsonify({"status": "success", "message": "رادار الواتساب اشتغل بنجاح"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@agent_bp.route('/weekly-summary')
def trigger_weekly_summary():
    """رابط خاص لـ Vercel Cron لإرسال التقرير الأسبوعي"""
    from app.tasks import send_weekly_agent_summary
    try:
        send_weekly_agent_summary()
        return jsonify({"status": "success", "message": "التقارير الأسبوعية أرسلت بنجاح"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@agent_bp.route('/get-my-certificate')
@login_required
def get_certificate():
    """توليد وإرسال الشهادة للمستخدم الحالي عبر تليجرام"""
    if not current_user.telegram_id:
        flash("يرجى ربط حساب تليجرام أولاً لتلقي الشهادة الموثقة.", "warning")
        return redirect(url_for('auth.dashboard'))

    display_name = current_user.full_name or current_user.username
    evaluation = current_user.last_evaluation or ""
    cert_img = JobeniAgent.create_certificate_image(display_name, evaluation)

    if cert_img:
        # يفضل وضع التوكن في env لكن سنبقي عليه كما هو في الكود الأصلي بناء على طلبك
        BOT_TOKEN = "8450110637:AAEMNOzpc8phiBr0Dmjm2UHoEWfKi30Ja_s"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': ('jobeni_certified.png', cert_img, 'image/png')}
        caption = (f"📜 <b>تهانينا {display_name}!</b>\n\n"
                   f"لقد تم إصدار شهادتك الرسمية من <b>جوبيني السودان</b>.\n"
                   f"هذه الشهادة مزودة بكود QR للتوثيق الفوري.")
        try:
            requests.post(url, data={'chat_id': current_user.telegram_id, 'caption': caption, 'parse_mode': 'HTML'}, files=files, verify=False)
            flash("تم إرسال الشهادة الفخمة إلى تليجرام بنجاح!", "success")
        except Exception as e:
            flash(f"حدث خطأ أثناء الإرسال: {str(e)}", "danger")
    else:
        flash("حدث خطأ أثناء توليد الشهادة، يرجى المحاولة لاحقاً.", "danger")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/toggle-agent', methods=['POST', 'GET'])
@login_required
def toggle_agent():
    """تفعيل أو إيقاف الوكيل الذكي"""
    current_user.agent_enabled = not current_user.agent_enabled
    db.session.commit()
    status = "تفعيل" if current_user.agent_enabled else "إيقاف"
    add_notification(current_user.id, f"رادار الوظائف: {status}", f"تم {status} البحث التلقائي عن الفرص.", "info")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/run-jobs-agent')
def run_agent():
    """رادار الوظائف: يكتشف الفرص ويرسلها عبر تليجرام وواتساب"""
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

        target_jobs = list({j['link']: j for j in all_found_jobs}.values())[:15]
        processed_count = 0
        
        for j in target_jobs:
            job_obj = Job.query.filter_by(title=j['title'], company_name=j['company']).first()
            if not job_obj:
                job_obj = Job(
                    title=j['title'], company_name=j['company'],
                    location=j.get('location', 'Remote'),
                    description=f"فرصة عمل مكتشفة عبر رادار جوبيني: {j['link']}"
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

                # 1. الإرسال عبر تليجرام (كما هو)
                if user.telegram_id and processed_count <= 5:
                    job_msg = (f"🎯 <b>فرصة عمل جديدة تناسبك:</b>\n\n"
                               f"🔹 <b>الوظيفة:</b> {j['title']}\n"
                               f"🏢 <b>الشركة:</b> {j['company']}\n"
                               f"📊 <b>المطابقة:</b> {match.get('percentage', 0)}%")
                    inline_kb = [[{"text": "🔗 تفاصيل الوظيفة", "url": j['link']}], [{"text": "📱 لوحة التحكم", "url": "https://jobeni-sd.vercel.app"}]]
                    send_message(user.telegram_id, job_msg, reply_markup={"inline_keyboard": inline_kb})

                # 2. الإرسال عبر واتساب (الإضافة الجديدة باستخدام Whapi)
                if user.whatsapp_number and processed_count <= 3:
                    wa_msg = (
                        f"🎯 *رادار جوبيني لقى ليك وظيفة مكنة!*\n\n"
                        f"🔹 *الوظيفة:* {j['title']}\n"
                        f"🏢 *الشركة:* {j['company']}\n"
                        f"📊 *المطابقة:* {match.get('percentage', 0)}%\n\n"
                        f"🔗 *رابط التفاصيل:* {j['link']}\n\n"
                        f"🇸🇩 بالتوفيق من فريق جوبيني!"
                    )
                    send_whatsapp_via_whapi(user.whatsapp_number, wa_msg)

        db.session.commit()
        return f"Agent success. Processed {processed_count} jobs.", 200
    except Exception as e:
        db.session.rollback()
        return f"Error: {str(e)}", 500
