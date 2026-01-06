# ~/jobeni-sD/app/telegram_bot.py
import requests, os, json, re
from flask import current_app, Blueprint, request, jsonify
from app.openrouter_ai import get_ai_response

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
telegram_bp = Blueprint('telegram', __name__)
interview_sessions = {}

@telegram_bp.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data: return jsonify({"status": "no data"}), 200
    if "callback_query" in data: handle_callback(data["callback_query"])
    elif "message" in data: handle_telegram_webhook(data)
    return jsonify({"status": "success"}), 200

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: return requests.post(url, json=payload, timeout=10).json()
    except: return None

def answer_callback(callback_query_id):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": callback_query_id})

def handle_callback(callback):
    answer_callback(callback["id"])
    chat_id = callback["message"]["chat"]["id"]
    data = callback["data"]

    if data.startswith("start_int_"):
        job_title = data.replace("start_int_", "")
        from app.models import User, CV
        with current_app.app_context():
            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first() if user else None
            exp = f"خبرته: {cv.profession}" if cv else ""
            prompt = f"أنت مدير توظيف. ابدأ مقابلة سريعة لوظيفة {job_title}. {exp}. رحب واسأل أول سؤال."
            first_q = get_ai_response(prompt) or "أهلاً بك! عرفنا عن خبرتك في هذا المجال؟"
            interview_sessions[chat_id] = {"job": job_title, "history": [f"AI: {first_q}"]}
            send_message(chat_id, f"🏁 <b>بدأت المقابلة لـ: {job_title}</b>\n\n{first_q}")

def handle_telegram_webhook(data):
    message = data.get("message")
    if not message or "text" not in message: return
    chat_id, text = message["chat"]["id"], message["text"]

    if chat_id in interview_sessions:
        session = interview_sessions[chat_id]
        if text.lower() in ["إنهاء", "exit", "stop", "خروج", "خلاص"]:
            send_message(chat_id, "🔄 جاري تحليل أدائك وحفظ التقرير...")
            prompt = f"بصفتك خبير HR، حلل هذه المقابلة لـ {session['job']}: {session['history']}. قدم نقاط قوة، نقاط تحسين، ونسبة مئوية للقبول."
            report = get_ai_response(prompt) or "أداء جيد، استمر في التدريب."
            
            # استخراج السكور
            match = re.search(r'(\d+)%', report)
            score_val = match.group(0) if match else "N/A"

            from app.models import User, InterviewReport, db
            with current_app.app_context():
                user = User.query.filter_by(telegram_id=str(chat_id)).first()
                if user:
                    db.session.add(InterviewReport(user_id=user.id, job_title=session['job'], full_report=report, score=score_val))
                    db.session.commit()

            del interview_sessions[chat_id]
            send_message(chat_id, f"📊 <b>التقرير المهني:</b>\n\n{report}")
            send_message(chat_id, "✅ تم حفظ التقرير في لوحة التحكم!")
            return

        session['history'].append(f"User: {text}")
        ai_reply = get_ai_response(f"مقابلة {session['job']}. السجل: {session['history'][-5:]}. قيم الرد واسأل التالي.") or "أخبرني المزيد؟"
        session['history'].append(f"AI: {ai_reply}")
        send_message(chat_id, f"{ai_reply}\n\n<i>(أرسل 'إنهاء' للتقييم)</i>")
        return

    if text.startswith("/start"):
        parts = text.split(" ")
        if len(parts) > 1:
            from app.models import User, db
            with current_app.app_context():
                user = db.session.get(User, int(parts[1]))
                if user:
                    user.telegram_id = str(chat_id)
                    db.session.commit()
                    send_message(chat_id, f"✅ تم الربط بنجاح (<b>{user.username}</b>)")
        else:
            send_message(chat_id, "🤖 أهلاً بك في جوبيني!")

# الدوال المساعدة المطلوبة (للإشعارات)
def notify_status_update(chat_id, job_title, status):
    send_message(chat_id, f"🔔 <b>تحديث الحالة:</b>\n{job_title}: {status}")

def broadcast_new_job(job_title, company, location, category):
    from app.models import User
    with current_app.app_context():
        for u in User.query.filter(User.telegram_id != None).all():
            send_message(u.telegram_id, f"📢 <b>وظيفة جديدة:</b> {job_title} في {company}")

def notify_new_message(chat_id, sender_name, job_title, body):
    send_message(chat_id, f"💬 <b>رسالة من {sender_name}:</b>\n{body}")

def send_document(chat_id, file_path, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as doc:
            requests.post(url, data={'chat_id': chat_id, 'caption': caption}, files={'document': doc})
    except: pass
