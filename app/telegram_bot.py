# ~/jobeni-sD/app/telegram_bot.py
import requests, os, re
from flask import Blueprint, request, jsonify, current_app
from app.openrouter_ai import openrouter_ai

# توكين البوت الخاص بك
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8560156074:AAH2cBxEmjRkBAcnUjcaWbZEwZ7RTFJEn2c"
telegram_bp = Blueprint('telegram', __name__)

# مخزن مؤقت لجلسات المقابلات (In-memory session management)
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

        if not text:
            return

        # 1. أمر البداية وربط الحساب
        if text.startswith("/start"):
            parts = text.split(" ")
            if len(parts) > 1:
                from app.models import User, db
                try:
                    user_id = parts[1]
                    user = db.session.get(User, int(user_id))
                    if user:
                        user.telegram_id = str(chat_id)
                        db.session.commit()
                        send_message(chat_id, f"✅ تم ربط حسابك بنجاح يا <b>{user.username}</b>!\nستصلك الآن تنبيهات الوظائف والمقابلات هنا.")
                    else:
                        send_message(chat_id, "❌ لم نتمكن من العثور على هذا المستخدم.")
                except Exception as e:
                    db.session.rollback()
                    send_message(chat_id, "⚠️ حدث خطأ أثناء عملية الربط.")
            else:
                send_message(chat_id, "🤖 أهلاً بك في جوبيني! لربط حسابك، اضغط على زر 'ربط تليجرام' في ملفك الشخصي بالمنصة.")

        # 2. تشغيل المقابلة الذكية (أمر جديد)
        elif text.startswith("/interview") or "مقابلة" in text:
            from app.models import User
            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            job_title = user.agent_query if (user and user.agent_query) else "مهندس اتصالات"
            
            interview_sessions[chat_id] = {
                "job": job_title,
                "history": [],
                "user_name": user.username if user else "باحث عن عمل"
            }
            start_msg = f"🚀 <b>بدء المقابلة الذكية</b>\nالوظيفة: {job_title}\n\nأهلاً بك، أنا مدير التوظيف الذكي. لنبدأ:\n<b>س1: عرفني بنفسك باختصار وما هي أكبر إنجازاتك المهنية؟</b>"
            send_message(chat_id, start_msg)

        # 3. إدارة جلسة المقابلة المستمرة
        elif chat_id in interview_sessions:
            handle_interview_logic(chat_id, text)

        # 4. رد عام للمساعدة
        else:
            help_text = (
                "💡 <b>أوامر متاحة:</b>\n"
                "/start - ربط الحساب\n"
                "مقابلة - لبدء مقابلة تجريبية مع AI\n"
                "إنهاء - لختم المقابلة والحصول على التقرير"
            )
            send_message(chat_id, help_text)

def handle_interview_logic(chat_id, text):
    """إدارة المقابلة الوهمية مع الذكاء الاصطناعي عبر تليجرام"""
    session = interview_sessions[chat_id]

    # إنهاء الجلسة وإصدار التقرير
    if text.lower() in ["إنهاء", "خروج", "تم", "stop", "end", "خلاص"]:
        send_message(chat_id, "⏳ جاري تحليل إجاباتك وإعداد التقرير النهائي...")
        
        history_str = "\n".join(session.get('history', []))
        report_prompt = f"حلل ردود هذا الشخص لوظيفة {session.get('job')}:\n{history_str}\nأعط تقرير مفصل باللغة العربية يشمل: نقاط القوة، نقاط الضعف، ونسبة مئوية للملاءمة."
        
        report = openrouter_ai.get_ai_response(report_prompt)
        send_message(chat_id, f"📊 <b>تقرير أداء المقابلة:</b>\n\n{report}")
        del interview_sessions[chat_id]

    # استمرار المقابلة بطرح أسئلة
    else:
        if 'history' not in session: session['history'] = []
        session['history'].append(f"User: {text}")

        ai_prompt = (
            f"أنت الآن مدير توظيف خبير. المتقدم لوظيفة {session.get('job')} أجاب بالتالي: '{text}'.\n"
            "قيم الإجابة في سرك ثم اطرح السؤال التالي (سؤال واحد فقط) لتقييم مهاراته التقنية أو السلوكية."
        )
        ai_reply = openrouter_ai.get_ai_response(ai_prompt)

        session['history'].append(f"AI: {ai_reply}")
        send_message(chat_id, ai_reply)

def send_document(chat_id, document_path, caption=None):
    """إرسال ملفات (مثل السيرة الذاتية PDF) إلى المستخدم"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    if not os.path.exists(document_path):
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
