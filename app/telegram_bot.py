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

# مخزن مؤقت لحالات المقابلة
interview_sessions = {}

@telegram_bp.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data: return jsonify({"status": "no data"}), 200
    if "callback_query" in data:
        handle_callback(data["callback_query"])
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
    
    # التعامل مع طلب بدء المقابلة من الوكيل الذكي (كما هو مطلوب في agent_worker.py)
    if data.startswith("start_int_"):
        job_title = data.replace("start_int_", "")
        from app.models import User, CV
        with current_app.app_context():
            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            # جلب آخر سي في للمستخدم لإضفاء طابع شخصي على المقابلة
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first() if user else None
            exp_context = f"خبرته: {cv.profession}" if cv else ""
            
            prompt = f"أنت مدير توظيف. ابدأ مقابلة سريعة (سؤال واحد) لوظيفة {job_title}. {exp_context}. رحب بالمستخدم واسأله سؤالاً ذكياً."
            first_q = get_ai_response(prompt)
            interview_sessions[chat_id] = {"job": job_title, "history": [f"AI: {first_q}"]}
            send_message(chat_id, f"🏁 <b>بدأت المقابلة لـ: {job_title}</b>\n\n{first_q}")

def handle_telegram_webhook(data):
    message = data.get("message")
    if not message or "text" not in message: return
    chat_id = message["chat"]["id"]
    text = message["text"]

    # إدارة جلسة المقابلة المستمرة
    if chat_id in interview_sessions:
        session = interview_sessions[chat_id]
        if text.lower() in ["إنهاء", "exit", "stop", "خروج", "خلاص"]:
            prompt = f"حلل أداء المستخدم في المقابلة لـ {session['job']}: {session['history']}. اعطِ نسبة مئوية ونصيحة."
            result = get_ai_response(prompt)
            del interview_sessions[chat_id]
            send_message(chat_id, f"📊 <b>نتيجة المقابلة:</b>\n\n{result}")
            return
            
        session['history'].append(f"User: {text}")
        prompt = f"المقابلة لـ {session['job']}. السجل: {session['history']}. قيم الإجابة واطرح السؤال التالي."
        ai_reply = get_ai_response(prompt)
        session['history'].append(f"AI: {ai_reply}")
        send_message(chat_id, f"{ai_reply}\n\n<i>(أرسل 'إنهاء' للتقييم)</i>")
        return

    # ربط الحساب (Deep Linking)
    if text.startswith("/start"):
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
            send_message(chat_id, "🤖 أهلاً بك في جوبيني!\n/my_status - متابعة طلباتي")

# --- الدوال المطلوبة من الملفات الأخرى (jobs.py, chat.py, agent_worker.py) ---

def notify_status_update(chat_id, job_title, status):
    """تحديث حالة الطلب (تستخدم في jobs.py)"""
    status_ar = {'accepted': '✅ مقبول', 'rejected': '❌ مرفوض', 'interview': '📅 مقابلة', 'pending': '⏳ قيد الانتظار'}
    text = f"🔔 <b>تحديث الحالة:</b>\nالوظيفة: {job_title}\nالحالة الجديدة: {status_ar.get(status, status)}"
    return send_message(chat_id, text)

def notify_employer_new_app(chat_id, seeker_name, job_title, score):
    """إشعار صاحب العمل بتقديم جديد (تستخدم في jobs.py)"""
    text = f"📥 <b>تقديم جديد!</b>\n👤 المتقدم: {seeker_name}\n💼 الوظيفة: {job_title}\n🎯 المطابقة: {score}%"
    return send_message(chat_id, text)

def broadcast_new_job(job_title, company, location, category):
    """نشر وظيفة جديدة لجميع المشتركين (تستخدم في jobs.py)"""
    from app.models import User
    text = f"📢 <b>وظيفة جديدة!</b>\n💼 {job_title}\n🏢 {company}\n📍 {location}"
    with current_app.app_context():
        users = User.query.filter(User.telegram_id != None).all()
        for user in users:
            send_message(user.telegram_id, text)

def notify_new_message(chat_id, sender_name, job_title, message_body):
    """إشعار برسالة دردشة جديدة (تستخدم في chat.py)"""
    text = f"💬 <b>رسالة جديدة من {sender_name}</b>\n📌 بخصوص: {job_title}\n\n{message_body}"
    return send_message(chat_id, text)

def send_document(chat_id, file_path, caption=""):
    """إرسال ملف PDF (تستخدم في cv.py)"""
    if not chat_id or not os.path.exists(file_path): return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            requests.post(url, data=data, files=files, timeout=40)
    except Exception as e:
        print(f"Send Document Error: {e}")
        pass
