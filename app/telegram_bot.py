# ~/jobeni-sD/app/telegram_bot.py
import requests, os, re, json, time, io
from flask import Blueprint, request, jsonify, current_app
from app.openrouter_ai import openrouter_ai
from gtts import gTTS  # لتحويل النص لصوت
import speech_recognition as sr  # لتحويل الصوت لنص
from pydub import AudioSegment  # لمعالجة صيغ الصوت

# التوكن الجديد والمؤمن (تم التحديث)
BOT_TOKEN = "8450110637:AAEMNOzpc8phiBr0Dmjm2UHoEWfKi30Ja_s"
telegram_bp = Blueprint('telegram', __name__)

# مخزن مؤقت لجلسات الذكاء الاصطناعي والمقابلات
user_sessions = {}

# --- وظائف المساعدة الإضافية (الصوت والتحليل) ---

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
        tts = gTTS(text=text, lang='ar')
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        voice_io.seek(0)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVoice"
        files = {'voice': ('reply.ogg', voice_io, 'audio/ogg')}
        requests.post(url, data={'chat_id': chat_id}, files=files, timeout=20)
    except Exception as e:
        print(f"❌ Voice Output Error: {e}")

def convert_voice_to_text(file_id):
    """تحميل البصمة الصوتية وتحويلها لنص مكتوب"""
    try:
        file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
        file_path = file_info['result']['file_path']
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        audio_data = requests.get(file_url).content
        
        ogg_path = "user_voice.ogg"
        wav_path = "user_voice.wav"
        with open(ogg_path, "wb") as f: f.write(audio_data)
        
        audio = AudioSegment.from_ogg(ogg_path)
        audio.export(wav_path, format="wav")
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data_rec = recognizer.record(source)
            text = recognizer.recognize_google(audio_data_rec, language="ar-SA")
            return text
    except Exception as e:
        print(f"❌ Voice Recognition Error: {e}")
        return None

def analyze_voice_tone(wav_path):
    """تحليل بسيط للنبرة باستخدام pydub (النسخة الخفيفة المعتمدة)"""
    try:
        audio = AudioSegment.from_wav(wav_path)
        loudness = audio.rms 
        duration_sec = len(audio) / 1000.0
        analysis = "📊 <b>تحليل الأداء الصوتي:</b>\n"
        if loudness < 500: analysis += "⚠️ صوتك منخفض، حاول التحدث بثقة أكبر.\n"
        elif loudness > 15000: analysis += "⚠️ ضجيج عالٍ، حاول الابتعاد عن الضوضاء.\n"
        else: analysis += "✅ مستوى صوتك متزن وواضح.\n"
        if duration_sec < 2: analysis += "⏱️ إجابتك قصيرة، حاول التوسع في الشرح."
        return analysis
    except:
        return "✅ تم استلام الصوت بنجاح."

# --- الوظائف الأساسية للملف ---

def send_photo(chat_id, photo_path, caption=None):
    """إرسال صور (دعم مسارات محلية وروابط خارجية)"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {'chat_id': chat_id, 'parse_mode': 'HTML'}
    if caption: data['caption'] = caption
    if photo_path.startswith('http'):
        data['photo'] = photo_path
        try:
            res = requests.post(url, data=data, timeout=20)
            return res.json()
        except: return None
    if not os.path.exists(photo_path): return None
    try:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            res = requests.post(url, data=data, files=files, timeout=20)
            return res.json()
    except Exception as e:
        print(f"❌ Photo Send Error: {e}")
        return None

def notify_new_message(telegram_id, sender_name, job_title, message_body):
    """تنبيه فوري للمستخدم عند استلام رسالة بالمنصة"""
    text = (
        f"💬 <b>رسالة جديدة في جوبيني!</b>\n"
        f"👤 <b>من:</b> {sender_name}\n"
        f"📂 <b>بخصوص:</b> {job_title}\n\n"
        f"📝 <b>المحتوى:</b>\n<i>{message_body[:150]}...</i>"
    )
    return send_message(telegram_id, text)

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    """المستقبل الرئيسي لإشارات تليجرام"""
    data = request.get_json()
    if not data:
        return jsonify({"status": "no data"}), 200
    handle_telegram_webhook(data)
    return jsonify({"status": "success"}), 200

def handle_telegram_webhook(data):
    """معالجة كافة أنواع التفاعلات (نص وصوت)"""
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        
        # أولوية معالجة الصوت (Speech-to-Text)
        if "voice" in message:
            voice_text = convert_voice_to_text(message["voice"]["file_id"])
            if voice_text:
                tone_report = analyze_voice_tone("user_voice.wav")
                send_message(chat_id, f"📝 <b>سمعتك بتقول:</b> {voice_text}\n\n{tone_report}")
                process_logic(chat_id, voice_text)
            else:
                send_message(chat_id, "⚠️ لم أفهم التسجيل، يرجى المحاولة مرة أخرى.")
            return

        # معالجة النص العادي
        if "text" in message:
            process_logic(chat_id, message["text"])

def process_logic(chat_id, text):
    """منطق الرد الذكي الموحد"""
    from app.models import User, CV, Application, Job, db

    # 1. أمر البداية والربط
    if text.startswith("/start"):
        parts = text.split(" ")
        if len(parts) > 1:
            try:
                user_id = parts[1]
                user = db.session.get(User, int(user_id))
                if user:
                    user.telegram_id = str(chat_id)
                    db.session.commit()
                    welcome = (
                        f"✅ <b>تم الربط بنجاح يا {user.username}!</b>\n\n"
                        "أنا الآن وكيلك الشخصي والخبير العالمي في جوبيني 🇸🇩🌎\n"
                        "أرسل لي بصمة صوتية أو نصاً للبدء."
                    )
                    send_message(chat_id, welcome)
                else:
                    send_message(chat_id, "❌ لم يتم العثور على الحساب.")
            except:
                db.session.rollback()
                send_message(chat_id, "⚠️ خطأ في عملية الربط.")
        else:
            send_message(chat_id, "🤖 أهلاً بك! أنا بوت جوبيني الذكي. اضغط على 'ربط تليجرام' في المنصة لتفعيل خدماتي.")

    # 2. أمر الـ QR Code
    elif text.startswith("/qr") or any(word in text for word in ["رابط", "تطبيق", "باركود"]):
        qr_path = os.path.join(current_app.root_path, 'static', 'App_qr.png')
        icon_url = "https://jobeni-sd.vercel.app/static/icon.png"
        caption = "🔗 <b>رابط منصة جوبيني السودان</b>\n\n🌐 https://jobeni-sd.vercel.app"
        if not send_photo(chat_id, qr_path, caption=caption):
            send_photo(chat_id, icon_url, caption=caption)

    # 3. المقابلة الذكية (نص وصوت)
    elif text.startswith("/interview") or "مقابلة" in text:
        user = User.query.filter_by(telegram_id=str(chat_id)).first()
        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first() if user else None
        job_name = user.agent_query if (user and user.agent_query) else "مهندس"
        user_sessions[chat_id] = {
            "mode": "interview", "job": job_name, "history": [],
            "cv_context": cv.extracted_text[:1000] if cv else "خبرة عامة"
        }
        start_prompt = f"أنت الآن مدير توظيف. رحب بالمرشح {user.username if user else ''} لوظيفة {job_name} واطرح أول سؤال باختصار."
        ai_q = openrouter_ai.get_ai_response(start_prompt)
        send_message(chat_id, f"🎙️ <b>بدء المقابلة</b>\n📌 الوظيفة: {job_name}\nاستمع للسؤال ورد صوتياً!")
        send_voice_response(chat_id, ai_q)

    # 4. إدارة جلسات المقابلة والشهادات
    elif chat_id in user_sessions:
        session = user_sessions[chat_id]
        if text.lower() in ["إنهاء", "خروج", "خلاص", "stop"]:
            send_message(chat_id, "📊 <b>تحليل النتائج...</b>")
            report_prompt = f"حلل المقابلة وأعطِ تقييماً من 10:\n{session['history']}"
            final_report = openrouter_ai.get_ai_response(report_prompt)
            send_message(chat_id, f"✅ <b>التقرير:</b>\n\n{final_report}")
            
            # توليد شهادة إذا كان السكور عالياً (مثال: 8)
            score = 9 
            if score >= 8:
                from app.utils.cert_gen import generate_interview_cert
                cert_path = generate_interview_cert(str(chat_id), session['job'], score)
                send_document(chat_id, cert_path, caption="🏆 شهادة اجتياز المقابلة من جوبيني!")
            
            del user_sessions[chat_id]
        else:
            session['history'].append(f"Candidate: {text}")
            ai_next = openrouter_ai.get_ai_response(f"قيم الإجابة: {text} واطرح السؤال التالي.")
            session['history'].append(f"AI: {ai_next}")
            send_voice_response(chat_id, ai_next)

    # 5. الاستشارات العامة
    else:
        user = User.query.filter_by(telegram_id=str(chat_id)).first()
        u_context = f"الاسم: {user.full_name}" if user else ""
        agent_response = openrouter_ai.get_expert_omni_response(text, user_context=u_context)
        send_message(chat_id, f"🤖 {agent_response}")
        send_voice_response(chat_id, agent_response)

def send_document(chat_id, document_path, caption=None):
    """إرسال ملفات"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    if not os.path.exists(document_path): return None
    try:
        with open(document_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'parse_mode': 'HTML'}
            if caption: data['caption'] = caption
            return requests.post(url, data=data, files=files, timeout=20).json()
    except Exception as e:
        print(f"❌ File Send Error: {e}")
        return None

