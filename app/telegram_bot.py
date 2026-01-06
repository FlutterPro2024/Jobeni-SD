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
    try: 
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except: 
        return None

def answer_callback(callback_query_id):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": callback_query_id})

def handle_callback(callback):
    answer_callback(callback["id"])
    chat_id = callback["message"]["chat"]["id"]
    data = callback["data"]

    if data.startswith("start_int_"):
        job_title = data.replace("start_int_", "")
        # تنظيف العنوان من الرموز التي قد تسبب مشاكل
        clean_title = re.sub(r'[^\w\s]', ' ', job_title).strip()
        
        from app.models import User, CV
        with current_app.app_context():
            user = User.query.filter_by(telegram_id=str(chat_id)).first()
            cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first() if user else None
            exp = f"خبرته: {cv.profession}" if cv else ""
            
            prompt = f"أنت مدير توظيف خبير. ابدأ مقابلة عمل احترافية لوظيفة {clean_title}. {exp}. رحب بالمتقدم بحفاوة واسأله السؤال الأول."
            first_q = get_ai_response(prompt) or "أهلاً بك! يسعدنا اهتمامك. عرفنا عن نفسك وخبرتك في هذا المجال؟"
            
            interview_sessions[chat_id] = {"job": clean_title, "history": [f"AI: {first_q}"]}
            send_message(chat_id, f"🏁 <b>بدأت المقابلة لـ: {clean_title}</b>\n\n{first_q}")

def handle_telegram_webhook(data):
    message = data.get("message")
    if not message or "text" not in message: return
    chat_id, text = message["chat"]["id"], message["text"]

    if chat_id in interview_sessions:
        session = interview_sessions[chat_id]
        
        # إنهاء المقابلة واستخراج التقرير
        if text.lower() in ["إنهاء", "exit", "stop", "خروج", "خلاص", "تم"]:
            send_message(chat_id, "🔄 جاري تحليل أدائك وحفظ التقرير في ملفك الشخصي...")
            
            prompt = f"بصفتك خبير HR عالمي، حلل هذه المقابلة لوظيفة {session['job']}: {session['history']}. قدم نقاط القوة، ونقاط التحسين، ونسبة مئوية واضحة للقبول بتنسيق (XX%)."
            report = get_ai_response(prompt) or "أداء جيد بشكل عام. ركز على الجوانب التقنية أكثر. نسبة القول التقديرية: 75%."

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
            send_message(chat_id, "✅ تم حفظ التقرير بنجاح! يمكنك مراجعته الآن من الموقع.")
            return

        # الرد على أسئلة المقابلة
        session['history'].append(f"User: {text}")
        
        # استخدام سياق الحوار الأخير لسرعة الاستجابة
        context = "\n".join(session['history'][-4:])
        ai_prompt = f"أنت مدير توظيف تجري مقابلة {session['job']}. المتقدم أجاب: '{text}'. قيّم رده واسأل السؤال التالي بناءً على السياق:\n{context}"
        
        ai_reply = get_ai_response(ai_prompt) or "رائع جداً، انتقل للسؤال التالي: ما هي أكبر تحدياتك في هذا المجال وكيف تعاملت معها؟"
        
        session['history'].append(f"AI: {ai_reply}")
        send_message(chat_id, f"{ai_reply}\n\n<i>(أرسل 'إنهاء' للتقييم النهائي)</i>")
        return

    if text.startswith("/start"):
        parts = text.split(" ")
        if len(parts) > 1:
            from app.models import User, db
            with current_app.app_context():
                try:
                    user = db.session.get(User, int(parts[1]))
                    if user:
                        user.telegram_id = str(chat_id)
                        db.session.commit()
                        send_message(chat_id, f"✅ أهلاً <b>{user.username}</b>! تم ربط حسابك بنجاح. سأقوم بإخطارك بكل الوظائف والمقابلات هنا.")
                except:
                    send_message(chat_id, "❌ حدث خطأ في عملية الربط. يرجى إعادة المحاولة من الموقع.")
        else:
            send_message(chat_id, "🤖 أهلاً بك في جوبيني (Jobeni)! منصتك الذكية للوظائف في السودان. كيف يمكنني مساعدتك اليوم؟")

# --- الدوال المساعدة للإشعارات (للتكامل مع النظام) ---

def notify_status_update(chat_id, job_title, status):
    status_ar = {'accepted': '✅ تم قبولك! تهانينا', 'rejected': '❌ نعتذر، لم يتم القبول', 'interview': '📅 تم تحديد موعد مقابلة', 'pending': '⏳ الطلب تحت المراجعة'}
    text = f"🔔 <b>تحديث جديد لحالة طلبك:</b>\n\nالوظيفة: {job_title}\nالحالة: {status_ar.get(status, status)}"
    send_message(chat_id, text)

def notify_employer_new_app(chat_id, seeker_name, job_title, score):
    text = f"📥 <b>طلب تقديم جديد!</b>\n\n👤 المتقدم: {seeker_name}\n💼 الوظيفة: {job_title}\n🎯 نسبة المطابقة: {score}%\n\n<i>افحص الداشبورد للتواصل معه.</i>"
    send_message(chat_id, text)

def broadcast_new_job(job_title, company, location, category):
    from app.models import User
    text = f"📢 <b>وظيفة جديدة تناسب مهاراتك!</b>\n\n💼 {job_title}\n🏢 {company}\n📍 {location}\n📂 التصنيف: {category}"
    with current_app.app_context():
        users = User.query.filter(User.telegram_id != None).all()
        for u in users:
            send_message(u.telegram_id, text)

def notify_new_message(chat_id, sender_name, job_title, body):
    text = f"💬 <b>رسالة جديدة من {sender_name}:</b>\n📌 بخصوص: {job_title}\n\n{body}"
    send_message(chat_id, text)

def send_document(chat_id, file_path, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as doc:
            requests.post(url, data={'chat_id': chat_id, 'caption': caption}, files={'document': doc})
    except: pass
