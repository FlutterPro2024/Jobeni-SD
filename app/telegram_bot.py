# ~/jobeni-sD/app/telegram_bot.py
import requests, os, re, json
from flask import Blueprint, request, jsonify, current_app
from app.openrouter_ai import openrouter_ai

# توكن البوت الجديد (مباشر ومفعل)
BOT_TOKEN = "8428928079:AAE9adzjOfMPj3k-WHuzmZc3uDM7KyBw8zA"
telegram_bp = Blueprint('telegram', __name__)

# مخزن مؤقت لجلسات الذكاء الاصطناعي والمقابلات
user_sessions = {}

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
    """معالجة كافة أنواع التفاعلات (نصوص، أوامر، مقابلات)"""
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user_info = message.get("from", {})

        if not text: return

        # 1. أمر البداية والربط الذكي
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
                        welcome = (
                            f"✅ <b>تم الربط بنجاح يا {user.username}!</b>\n\n"
                            "أنا الآن وكيلك الشخصي في جوبيني السودان 🇸🇩\n"
                            "سأقوم بـ:\n"
                            "• جلب أحدث الوظائف التي تناسبك.\n"
                            "• إجراء مقابلات تدريبية معك.\n"
                            "• تنبيهك فور قبول طلباتك."
                        )
                        send_message(chat_id, welcome)
                    else:
                        send_message(chat_id, "❌ خطأ: لم أستطع العثور على حسابك.")
                except:
                    db.session.rollback()
                    send_message(chat_id, "⚠️ عذراً، حدث خلل أثناء الربط.")
            else:
                send_message(chat_id, "🤖 أهلاً بك! أنا بوت جوبيني الذكي. يرجى الضغط على 'ربط تليجرام' من داخل المنصة لتفعيل خدماتي.")

        # 2. تشغيل المقابلة الذكية (الوكيل الشخصي)
        elif text.startswith("/interview") or "مقابلة" in text:
            from app.models import User, CV
            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            cv = CV.query.filter_by(user_id=user.id).first() if user else None
            job_name = user.agent_query if (user and user.agent_query) else "مهندس"

            user_sessions[chat_id] = {
                "mode": "interview",
                "job": job_name,
                "history": [],
                "cv_context": cv.extracted_text[:1000] if cv else "خبرة عامة"
            }
            
            start_prompt = f"أنت الآن مدير توظيف. رحب بالمرشح {user.username if user else ''} لوظيفة {job_name} واطرح أول سؤال بناءً على خبرته."
            ai_q = openrouter_ai.get_ai_response(start_prompt)
            send_message(chat_id, f"🚀 <b>بدء المقابلة الافتراضية</b>\n📌 الوظيفة: {job_name}\n" + "—" * 10 + f"\n\n{ai_q}")

        # 3. إدارة جلسات الحوار النشطة (مقابلة أو دردشة ذكية)
        elif chat_id in user_sessions:
            session = user_sessions[chat_id]
            
            # خيار الإنهاء
            if text.lower() in ["إنهاء", "خروج", "خلاص", "stop", "end"]:
                send_message(chat_id, "📊 <b>جاري تحليل أدائك... انتظر قليلاً</b>")
                report_prompt = f"حلل حوار المقابلة هذا:\n{session['history']}\nأعطِ تقييماً من 10 ونقاط قوة وضعف بالعربية."
                final_report = openrouter_ai.get_ai_response(report_prompt)
                send_message(chat_id, f"✅ <b>التقرير النهائي:</b>\n\n{final_report}")
                del user_sessions[chat_id]
            
            # متابعة المقابلة
            else:
                session['history'].append(f"Candidate: {text}")
                ai_next_prompt = f"السجل: {session['history']}\nالوظيفة: {session['job']}\nقيم الإجابة واطرح السؤال التالي."
                ai_next_q = openrouter_ai.get_ai_response(ai_next_prompt)
                session['history'].append(f"AI: {ai_next_q}")
                send_message(chat_id, ai_next_q)

        # 4. الاستفسارات العامة (الوكيل يرد على أي شيء)
        else:
            send_message(chat_id, "⏳ <i>جاري التفكير...</i>")
            agent_response = openrouter_ai.get_ai_response(f"رد كمساعد ذكي لمنصة جوبيني السودان: {text}")
            help_footer = "\n\n💡 <i>يمكنك قول 'مقابلة' للتدريب أو 'إنهاء' لختم الجلسة.</i>"
            send_message(chat_id, f"🤖 {agent_response}" + help_footer)

def send_document(chat_id, document_path, caption=None):
    """إرسال السير الذاتية أو التقارير كملفات"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    if not os.path.exists(document_path): return None
    try:
        with open(document_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'parse_mode': 'HTML'}
            if caption: data['caption'] = caption
            res = requests.post(url, data=data, files=files, timeout=20)
            return res.json()
    except Exception as e:
        print(f"❌ File Send Error: {e}")
        return None
