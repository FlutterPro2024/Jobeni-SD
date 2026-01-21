import requests, os, re, json, time, io, urllib3
from flask import Blueprint, request, jsonify, current_app
from app.openrouter_ai import openrouter_ai
from gtts import gTTS
import speech_recognition as sr
from pydub import AudioSegment

# تعطيل تحذيرات الـ SSL لضمان العمل في بيئة تيرمكس
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8450110637:AAEMNOzpc8phiBr0Dmjm2UHoEWfKi30Ja_s"
telegram_bp = Blueprint('telegram', __name__)

user_sessions = {}

# --- وظائف المساعدة (إرسال الرسائل، الصور، الصوت) ---

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    if reply_markup: payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=30, verify=False)
        return res.json()
    except Exception as e:
        print(f"❌ Telegram Send Error: {e}")
        return None

def send_photo(chat_id, photo_bytes, caption=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    if hasattr(photo_bytes, 'seek'): photo_bytes.seek(0)
    files = {'photo': ('image.png', photo_bytes, 'image/png')}
    try:
        return requests.post(url, data={'chat_id': chat_id, 'caption': caption}, files=files, verify=False).json()
    except Exception as e:
        print(f"❌ Photo Send Error: {e}")
        return None

def send_voice_response(chat_id, text):
    try:
        clean_text = re.sub(r'<[^>]+>', '', text)[:300]
        tts = gTTS(text=clean_text, lang='ar')
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        voice_io.seek(0)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVoice"
        files = {'voice': ('reply.ogg', voice_io, 'audio/ogg')}
        requests.post(url, data={'chat_id': chat_id}, files=files, timeout=50, verify=False)
    except Exception as e:
        print(f"❌ Voice Output Error: {e}")

# --- معالجة الصوت وتحويله لنص ---

def convert_voice_to_text(file_id):
    try:
        file_info_res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}", timeout=30, verify=False)
        file_info = file_info_res.json()
        if not file_info.get('ok'): return "❌ فشل الوصول للملف"
        file_path = file_info['result']['file_path']
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        audio_content = requests.get(file_url, timeout=60, verify=False).content

        # محاولة استخدام Google Recognition كخيار أساسي في تيرمكس
        return fallback_google_recognition(audio_content)
    except: return "⚠️ خطأ في معالجة الصوت"

def fallback_google_recognition(audio_content):
    try:
        ogg_io = io.BytesIO(audio_content)
        audio = AudioSegment.from_file(ogg_io, format="ogg")
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data_rec = recognizer.record(source)
            return recognizer.recognize_google(audio_data_rec, language="ar-SA")
    except: return None

# --- المنطق الرئيسي للبوت ---

def handle_telegram_webhook(data):
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        if "voice" in message:
            send_message(chat_id, "⏳ <i>أبشر، جاري معالجة صوتك...</i>")
            voice_text = convert_voice_to_text(message["voice"]["file_id"])
            if voice_text and not voice_text.startswith("❌"):
                send_message(chat_id, f"📝 <b>سمعتك بتقول:</b>\n\"{voice_text}\"")
                process_logic(chat_id, voice_text)
            return
        if "text" in message:
            process_logic(chat_id, message["text"])

def process_logic(chat_id, text):
    from app.models import User, db
    from app.agent_worker import JobeniAgent

    # 1. أوامر النظام
    if text.startswith("/start"):
        parts = text.split(" ")
        if len(parts) > 1:
            try:
                user_id = parts[1]
                user = db.session.get(User, int(user_id))
                if user:
                    user.telegram_id = str(chat_id)
                    db.session.commit()
                    send_message(chat_id, f"✅ <b>تم الربط بنجاح يا {user.username}!</b>\nأرسل /interview للمقابلة.")
                else: send_message(chat_id, "❌ حساب غير موجود.")
            except: send_message(chat_id, "⚠️ خطأ في الربط.")
        else:
            send_message(chat_id, "🤖 أهلاً بك في جوبيني! منصتك للتوظيف الذكي.\nأرسل /interview للمقابلة أو /qr لرابط المنصة.")

    elif text.startswith("/qr"):
        qr_img = JobeniAgent.create_qr_code("https://jobeni-sd.vercel.app")
        send_photo(chat_id, qr_img, "🔗 رابط منصة جوبيني السودان المعتمد")

    elif text.startswith("/certified") or "شهادة" in text:
        user = User.query.filter_by(telegram_id=str(chat_id)).first()
        if user and user.last_evaluation:
            send_message(chat_id, "⏳ جاري استخراج شهادتك الموثقة...")
            display_name = user.full_name or user.username
            cert_img = JobeniAgent.create_certificate_image(display_name, user.last_evaluation)
            send_photo(chat_id, cert_img, f"📜 شهادة اعتماد جوبيني الرقمية\nللمستخدم: {display_name}")
        else:
            send_message(chat_id, "⚠️ لا توجد شهادة محفوظة. يرجى إكمال مقابلة أولاً عبر /interview")

    # 2. نظام المقابلات
    elif text.startswith("/interview") or "مقابلة" in text:
        user = User.query.filter_by(telegram_id=str(chat_id)).first()
        job = user.agent_query if (user and user.agent_query) else "Cloud Solutions Architect"
        user_sessions[chat_id] = {"mode": "interview", "job": job, "history": []}
        ai_q = openrouter_ai.get_ai_response(f"ابدأ مقابلة لـ {job} بسؤال واحد فني باللغة العربية.")
        send_message(chat_id, f"🎙️ <b>بدأت المقابلة: {job}</b>\n\n{ai_q}")
        send_voice_response(chat_id, ai_q)

    # 3. إدارة جلسة المقابلة النشطة
    elif chat_id in user_sessions:
        session = user_sessions[chat_id]
        if any(x in text for x in ["خلاص", "إنهاء", "تم", "انتهيت"]):
            send_message(chat_id, "🏁 جاري تقييم أدائك وتوليد التقرير النهائي...")
            # إجبار الـ AI على الصيغة الاحترافية للشهادة
            cert_prompt = f"Analyze this interview for {session['job']}: {session['history']}. Provide a professional assessment in English starting with 'Expert Technical Assessment:' followed by 3 key strengths and a conclusion."
            certificate = openrouter_ai.get_ai_response(cert_prompt)

            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            if user:
                user.last_evaluation = certificate
                db.session.commit()
                display_name = user.full_name or user.username
                cert_img = JobeniAgent.create_certificate_image(display_name, certificate)
                send_photo(chat_id, cert_img, "📜 مبروك! لقد اجتزت المقابلة بنجاح وهذه شهادة اعتمادك.")
            del user_sessions[chat_id]
        else:
            session['history'].append(f"User: {text}")
            ai_next = openrouter_ai.get_ai_response(f"رد المرشح: {text}. قيم الرد باختصار باللغة العربية ثم اسأل السؤال الفني التالي.")
            send_message(chat_id, ai_next)
            send_voice_response(chat_id, ai_next)

    # 4. الاستشارة العامة
    else:
        resp = openrouter_ai.get_ai_response(text)
        send_message(chat_id, resp)
        send_voice_response(chat_id, resp)

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if data: handle_telegram_webhook(data)
    return jsonify({"status": "ok"}), 200
