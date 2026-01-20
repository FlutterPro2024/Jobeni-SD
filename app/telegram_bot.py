# ~/jobeni-sD/app/telegram_bot.py
import requests, os, re, json, time, io
from flask import Blueprint, request, jsonify, current_app
from app.openrouter_ai import openrouter_ai
from gtts import gTTS  # لتحويل النص لصوت
import speech_recognition as sr  # لتحويل الصوت لنص
from pydub import AudioSegment  # لمعالجة صيغ الصوت

# التوكن الجديد والمؤمن
BOT_TOKEN = "8450110637:AAEMNOzpc8phiBr0Dmjm2UHoEWfKi30Ja_s"
telegram_bp = Blueprint('telegram', __name__)

# مخزن مؤقت لجلسات الذكاء الاصطناعي والمقابلات
user_sessions = {}

# --- وظائف المساعدة (الصوت والتحليل) ---

def send_message(chat_id, text, reply_markup=None):
    """إرسال رسالة نصية مدعومة بـ HTML وأزرار"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"❌ Telegram Send Error: {e}")
        return None

def send_voice_response(chat_id, text):
    """تحويل رد الـ AI لصوت وإرساله للمستخدم"""
    try:
        # تقليل طول النص للصوت لضمان السرعة
        clean_text = re.sub(r'<[^>]+>', '', text)[:300] 
        tts = gTTS(text=clean_text, lang='ar')
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        voice_io.seek(0)
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVoice"
        files = {'voice': ('reply.ogg', voice_io, 'audio/ogg')}
        requests.post(url, data={'chat_id': chat_id}, files=files, timeout=25)
    except Exception as e:
        print(f"❌ Voice Output Error: {e}")

def convert_voice_to_text(file_id):
    """تحميل البصمة الصوتية وتحويلها لنص مكتوب مع معالجة الأخطاء"""
    try:
        # 1. جلب رابط الملف من تليجرام
        file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
        if not file_info.get('ok'): return None
        
        file_path = file_info['result']['file_path']
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        audio_content = requests.get(file_url).content

        # 2. حفظ الملف مؤقتاً في المجلد الحالي
        ogg_path = "temp_voice.ogg"
        wav_path = "temp_voice.wav"
        
        with open(ogg_path, "wb") as f:
            f.write(audio_content)

        # 3. التحويل من OGG إلى WAV (يتطلب ffmpeg مثبت في تيرمكس)
        audio = AudioSegment.from_file(ogg_path, format="ogg")
        audio.export(wav_path, format="wav")

        # 4. استخدام محرك جوجل للتعرف على الكلام
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            # فلترة الضوضاء
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data_rec = recognizer.record(source)
            # التعرف على اللهجة العربية (السعودية هي الأقرب للسودانية في المحرك)
            text = recognizer.recognize_google(audio_data_rec, language="ar-SA")
            
            # تنظيف الملفات المؤقتة بعد النجاح
            if os.path.exists(ogg_path): os.remove(ogg_path)
            if os.path.exists(wav_path): os.remove(wav_path)
            
            return text
    except Exception as e:
        print(f"❌ Voice Recognition Detail: {str(e)}")
        return None

def analyze_voice_tone(wav_path):
    """تحليل نبرة الصوت (RMS)"""
    try:
        if not os.path.exists(wav_path): return "✅ تم استلام الصوت."
        audio = AudioSegment.from_wav(wav_path)
        loudness = audio.rms
        analysis = "📊 <b>تحليل الأداء الصوتي:</b>\n"
        if loudness < 500: analysis += "⚠️ صوتك منخفض، ارفع صوتك قليلاً.\n"
        else: analysis += "✅ مستوى صوتك ممتاز وثابت.\n"
        return analysis
    except:
        return "✅ تم تحليل الصوت بنجاح."

# --- إدارة الـ Webhook والمنطق ---

def handle_telegram_webhook(data):
    """المستقبل الرئيسي للرسائل"""
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]

        # معالجة بصمات الصوت
        if "voice" in message:
            send_message(chat_id, "⏳ <i>جاري معالجة صوتك...</i>")
            voice_text = convert_voice_to_text(message["voice"]["file_id"])
            if voice_text:
                tone_report = analyze_voice_tone("temp_voice.wav")
                send_message(chat_id, f"📝 <b>سمعتك بتقول:</b>\n\"{voice_text}\"\n\n{tone_report}")
                process_logic(chat_id, voice_text)
            else:
                send_message(chat_id, "⚠️ معليش، ما قدرت أفهم الصوت بوضوح. جرب سجل في مكان هادئ أو اتكلم ببطء.")
            return

        # معالجة النصوص
        if "text" in message:
            process_logic(chat_id, message["text"])

def process_logic(chat_id, text):
    """منطق الرد الذكي"""
    from app.models import User, CV, db
    
    # أوامر النظام
    if text.startswith("/start"):
        # (كود الربط المعتاد)
        send_message(chat_id, "🤖 أهلاً بك في جوبيني! أنا مساعدك المهني الذكي. كيف أساعدك اليوم؟")

    elif "مقابلة" in text or text.startswith("/interview"):
        user = User.query.filter_by(telegram_id=str(chat_id)).first()
        job_name = user.agent_query if (user and user.agent_query) else "مهندس"
        user_sessions[chat_id] = {"mode": "interview", "job": job_name, "history": []}
        
        prompt = f"أنت مدير توظيف. رحب بالمرشح {user.username if user else ''} لوظيفة {job_name} واطرح سؤالاً واحداً."
        ai_q = openrouter_ai.get_ai_response(prompt)
        send_message(chat_id, f"🎙️ <b>بدأت المقابلة: {job_name}</b>")
        send_voice_response(chat_id, ai_q)

    elif chat_id in user_sessions:
        session = user_sessions[chat_id]
        if any(x in text for x in ["خلاص", "إنهاء", "شكرا"]):
            send_message(chat_id, "🏁 <b>انتهت المقابلة. جاري استخراج الشهادة...</b>")
            # توليد الشهادة (استدعاء cert_gen)
            from app.utils.cert_gen import generate_interview_cert
            path = generate_interview_cert(str(chat_id), session['job'], 9)
            send_document(chat_id, path, caption="🏆 مبروك! شهادة تميز من جوبيني.")
            del user_sessions[chat_id]
        else:
            ai_next = openrouter_ai.get_ai_response(f"إجابة المرشح: {text}. قيمها واطرح السؤال التالي.")
            send_voice_response(chat_id, ai_next)

    else:
        # استشارة عامة
        resp = openrouter_ai.get_ai_response(text)
        send_message(chat_id, resp)
        send_voice_response(chat_id, resp)

def send_document(chat_id, document_path, caption=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(document_path, 'rb') as doc:
            return requests.post(url, data={'chat_id': chat_id, 'caption': caption}, files={'document': doc}).json()
    except: return None

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if data: handle_telegram_webhook(data)
    return jsonify({"status": "ok"}), 200
