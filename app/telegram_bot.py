# ~/jobeni-sD/app/telegram_bot.py
import requests
import os
from flask import current_app, Blueprint, request, jsonify

# التوكن من البيئة أو الافتراضي
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
ADMIN_ID = "604818360"

telegram_bp = Blueprint('telegram', __name__)

@telegram_bp.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if data:
        handle_telegram_webhook(data)
    return jsonify({"status": "success"}), 200

def send_message(chat_id, text):
    if not chat_id: return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"Telegram Error: {e}")
        return None

def send_document(chat_id, file_path, caption=""):
    """إرسال ملف PDF إلى المستخدم عبر التلجرام"""
    if not chat_id or not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            res = requests.post(url, data=data, files=files, timeout=40)
            return res.json()
    except Exception as e:
        print(f"Telegram Document Error: {e}")
        return None

def handle_telegram_webhook(data):
    message = data.get("message") or data.get("result", [{}])[0].get("message")
    if not message: return

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

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

# --- الدوال المطلوبة لملف jobs.py و cv.py ---

def notify_admin_new_cv(username, profession, score, feedback):
    text = f"🆕 <b>سيرة جديدة!</b>\n👤 {username}\n💼 {profession}\n📊 {score}%"
    return send_message(ADMIN_ID, text)

def notify_employer_new_app(chat_id, seeker_name, job_title, score):
    text = f"📥 <b>طلب تقديم جديد!</b>\n👤 المتقدم: {seeker_name}\n💼 الوظيفة: {job_title}\n🎯 المطابقة: {score}%"
    return send_message(chat_id, text)

def notify_status_update(chat_id, job_title, status):
    status_ar = {'accepted': '✅ تم قبولك!', 'rejected': ' ❌ نعتذر، لم يتم اختيارك.', 'interview': '📅 مقابلة!'}
    text = f"🔔 <b>تحديث لوظيفة: {job_title}</b>\nالحالة: {status_ar.get(status, status)}"
    return send_message(chat_id, text)

def broadcast_new_job(job_title, company, location, category):
    from app.models import User
    text = f"📢 <b>وظيفة جديدة!</b>\n💼 {job_title}\n🏢 {company}\n📍 {location}"
    with current_app.app_context():
        users = User.query.filter(User.telegram_id != None).all()
        for user in users: send_message(user.telegram_id, text)

def notify_seeker_analysis(chat_id, profession, score, feedback):
    text = f"📊 <b>تحليل CV:</b>\n💼 {profession}\n📈 القوة: {score}%\n💡 {feedback}"
    return send_message(chat_id, text)

def notify_new_message(chat_id, sender_name, job_title, message_body):
    text = f"💬 <b>رسالة من: {sender_name}</b>\n✉️: {message_body[:50]}..."
    return send_message(chat_id, text)
