# ~/jobeni-sD/app/telegram_bot.py
import requests
import os
import json
from flask import current_app, Blueprint, request, jsonify
from app.openrouter_ai import get_ai_response

# التوكن من البيئة أو الافتراضي
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
ADMIN_ID = "604818360"

telegram_bp = Blueprint('telegram', __name__)

# مخزن مؤقت لحالات المقابلة (في الإنتاج يفضل استخدام Redis أو DB)
interview_sessions = {}

@telegram_bp.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data: return jsonify({"status": "no data"}), 200
    
    # معالجة الضغط على الأزرار
    if "callback_query" in data:
        handle_callback(data["callback_query"])
    # معالجة الرسائل النصية
    elif "message" in data:
        handle_telegram_webhook(data)
        
    return jsonify({"status": "success"}), 200

def send_message(chat_id, text, reply_markup=None):
    if not chat_id: return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"Telegram Error: {e}")
        return None

def handle_callback(callback):
    chat_id = callback["message"]["chat"]["id"]
    data = callback["data"]
    
    if data.startswith("start_int_"):
        job_title = data.replace("start_int_", "")
        from app.models import User, CV
        with current_app.app_context():
            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first() if user else None
            
            prompt = f"أنت مدير توظيف. ابدأ مقابلة سريعة (سؤال واحد) لوظيفة {job_title} بناءً على CV: {cv.extracted_text[:500] if cv else 'غير متوفر'}. رحب بالمستخدم واسأل أول سؤال."
            first_q = get_ai_response(prompt)
            
            interview_sessions[chat_id] = {"job": job_title, "history": [f"AI: {first_q}"]}
            send_message(chat_id, f"🏁 <b>بدأت المقابلة لـ: {job_title}</b>\n\n{first_q}")

def handle_telegram_webhook(data):
    message = data.get("message")
    if not message or "text" not in message: return

    chat_id = message["chat"]["id"]
    text = message["text"]

    # إذا كان المستخدم في جلسة مقابلة
    if chat_id in interview_sessions:
        session = interview_sessions[chat_id]
        if text.lower() in ["إنهاء", "exit", "stop", "خروج"]:
            prompt = f"حلل أداء المستخدم في هذه المقابلة لـ {session['job']}: {session['history']}. اعطِ نسبة مئوية ونصيحة أخيرة."
            result = get_ai_response(prompt)
            del interview_sessions[chat_id]
            send_message(chat_id, f"📊 <b>نتيجة المقابلة السريعة:</b>\n\n{result}")
            return

        session['history'].append(f"User: {text}")
        prompt = f"المقابلة لـ {session['job']}. السجل: {session['history']}. قيم الإجابة واطرح السؤال التالي أو قل 'انتهينا' إذا اكتفيت (3 أسئلة كافية)."
        ai_reply = get_ai_response(prompt)
        session['history'].append(f"AI: {ai_reply}")
        send_message(chat_id, f"{ai_reply}\n\n<i>(أرسل 'إنهاء' للحصول على التقييم)</i>")
        return

    # الأوامر العادية
    if text == "/my_status":
        from app.models import User, Application
        with current_app.app_context():
            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            if not user:
                send_message(chat_id, "⚠️ يرجى ربط حسابك أولاً.")
                return
            apps = Application.query.filter_by(user_id=user.id).order_by(Application.applied_at.desc()).limit(5).all()
            if not apps:
                send_message(chat_id, "📋 لا توجد طلبات تقديم.")
                return
            res_text = "📊 <b>آخر طلبات التقديم:</b>\n\n"
            for a in apps:
                res_text += f"🔹 {a.job.title} | {a.status}\n"
            send_message(chat_id, res_text)

    elif text == "/my_cv":
        from app.models import User, CV
        with current_app.app_context():
            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            if user:
                cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
                if cv:
                    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'cvs', cv.file_path)
                    send_document(chat_id, full_path, caption="📄 سيرتك الذاتية")
                else: send_message(chat_id, "❌ لا يوجد ملف.")

    elif text.startswith("/start"):
        parts = text.split(" ")
        if len(parts) > 1:
            user_id_str = parts[1]
            from app.models import User, db
            with current_app.app_context():
                user = db.session.get(User, int(user_id_str))
                if user:
                    user.telegram_id = str(chat_id)
                    db.session.commit()
                    send_message(chat_id, f"✅ تم الربط بنجاح (<b>{user.username}</b>)")
        else:
            send_message(chat_id, "🤖 أهلاً بك في جوبيني!\n/my_status - متابعة طلباتي\n/my_cv - تحميل سيرتي")

# --- بقية الدوال (إرسال المستندات، التنبيهات، إلخ) تظل كما هي ---
def send_document(chat_id, file_path, caption=""):
    if not chat_id or not os.path.exists(file_path): return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            res = requests.post(url, data=data, files=files, timeout=40)
            return res.json()
    except Exception as e: return None

def notify_admin_new_cv(username, profession, score, feedback):
    text = f"🆕 <b>سيرة جديدة!</b>\n👤 {username}\n💼 {profession}\n📊 {score}%"
    return send_message(ADMIN_ID, text)

def notify_employer_new_app(chat_id, seeker_name, job_title, score):
    text = f"📥 <b>طلب تقديم جديد!</b>\n👤 المتقدم: {seeker_name}\n💼 الوظيفة: {job_title}\n🎯 المطابقة: {score}%"
    return send_message(chat_id, text)
