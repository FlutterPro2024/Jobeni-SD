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

# --- وظائف المساعدة ---
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

def send_voice_response(chat_id, text, lang='ar'):
    try:
        clean_text = re.sub(r'<[^>]+>', '', text)[:300]
        # اختيار لغة النطق بناءً على اختيار المستخدم
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

# --- المنطق الرئيسي للبوت ---
def handle_telegram_webhook(data):
    # معالجة ضغطات الأزرار (선택 اللغة)
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
            send_message(chat_id, "⏳ <i>Processing voice...</i>")
            # نحتاج دوال convert_voice_to_text و fallback_google_recognition من الكود السابق
            from app.telegram_bot import convert_voice_to_text 
            voice_text = convert_voice_to_text(message["voice"]["file_id"])
            if voice_text and not voice_text.startswith("❌"):
                process_logic(chat_id, voice_text)
            return
        if "text" in message:
            process_logic(chat_id, message["text"])

def start_interview(chat_id, lang):
    from app.models import User
    user = User.query.filter_by(telegram_id=str(chat_id)).first()
    job = user.agent_query if (user and user.agent_query) else "Cloud Solutions Architect"
    
    user_sessions[chat_id] = {
        "mode": "interview", 
        "job": job, 
        "history": [],
        "question_count": 1,
        "lang": lang
    }
    
    prompt = f"Start a professional interview for {job}. Ask question #1 (Level: Very Easy). Conduct the interview entirely in {lang}."
    ai_q = openrouter_ai.get_ai_response(prompt)
    
    msg = f"🎙️ <b>Interview Started: {job}</b>\n🌐 Language: {lang}\n━━━━━━━━━━━━━━\nQ [1/5] - 🟢 Easy"
    if lang == "العربية":
        msg = f"🎙️ <b>بدأت المقابلة: {job}</b>\n🌐 اللغة: {lang}\n━━━━━━━━━━━━━━\nالسؤال [1/5] - 🟢 سهل"
        
    send_message(chat_id, f"{msg}\n\n{ai_q}")
    send_voice_response(chat_id, ai_q, lang=lang)

def process_logic(chat_id, text):
    from app.models import User, db
    from app.agent_worker import JobeniAgent

    # 1. أوامر النظام
    if text.startswith("/start"):
        # (منطق الربط كما هو في الكود السابق)
        send_message(chat_id, "🤖 Welcome to Jobeni! Use /interview to start.")

    elif text.startswith("/interview") or "مقابلة" in text:
        # عرض أزرار اختيار اللغة
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "العربية 🇸🇩", "callback_data": "lang_ar"},
                    {"text": "English 🇬🇧", "callback_data": "lang_en"}
                ]
            ]
        }
        send_message(chat_id, "الرجاء اختيار لغة المقابلة | Please select interview language:", reply_markup=keyboard)

    # 2. إدارة جلسة المقابلة النشطة
    elif chat_id in user_sessions:
        session = user_sessions[chat_id]
        lang = session['lang']
        
        if any(x in text.lower() for x in ["خلاص", "إنهاء", "done", "finish"]):
            session['question_count'] = 6 

        if session['question_count'] >= 5:
            finish_msg = "🏁 Analysing your performance..." if lang == "English" else "🏁 جاري تحليل الأداء..."
            send_message(chat_id, finish_msg)
            
            cert_prompt = f"Analyze this 5-question interview for {session['job']} conducted in {lang}: {session['history']}. Provide a professional assessment in English starting with 'Expert Technical Assessment:'."
            certificate = openrouter_ai.get_ai_response(cert_prompt)

            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            if user:
                user.last_evaluation = certificate
                db.session.commit()
                display_name = user.full_name or user.username
                cert_img = JobeniAgent.create_certificate_image(display_name, certificate)
                success_msg = "📜 Congratulations! You've passed." if lang == "English" else "📜 مبروك! لقد اجتزت بنجاح."
                send_photo(chat_id, cert_img, success_msg)
            del user_sessions[chat_id]
        else:
            session['question_count'] += 1
            count = session['question_count']
            levels = {2: "Easy", 3: "Medium", 4: "Advanced", 5: "Hardcore"} if lang == "English" else {2: "سهل", 3: "متوسط", 4: "متقدم", 5: "معقد جداً"}
            icons = {2: "🟢", 3: "🟡", 4: "🟠", 5: "🔴"}
            
            session['history'].append(f"User: {text}")
            next_prompt = f"Candidate's last answer: {text}. Now ask question #{count} for {session['job']}. Difficulty: {levels[count]}. Language: {lang}."
            ai_next = openrouter_ai.get_ai_response(next_prompt)
            
            header = f"{icons[count]} <b>Question [{count}/5] - {levels[count]}</b>" if lang == "English" else f"{icons[count]} <b>السؤال [{count}/5] - {levels[count]}</b>"
            send_message(chat_id, f"{header}\n\n{ai_next}")
            send_voice_response(chat_id, ai_next, lang=lang)

    else:
        resp = openrouter_ai.get_ai_response(text)
        send_message(chat_id, resp)
        send_voice_response(chat_id, resp)

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if data: handle_telegram_webhook(data)
    return jsonify({"status": "ok"}), 200
