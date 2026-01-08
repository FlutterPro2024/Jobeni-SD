# ~/jobeni-sD/app/telegram_bot.py
import requests, os, re
from flask import Blueprint, request, jsonify, current_app
from app.openrouter_ai import openrouter_ai

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
telegram_bp = Blueprint('telegram', __name__)

interview_sessions = {}

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except:
        return None

@telegram_bp.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data: return jsonify({"status": "no data"}), 200
    
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        # معالجة أمر البداية والربط
        if text.startswith("/start"):
            parts = text.split(" ")
            if len(parts) > 1:
                from app.models import User, db
                # ربط التلجرام بـ user_id الممرر في الرابط
                user = User.query.get(int(parts[1]))
                if user:
                    user.telegram_id = str(chat_id)
                    db.session.commit()
                    send_message(chat_id, f"✅ تم ربط حسابك بنجاح يا <b>{user.username}</b>!")
            else:
                send_message(chat_id, "🤖 مرحباً بك في بوت جوبيني! اربط حسابك من الموقع لتصلك الإشعارات.")

        # معالجة المقابلات الذكية (لو كانت الجلسة نشطة)
        elif chat_id in interview_sessions:
            handle_interview_logic(chat_id, text)

    return jsonify({"status": "success"}), 200

def handle_interview_logic(chat_id, text):
    session = interview_sessions[chat_id]
    if text.lower() in ["إنهاء", "خروج", "تم"]:
        # تحليل المقابلة عبر AI
        prompt = f"حلل ردود المتقدم لوظيفة {session['job']}: {session['history']}. أعط تقرير مختصر ونسبة مئوية."
        report = openrouter_ai.get_ai_response(prompt)
        send_message(chat_id, f"📊 <b>تقرير المقابلة:</b>\n\n{report}")
        del interview_sessions[chat_id]
    else:
        session['history'].append(f"User: {text}")
        ai_reply = openrouter_ai.get_ai_response(f"أنت مدير توظيف. المتقدم قال: {text}. اسأله السؤال التالي.")
        session['history'].append(f"AI: {ai_reply}")
        send_message(chat_id, ai_reply)

# دوال الإشعارات الخارجية
def notify_new_message(chat_id, sender_name, context, body):
    text = f"💬 <b>رسالة جديدة من {sender_name}</b>\n📌 بخصوص: {context}\n\n{body}"
    send_message(chat_id, text)

def notify_status_update(chat_id, job_title, status):
    status_ar = {'accepted': '✅ مقبول', 'rejected': '❌ مرفوض', 'interview': '📅 مقابلة'}
    text = f"🔔 <b>تحديث لطلبك:</b>\n💼 {job_title}\nالحالة: {status_ar.get(status, status)}"
    send_message(chat_id, text)

# أضف هذه الدالة في نهاية ملف ~/jobeni-sD/app/telegram_bot.py

def send_document(chat_id, document_path, caption=None):
    """إرسال ملف (سيرة ذاتية) عبر بوت التلجرام"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(document_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'parse_mode': 'HTML'}
            if caption:
                data['caption'] = caption
            res = requests.post(url, data=data, files=files, timeout=15)
            return res.json()
    except Exception as e:
        print(f"❌ [Telegram SendDoc Error]: {e}")
        return None
