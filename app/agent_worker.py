# ~/jobeni-sD/app/agent_worker.py
import os
import re
import io
import json
import textwrap
import logging
import requests
import qrcode
import urllib.parse
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from flask import Blueprint, current_app, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# تم إضافة Scholarship هنا لضمان الحفظ في الجدول الجديد
from app.models import User, CV, db, Job, Application, AgentMemory, Notification, Scholarship
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification
from app.serper_search import serper_searcher
from app.telegram_bot import send_message

# إعداد الـ Logging السيادي لمراقبة الأداء
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JobeniAgent")

agent_bp = Blueprint('agent', __name__)

# --- مصفوفة المهارات والمصادر الذكية (Smart Learning) ---
SKILLS_RESOURCES = {
    "Python": {"title": "دورة Python كاملة - Elzero", "url": "https://www.youtube.com/playlist?list=PLDoPjvoNmBAyE_gei5dSy8qeBCSuQxe9z"},
    "Excel": {"title": "احترف الإكسيل - نضال الشامي", "url": "https://www.youtube.com/playlist?list=PL0fndWZpS87H97LzCIn6z09T_S9kSInw_"},
    "Management": {"title": "أساسيات الإدارة", "url": "https://www.coursera.org/learn/management-foundations"},
    "English": {"title": "ZAmericanEnglish Course", "url": "https://www.youtube.com/c/ZAmericanEnglish"},
    "Marketing": {"title": "Digital Marketing - Google", "url": "https://learndigital.withgoogle.com/digitalgarage/course/digital-marketing"},
    "Communication": {"title": "مهارات التواصل الفعال", "url": "https://youtu.be/WIdYv86OthY"}
}

# --- نظام الواتساب مع الـ Retry الذكي ---
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True
)
def send_whatsapp_via_whapi(to_number, message):
    """إرسال رسالة واتساب عبر Whapi مع نظام إعادة المحاولة ومحاكاة الكتابة"""
    token = os.getenv('WHAPI_TOKEN')
    api_url = "https://gate.whapi.cloud/messages/text"
    if not token:
        logger.error("❌ WHAPI_TOKEN مفقود في متغيرات البيئة")
        return None

    clean_number = str(to_number).replace('+', '').replace(' ', '').strip()
    if not clean_number.startswith('249') and len(clean_number) == 9:
        clean_number = '249' + clean_number

    payload = {
        "to": f"{clean_number}@s.whatsapp.net",
        "body": message,
        "typing_time": 2  # إعطاء طابع بشري (Writing...)
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {token}"
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"❌ WhatsApp Error: {e}")
        raise e

class JobeniAgent:
    """المحرك المركزي للوكيل الذكي والشهادات المعتمدة ورادار المنح"""

    @staticmethod
    def create_qr_code(link="https://jobeni-sd.vercel.app"):
        """توليد QR عالي الجودة مشفر بالهوية الشخصية"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="white")
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr

    @staticmethod
    def create_certificate_image(user_name, evaluation_text):
        """توليد الشهادة الملكية (أسود وذهبي) مع التوقيع الرقمي"""
        try:
            width, height = 850, 1100
            img = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)

            draw.rectangle([20, 20, 830, 1080], outline=(15, 15, 15), width=20)
            draw.rectangle([40, 40, 810, 1060], outline=(218, 165, 32), width=5)

            try:
                base_dir = os.path.dirname(os.path.dirname(__file__))
                logo_path = os.path.join(base_dir, 'app', 'static', 'icons.png')
                if os.path.exists(logo_path):
                    logo = Image.open(logo_path).convert("RGBA").resize((130, 130))
                    img.paste(logo, (360, 60), logo)
            except:
                pass

            draw.text((320, 200), "JOBENI SUDAN", fill=(184, 134, 11))
            draw.text((260, 240), "AI-POWERED CAREER VERIFICATION", fill=(0, 0, 0))
            draw.text((250, 310), "CERTIFICATE OF EXCELLENCE", fill=(218, 165, 32))
            draw.text((340, 350), "This is to certify that", fill=(100, 100, 100))

            draw.text((250, 390), user_name.upper(), fill=(0, 0, 0))
            draw.line((180, 450, 670, 450), fill=(218, 165, 32), width=3)

            margin, offset = 90, 490
            draw.text((margin, offset), "Technical Assessment Summary:", fill=(184, 134, 11))
            offset += 45

            display_eval = evaluation_text or "Candidate demonstrated high proficiency in modern professional workflows and AI integration."
            for line in display_eval.split('\n'):
                for w_line in textwrap.wrap(line, width=65):
                    if offset > 900: break
                    draw.text((margin, offset), w_line, fill=(40, 40, 40))
                    offset += 28
                offset += 8

            draw.text((90, 960), "Issued by Jobeni AI Engine v2.0", fill=(150, 150, 150))
            draw.text((90, 985), f"Verification Date: {datetime.now().strftime('%d %B %Y')}", fill=(150, 150, 150))

            verify_url = f"https://jobeni-sd.vercel.app/verify/{urllib.parse.quote(user_name)}"
            qr_img = Image.open(JobeniAgent.create_qr_code(verify_url)).resize((150, 150))
            img.paste(qr_img, (640, 910))

            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            return img_byte_arr
        except Exception as e:
            logger.error(f"❌ Certificate Generation Error: {e}")
            return None

    @staticmethod
    def calculate_match_strictly(cv_text, job_title, job_desc):
        """المحلل الصارم (ATS Matcher) للوظائف"""
        prompt = f"""
        Act as a HARSH Recruiter. Analyze match for: {job_title}.
        CV: {cv_text[:1500]}
        Job: {job_desc[:800]}
        Rules: - Penalize missing hard skills (-20%).
        Output JSON ONLY: {{"score": 0-100, "verdict": "Match/Reject", "missing": [], "notes": "concise feedback"}}
        """
        try:
            res = openrouter_ai.get_ai_response(prompt, temperature=0.1)
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match: return json.loads(match.group())
        except:
            pass
        return {"score": 0, "verdict": "Reject", "notes": "AI Analysis Failed"}

    @staticmethod
    def find_scholarships_strictly(user_context, query):
        """الوكيل الذكي للبحث عن المنح (Scholarship AI Agent)"""
        prompt = f"""
        Act as a Global Scholarship AI Agent. Find opportunities for: {query}
        User Academic Context: {user_context[:1500]}
        Tasks:
        1. Evaluate based on GPA, Field, and Eligibility for Sudanese.
        2. Assign Match Score (0-100%).
        3. Output exactly as JSON array of objects.

        Required JSON Format:
        [{{
          "title": "Scholarship Name",
          "university": "University Name",
          "level": "Undergraduate/Masters/PhD",
          "field": "Specialization",
          "country": "Host Country",
          "funding": "Full/Partial",
          "deadline": "YYYY-MM-DD",
          "match_score": 0-100,
          "notes": "Brief AI advice",
          "link": "Official URL"
        }}]
        """
        try:
            search_results = serper_searcher.search_jobs(f"{query} scholarship 2026 fully funded")
            web_context = str(search_results.get('jobs', []))
            full_prompt = f"{prompt}\n\nSearch Data: {web_context[:2000]}"
            res = openrouter_ai.get_ai_response(full_prompt, temperature=0.3)
            match = re.search(r'\[.*\]', res, re.DOTALL)
            if match: return json.loads(match.group())
        except Exception as e:
            logger.error(f"❌ Scholarship Search Error: {e}")
        return []

# --- المسارات الذكية (Routes) ---

@agent_bp.route('/run-jobs-agent')
def run_agent():
    """المحرك الرئيسي: رادار الوظائف والمنح الصارم"""
    try:
        user = User.query.filter_by(agent_enabled=True).order_by(db.func.random()).first()
        if not user: return "No active agents.", 200

        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
        context_text = cv.extracted_text if cv else "Generic student"

        matches_found = 0

        # --- حالة باحث عن منحة (مع الحفظ في جدول Scholarship الجديد) ---
        if user.role == 'scholarship_seeker':
            query = user.agent_query or "Global"
            scholarships = JobeniAgent.find_scholarships_strictly(context_text, query)
            for sch in scholarships:
                # تجنب التكرار بناءً على الرابط في جدول Scholarship
                existing = Scholarship.query.filter_by(official_link=sch['link']).first()
                if existing:
                    # إذا كانت المنحة موجودة، نتحقق هل تم إرسالها لهذا المستخدم مسبقاً في الذاكرة؟
                    if AgentMemory.query.filter_by(user_id=user.id, scholarship_id=existing.id).first():
                        continue

                score = sch.get('match_score', 0)
                if score >= 60:
                    # 1. حفظ المنحة في جدول Scholarship إذا كانت جديدة
                    if not existing:
                        new_sch_entry = Scholarship(
                            title=sch['title'],
                            university=sch.get('university'),
                            country=sch.get('country'),
                            field_of_study=sch.get('field'),
                            level=sch.get('level'),
                            funding_type=sch.get('funding'),
                            official_link=sch['link']
                        )
                        try:
                            if sch.get('deadline'):
                                new_sch_entry.deadline = datetime.strptime(sch['deadline'], '%Y-%m-%d')
                        except:
                            pass
                        db.session.add(new_sch_entry)
                        db.session.flush() # للحصول على ID المنحة
                        scholar_id = new_sch_entry.id
                    else:
                        scholar_id = existing.id

                    # 2. حفظ في ذاكرة الوكيل بربط الحقل الجديد scholarship_id
                    memory = AgentMemory(
                        user_id=user.id,
                        action='scholarship_found',
                        scholarship_id=scholar_id, # ربط الجدول الجديد
                        action_url=sch['link'],
                        feedback_notes=f"Match: {score}%",
                        score=score
                    )
                    db.session.add(memory)

                    msg = (
                        f"🎓 *بشارة منحة دراسية!* \n\n"
                        f"📌 {sch['title']}\n"
                        f"📊 المطابقة: {score}%\n"
                        f"🌍 البلد: {sch.get('country')}\n"
                        f"💰 التمويل: {sch.get('funding')}\n"
                        f"📅 التقديم: {sch.get('deadline')}\n\n"
                        f"🔗 {sch['link']}"
                    )

                    if user.telegram_id:
                        send_message(user.telegram_id, msg)
                    if user.whatsapp_number and score >= 85:
                        send_whatsapp_via_whapi(user.whatsapp_number, msg)

                    matches_found += 1
        # --- حالة باحث عن وظيفة ---
        else:
            query = user.agent_query or (cv.profession if cv else "Professional")
            search_results = serper_searcher.search_jobs(f"{query} jobs {user.agent_work_type}")
            jobs_pool = search_results.get('jobs', [])[:10]

            for j in jobs_pool:
                if AgentMemory.query.filter_by(user_id=user.id, job_id=str(j.get('title'))).first():
                    continue

                analysis = JobeniAgent.calculate_match_strictly(context_text, j['title'], j.get('snippet', ''))
                score = analysis.get('score', 0)

                if score >= user.agent_target_score:
                    memory = AgentMemory(user_id=user.id, action='sent', job_id=j['title'], feedback_notes=f"Score: {score}%", score=score)
                    db.session.add(memory)

                    if user.telegram_id:
                        msg = f"🎯 *فرصة مكنة:* {j['title']}\n🏢 {j['company']}\n📊 المطابقة: {score}%\n💡 {analysis.get('notes')}"
                        kb = {"inline_keyboard": [[{"text": "🔗 التقديم الآن", "url": j['link']}]]}
                        send_message(user.telegram_id, msg, reply_markup=kb)

                    if user.whatsapp_number and score >= 85:
                        wa_msg = f"🎯 *يا {user.username}، وظيفة لقطة!*\n\n📌 {j['title']}\n🏢 {j['company']}\n🔥 درجة المطابقة: {score}%\n\n🔗 {j['link']}"
                        send_whatsapp_via_whapi(user.whatsapp_number, wa_msg)

                    matches_found += 1

        user.last_agent_run = datetime.utcnow()
        db.session.commit()
        return f"Processed for {user.username}. Found: {matches_found}", 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Agent System Error: {e}")
        return f"Error: {str(e)}", 500

@agent_bp.route('/weekly-summary')
def weekly_summary_cron():
    """المحرك الذكي للتقارير الأسبوعية (وظائف + منح)"""
    try:
        users = User.query.filter_by(agent_enabled=True).all()
        processed_count = 0
        one_week_ago = datetime.utcnow() - timedelta(days=7)

        for user in users:
            memories = AgentMemory.query.filter(
                AgentMemory.user_id == user.id,
                AgentMemory.created_at >= one_week_ago,
                AgentMemory.action.in_(['sent', 'scholarship_found'])
            ).all()

            matches_count = len(memories)
            top_score = max([m.score for m in memories]) if memories else 0

            role_text = "المنح" if user.role == "scholarship_seeker" else "الوظائف"
            prompt = f"بصفتك مستشار مهني ذكي، اكتب ملخصاً أسبوعياً لمستخدم سوداني يبحث عن {role_text}. الفرص المكتشفة {matches_count}، أعلى مطابقة {top_score}%. استخدم لهجة سودانية دارجة مهذبة."
            ai_advice = openrouter_ai.get_ai_response(prompt, temperature=0.7)

            report_msg = (
                f"📊 *تقرير جوبيني الأسبوعي يا {user.username}* \n"
                f"━━━━━━━━━━━━━━━\n"
                f"🕵️‍♂️ *فرص {role_text} المكتشفة:* {matches_count}\n"
                f"🚀 *أعلى مطابقة:* {top_score}%\n"
                f"💡 *نصيحة الأسبوع:* {ai_advice}\n\n"
                f"🇸🇩 _معاً نصنع مستقبلك بذكاء_"
            )

            if user.whatsapp_number: send_whatsapp_via_whapi(user.whatsapp_number, report_msg)
            if user.telegram_id: send_message(user.telegram_id, report_msg)

            db.session.add(AgentMemory(user_id=user.id, action='weekly_report', feedback_notes=f"Sent summary"))
            processed_count += 1

        db.session.commit()
        return f"Weekly reports sent to {processed_count} users.", 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Weekly Summary Error: {e}")
        return f"Error: {str(e)}", 500

@agent_bp.route('/get-my-certificate')
@login_required
def get_certificate():
    """توليد وإرسال الشهادة الموثقة فوراً عبر تليجرام"""
    if not current_user.telegram_id:
        flash("يرجى ربط حساب تليجرام أولاً لاستلام الشهادة.", "warning")
        return redirect(url_for('auth.dashboard'))

    cert_img = JobeniAgent.create_certificate_image(current_user.full_name or current_user.username, current_user.last_evaluation)
    if cert_img:
        # تأكد من وجود TELEGRAM_BOT_TOKEN في .env
        BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        files = {'photo': ('jobeni_cert.png', cert_img, 'image/png')}
        caption = "📜 *شهادة اعتماد جوبيني AI*\nتم توثيق مهاراتك رقمياً لعام 2026."
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data={'chat_id': current_user.telegram_id, 'caption': caption, 'parse_mode': 'Markdown'}, files=files)
        flash("أبشر! الشهادة الموثقة أصبحت في جيبك (تليجرام).", "success")
    else:
        flash("حدث خطأ في توليد الشهادة.", "danger")
    return redirect(url_for('auth.dashboard'))

@agent_bp.route('/toggle-agent', methods=['POST', 'GET'])
@login_required
def toggle_agent():
    """تشغيل أو إيقاف الرادار"""
    current_user.agent_enabled = not current_user.agent_enabled
    db.session.commit()
    status = "نشط الآن" if current_user.agent_enabled else "متوقف"
    add_notification(current_user.id, "تحديث الرادار", f"حالة الوكيل الذكي: {status}", "info")
    flash(f"تم {status} رادار الفرص بنجاح.", "success")
    return redirect(url_for('auth.dashboard'))
