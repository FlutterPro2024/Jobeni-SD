# ~/jobeni-sD/app/notifications.py
import threading
from flask import current_app
from flask_mail import Message as MailMessage # تم تغيير الاسم هنا للسلامة
from app import mail
from app.telegram_bot import send_message

def send_async_email(app, msg):
    """إرسال البريد في الخلفية لضمان سرعة استجابة الموقع"""
    with app.app_context():
        try:
            # التأكد من وجود مرسل قبل الإرسال لتجنب خطأ "No sender specified"
            if not msg.sender:
                msg.sender = app.config.get('MAIL_USERNAME') or app.config.get('MAIL_DEFAULT_SENDER')
            
            mail.send(msg)
            print(f"📧 [Email Engine] Sent: {msg.subject}")
        except Exception as e:
            print(f"❌ [Mail Error] Failed to send: {e}")

def send_welcome_email(email, username):
    """إرسال بريد ترحيبي عند التسجيل"""
    app = current_app._get_current_object()
    # جلب المرسل مع وضع قيمة احتياطية فورية
    sender = app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME')
    
    msg = MailMessage(subject="مرحباً بك في جوبيني الذكي 🌍", recipients=[email], sender=sender)

    msg.html = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 15px;">
        <h2 style="text-align: center; color: #3b82f6;">أهلاً بك يا {username}! 🚀</h2>
        <p style="font-size: 1.1rem;">شكراً لانضمامك إلى <b>جوبيني SD</b>، منصتك الذكية للبحث عن الوظائف وتطوير السيرة الذاتية باستخدام AI.</p>
        <hr style="border: 0; border-top: 1px solid #eee;">
        <p style="color: #666; font-size: 0.9rem;">يمكنك الآن رفع سيرتك الذاتية والبدء في تلقي اقتراحات الوظائف المناسبة.</p>
    </div>"""
    threading.Thread(target=send_async_email, args=[app, msg]).start()

def send_new_application_email(employer, job, applicant, match_score):
    """إخطار صاحب العمل (إيميل + تلجرام) بوجود متقدم جديد"""
    app = current_app._get_current_object()
    sender = app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME')
    
    msg = MailMessage(subject=f"🔔 تقديم جديد: {job.title}", recipients=[employer.email], sender=sender)

    msg.html = f"""
    <div dir='rtl' style="font-family: Arial;">
        <h3>تنبيه توظيف جديد 🎯</h3>
        <p>المتقدم: <b>{applicant.full_name or applicant.username}</b></p>
        <p>نسبة المطابقة: <b style="color: green;">{match_score}%</b></p>
        <p>يمكنك مراجعة السيرة الذاتية وبدء الدردشة عبر لوحة التحكم.</p>
    </div>"""
    threading.Thread(target=send_async_email, args=[app, msg]).start()

    if employer.telegram_id:
        tg_text = (f"🎯 <b>تقديم جديد لوظيفتك!</b>\n\n"
                   f"💼 الوظيفة: {job.title}\n"
                   f"👤 المتقدم: {applicant.full_name or applicant.username}\n"
                   f"📊 نسبة المطابقة: {match_score}%")
        try:
            send_message(employer.telegram_id, tg_text)
        except: pass

def send_application_status_email(applicant, job_title, status):
    """إخطار المتقدم بتحديث الحالة (إيميل + تلجرام)"""
    app = current_app._get_current_object()
    sender = app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME')

    status_info = {
        'accepted': {'ar': 'مقبول مبدئياً ✅', 'desc': 'مبروك! سيتم التواصل معك قريباً.'},
        'interview': {'ar': 'دعوة لمقابلة 📅', 'desc': 'يرجى مراجعة بريدك أو الرسائل لتحديد الموعد.'},
        'rejected': {'ar': 'نعتذر منك ❌', 'desc': 'نتمنى لك حظاً أوفر في الفرص القادمة.'},
        'pending': {'ar': 'قيد الانتظار ⏳', 'desc': 'طلبك لا يزال تحت المراجعة.'}
    }.get(status, {'ar': status, 'desc': ''})

    msg = MailMessage(subject=f"تحديث لطلبك: {job_title}", recipients=[applicant.email], sender=sender)
    msg.html = f"""
    <div dir='rtl' style="font-family: Arial;">
        <h3>تحديث حالة الطلب</h3>
        <p>مرحباً {applicant.username}،</p>
        <p>بخصوص وظيفة <b>{job_title}</b>، الحالة الجديدة هي: <b style="color: #3b82f6;">{status_info['ar']}</b></p>
        <p>{status_info['desc']}</p>
    </div>"""
    threading.Thread(target=send_async_email, args=[app, msg]).start()

    if applicant.telegram_id:
        tg_text = (f"🔔 <b>تحديث لطلب التوظيف!</b>\n\n"
                   f"💼 الوظيفة: {job_title}\n"
                   f"الحالة الجديدة: {status_info['ar']}")
        try:
            send_message(applicant.telegram_id, tg_text)
        except: pass
