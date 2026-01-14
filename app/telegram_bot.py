# ~/jobeni-sD/app/telegram_bot.py
import requests, os, re
from flask import Blueprint, request, jsonify, current_app
from app.openrouter_ai import openrouter_ai

# توكين البوت الخاص بك
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
telegram_bp = Blueprint('telegram', __name__)

# مخزن مؤقت لجلسات المقابلات (في الإنتاج يفضل استخدام Redis)
interview_sessions = {}

def send_message(chat_id, text, reply_markup=None):
    """إرسال رسالة نصية بسيطة عبر البوت"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: 
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return None

def notify_new_message(telegram_id, sender_name, job_title, message_body):
    """تنبيه المستخدم عند استلام رسالة جديدة في المنصة"""
    text = (
        f"💬 <b>رسالة جديدة!</b>\n"
        f"من: {sender_name}\n"
        f"بخصوص: {job_title}\n\n"
        f"الرسالة: {message_body[:100]}..."
    )
    return send_message(telegram_id, text)

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    """نقطة استقبال البيانات من تليجرام"""
    data = request.get_json()
    if not data: 
        return jsonify({"status": "no data"}), 200
    
    handle_telegram_webhook(data)
    return jsonify({"status": "success"}), 200

def handle_telegram_webhook(data):
    """معالجة الرسائل الواردة للبوت"""
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        # 1. أمر البداية وربط الحساب
        if text and text.startswith("/start"):
            parts = text.split(" ")
            if len(parts) > 1:
                from app.models import User, db
                try:
                    user_id = parts[1]
                    user = db.session.get(User, int(user_id))
                    if user:
                        user.telegram_id = str(chat_id)
                        db.session.commit()
                        send_message(chat_id, f"✅ تم ربط حسابك بنجاح يا <b>{user.username}</b>!\nستصلك الآن تنبيهات الوظائف والرسائل هنا.")
                    else:
                        send_message(chat_id, "❌ لم نتمكن من العثور على هذا المستخدم في قاعدة البيانات.")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error linking telegram: {e}")
                    send_message(chat_id, "⚠️ حدث خطأ أثناء عملية الربط.")
            else:
                send_message(chat_id, "🤖 مرحباً بك في بوت جوبيني السودان! لربط حسابك وتلقي الإشعارات، يرجى الضغط على زر 'ربط تليجرام' من داخل صفحتك الشخصية في المنصة.")

        # 2. منطق المقابلة الذكية
        elif chat_id in interview_sessions:
            handle_interview_logic(chat_id, text)
            
        # 3. رد عام
        elif text:
            send_message(chat_id, "أهلاً بك! أنا بوت جوبيني الذكي. سأقوم بتنبيهك عند وجود رسائل جديدة أو تحديثات لوظائفك.")

def handle_interview_logic(chat_id, text):
    """إدارة المقابلة الوهمية مع الذكاء الاصطناعي عبر تليجرام"""
    session = interview_sessions[chat_id]
    
    # إنهاء الجلسة
    if text and text.lower() in ["إنهاء", "خروج", "تم", "stop", "end"]:
        prompt = f"حلل ردود المتقدم لوظيفة {session.get('job', 'عامة')}: {session.get('history', [])}. أعطِ تقريراً مختصراً باللغة العربية ونسبة مئوية لملاءمته للوظيفة."
        report = openrouter_ai.get_ai_response(report_prompt)
        send_message(chat_id, f"📊 <b>تقرير المقابلة:</b>\n\n{report}")
        del interview_sessions[chat_id]
    
    # استمرار المقابلة
    elif text:
        if 'history' not in session: session['history'] = []
        session['history'].append(f"User: {text}")
        
        ai_prompt = f"أنت مدير توظيف. المستخدم أجاب بـ: '{text}'. قم بتقييم الإجابة سريعاً واسأله السؤال التالي للمقابلة بخصوص وظيفة {session.get('job', 'تقنية')}."
        ai_reply = openrouter_ai.get_ai_response(ai_prompt)
        
        session['history'].append(f"AI: {ai_reply}")
        send_message(chat_id, ai_reply)

def send_document(chat_id, document_path, caption=None):
    """إرسال ملفات (مثل السيرة الذاتية PDF) إلى المستخدم"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    if not os.path.exists(document_path):
        print(f"❌ File not found: {document_path}")
        return None
        
    try:
        with open(document_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'parse_mode': 'HTML'}
            if caption: 
                data['caption'] = caption
            res = requests.post(url, data=data, files=files, timeout=20)
            return res.json()
    except Exception as e:
        print(f"❌ Error sending document: {e}")
        return None
