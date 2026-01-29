# ~/jobeni-sD/app/telegram_bot.py
import requests, os, re, json, time, io, urllib3
from flask import Blueprint, request, jsonify, current_app
from app.openrouter_ai import openrouter_ai
from gtts import gTTS
import speech_recognition as sr
from pydub import AudioSegment

# تعطيل تحذيرات الـ SSL لضمان العمل في بيئة تيرمكس و Vercel
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8450110637:AAEMNOzpc8phiBr0Dmjm2UHoEWfKi30Ja_s"
telegram_bp = Blueprint('telegram', __name__)
user_sessions = {}

# --- وظائف المساعدة الإضافية لضمان عدم حدوث Error ---

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

def send_document(chat_id, document_bytes, caption=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    if hasattr(document_bytes, 'seek'): document_bytes.seek(0)
    files = {'document': ('Jobeni_Report.pdf', document_bytes)}
    try:
        return requests.post(url, data={'chat_id': chat_id, 'caption': caption}, files=files, verify=False).json()
    except Exception as e:
        print(f"❌ Document Send Error: {e}")
        return None

def send_voice_response(chat_id, text, lang='ar'):
    try:
        clean_text = re.sub(r'<[^>]+>', '', text)[:300]
        tts_lang = 'en' if lang == 'English' else 'ar'
        tts = gTTS(text=clean_text, lang=tts_lang)
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        voice_io.seek(0)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVoice"
        files = {'voice': ('reply.ogg', voice_io, 'audio/ogg')}
        requests.post(url, data={'chat_id': chat_id}, files=files, timeout=50, verify=False)
    except Exception as e:
        print(f"❌ Voice Output Error: {e}")

# --- معالجة الصوت (تحويل الصوت إلى نص) ---

def convert_voice_to_text(file_id):
    try:
        file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}", verify=False).json()
        file_path = file_info['result']['file_path']
        voice_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        voice_data = requests.get(voice_url, verify=False).content
        ogg_io = io.BytesIO(voice_data)
        audio = AudioSegment.from_ogg(ogg_io)
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="ar-SA")
            return text
    except Exception as e:
        print(f"❌ Speech Recognition Error: {e}")
        return "❌ نعتذر، لم أتمكن من فهم التسجيل الصوتي."

# --- المنطق الرئيسي للبوت ---

def handle_telegram_webhook(data):
    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        data_payload = callback["data"]
        if data_payload.startswith("lang_"):
            selected_lang = "English" if "en" in data_payload else "العربية"
            start_interview(chat_id, selected_lang)
        return

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        if "voice" in message:
            send_message(chat_id, "⏳ <i>جاري معالجة صوتك...</i>")
            voice_text = convert_voice_to_text(message["voice"]["file_id"])
            if voice_text and not voice_text.startswith("❌"):
                process_logic(chat_id, voice_text)
            else:
                send_message(chat_id, voice_text)
            return
        if "text" in message:
            process_logic(chat_id, message["text"])

def start_interview(chat_id, lang):
    from app.models import User
    user = User.query.filter_by(telegram_id=str(chat_id)).first()
    
    # تحديد هدف المقابلة بناءً على نوع الحساب (منحة أو وظيفة)
    if user and user.role == 'scholarship_seeker':
        job = user.agent_query or "Academic Scholarship Candidate"
        context = "Academic Admission Interview"
    else:
        job = user.agent_query if (user and user.agent_query) else "Cloud Solutions Architect"
        context = "Professional Job Interview"

    user_sessions[chat_id] = {
        "mode": "interview",
        "job": job,
        "history": [],
        "question_count": 1,
        "lang": lang,
        "role": user.role if user else 'jobseeker'
    }

    prompt = f"Start a {context} for {job}. Ask question #1 (Level: Easy). Conduct entirely in {lang}."
    ai_q = openrouter_ai.get_ai_response(prompt)

    msg = f"🎙️ <b>Started: {job}</b>\n🌐 Language: {lang}\n━━━━━━━━━━━━━━\nQ [1/5]"
    if lang == "العربية":
        type_label = "مقابلة منحة" if (user and user.role == 'scholarship_seeker') else "مقابلة وظيفة"
        msg = f"🎙️ <b>بدأت {type_label}: {job}</b>\n🌐 اللغة: {lang}\n━━━━━━━━━━━━━━\nالسؤال [1/5]"

    send_message(chat_id, f"{msg}\n\n{ai_q}")
    send_voice_response(chat_id, ai_q, lang=lang)

def process_logic(chat_id, text):
    from app.models import User, db
    from app.agent_worker import JobeniAgent

    # البحث عن المستخدم بالرقم التعريفي للتليجرام
    user = User.query.filter(User.telegram_id == str(chat_id)).first()

    # 1. أوامر النظام
    if text.startswith("/start"):
        if user:
            role_text = "باحث عن منح 🎓" if user.role == "scholarship_seeker" else "عضو في جوبيني 🤖"
            welcome_msg = f"مرحباً بك مجدداً يا {user.username}!\nأنت مسجل كـ: {role_text}\n\nاستخدم /interview للبدء أو /certified للحصول على شهادتك."
        else:
            welcome_msg = "🤖 Welcome to Jobeni! \nلم نتمكن من العثور على حساب مرتب بهذا الرقم.\n\n💡 لربط الحساب: أرسل اسم المستخدم الخاص بك في الموقع مسبوقاً بكلمة 'ربط' (مثال: ربط ahmed2026)"
        send_message(chat_id, welcome_msg)

    # ميزة الربط اليدوي للأمان
    elif text.startswith("ربط"):
        target_username = text.replace("ربط", "").strip()
        found_user = User.query.filter_by(username=target_username).first()
        if found_user:
            found_user.telegram_id = str(chat_id)
            db.session.commit()
            send_message(chat_id, f"✅ تم ربط الحساب بنجاح يا {found_user.username}!\nنوع الحساب: {found_user.role}")
        else:
            send_message(chat_id, "❌ لم نجد مستخدم بهذا الاسم في المنصة.")

    elif text.startswith("/interview") or "مقابلة" in text:
        if not user:
            send_message(chat_id, "⚠️ يجب ربط حسابك أولاً لتتمكن من إجراء المقابلة وحفظ النتائج.")
            return
        keyboard = {
            "inline_keyboard": [[
                {"text": "العربية 🇸🇩", "callback_data": "lang_ar"},
                {"text": "English 🇬🇧", "callback_data": "lang_en"}
            ]]
        }
        send_message(chat_id, "الرجاء اختيار لغة المقابلة | Please select language:", reply_markup=keyboard)

    elif text.startswith("/certified"):
        if user and user.last_evaluation:
            send_message(chat_id, "📜 <i>جاري استخراج شهادتك الموثقة...</i>")
            display_name = user.full_name or user.username
            cert_img = JobeniAgent.create_certificate_image(display_name, user.last_evaluation)
            if cert_img:
                caption = f"📜 تهانينا {display_name}!\nلقد اجتزت التقييم بنجاح."
                send_photo(chat_id, cert_img, caption=caption)
            else:
                send_message(chat_id, "❌ حدث خطأ في إنشاء صورة الشهادة.")
        else:
            send_message(chat_id, "⚠️ لا يوجد تقييم مسجل. ابدأ مقابلة أولاً عبر /interview")

    # 2. إدارة جلسة المقابلة النشطة
    elif chat_id in user_sessions:
        session = user_sessions[chat_id]
        lang = session['lang']

        if any(x in text.lower() for x in ["خلاص", "إنهاء", "done", "finish"]):
            session['question_count'] = 6

        if session['question_count'] >= 5:
            finish_msg = "🏁 Analyzing..." if lang == "English" else "🏁 جاري تحليل الأداء..."
            send_message(chat_id, finish_msg)

            cert_prompt = f"Analyze this interview for {session['job']}: {session['history']}. Provide a professional assessment starting with 'Expert Assessment:'."
            certificate = openrouter_ai.get_ai_response(cert_prompt)

            if user:
                user.last_evaluation = certificate
                db.session.commit()
                display_name = user.full_name or user.username
                cert_img = JobeniAgent.create_certificate_image(display_name, certificate)
                send_photo(chat_id, cert_img, "📜 Official Certificate Generated!")

            del user_sessions[chat_id]
        else:
            session['question_count'] += 1
            count = session['question_count']
            levels = {2: "Easy", 3: "Medium", 4: "Advanced", 5: "Hardcore"} if lang == "English" else {2: "سهل", 3: "متوسط", 4: "متقدم", 5: "معقد جداً"}
            icons = {2: "🟢", 3: "🟡", 4: "🟠", 5: "🔴"}

            session['history'].append(f"User: {text}")
            next_prompt = f"Ask next question for {session['job']} (Difficulty: {levels[count]}) in {lang}."
            ai_next = openrouter_ai.get_ai_response(next_prompt)

            header = f"{icons[count]} <b>Question [{count}/5]</b>" if lang == "English" else f"{icons[count]} <b>السؤال [{count}/5]</b>"
            send_message(chat_id, f"{header}\n\n{ai_next}")
            send_voice_response(chat_id, ai_next, lang=lang)

    else:
        # رد ذكاء اصطناعي عام
        resp = openrouter_ai.get_ai_response(text)
        send_message(chat_id, resp)
        send_voice_response(chat_id, resp)

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if data: handle_telegram_webhook(data)
    return jsonify({"status": "ok"}), 200

