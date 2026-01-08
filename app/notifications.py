# ~/jobeni-sD/app/notifications.py
import threading
from flask import current_app
from flask_mail import Message as MailMessage
from app import mail, db
from app.models import Notification
from app.telegram_bot import send_message

def add_notification(user_id, title, message, category='info', link=None):
    """إضافة إشعار لقاعدة البيانات (نظام الجرس داخل الموقع)"""
    try:
        new_notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            category=category,
            link=link
        )
        db.session.add(new_notif)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ [DB Notif Error]: {e}")
        return False

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            print(f"📧 [Email Engine] Sent: {msg.subject}")
        except Exception as e:
            print(f"❌ [Mail Error]: {e}")

def send_welcome_email(email, username, user_id):
    app = current_app._get_current_object()
    add_notification(user_id, "مرحباً بك في جوبيني! 🎉", f"يا {username}، نحن سعداء بانضمامك إلينا.", "success")

    msg = MailMessage(subject="مرحباً بك في جوبيني SD 🌍", recipients=[email])
    msg.body = f"أهلاً بك يا {username} في جوبيني، منصة التوظيف الذكية الأولى في السودان."
    threading.Thread(target=send_async_email, args=[app, msg]).start()

def send_new_application_email(employer, job, applicant, match_score):
    app = current_app._get_current_object()
    
    # 1. إشعار الجرس
    add_notification(
        employer.id, 
        "تقديم جديد 🎯", 
        f"قدم {applicant.username} على وظيفة {job.title} بنسبة {match_score}%", 
        "job_alert"
    )

    # 2. إيميل
    msg = MailMessage(subject=f"🔔 تقديم جديد: {job.title}", recipients=[employer.email])
    msg.body = f"هناك متقدم جديد: {applicant.username}\nنسبة المطابقة: {match_score}%"
    threading.Thread(target=send_async_email, args=[app, msg]).start()

    # 3. تلجرام
    if employer.telegram_id:
        tg_text = f"🎯 <b>تقديم جديد!</b>\n💼 الوظيفة: {job.title}\n📊 المطابقة: {match_score}%"
        try: send_message(employer.telegram_id, tg_text)
        except: pass

def send_application_status_email(applicant, job_title, status):
    app = current_app._get_current_object()
    
    status_ar = {
        'accepted': 'مقبول ✅',
        'rejected': 'نعتذر منك ❌',
        'interview': 'دعوة لمقابلة 📅',
        'pending': 'قيد الانتظار ⏳'
    }
    current_status = status_ar.get(status, status)

    # 1. إشعار الجرس
    add_notification(applicant.id, "تحديث حالة طلبك", f"حالة طلبك لـ {job_title} هي الآن: {current_status}", "info")

    # 2. إيميل
    msg = MailMessage(subject=f"تحديث لطلبك: {job_title}", recipients=[applicant.email])
    msg.body = f"تم تحديث حالة طلبك للوظيفة {job_title} إلى: {current_status}"
    threading.Thread(target=send_async_email, args=[app, msg]).start()

    # 3. تلجرام
    if applicant.telegram_id:
        try: send_message(applicant.telegram_id, f"🔔 <b>تحديث طلبك:</b>\n💼 {job_title}\nالحالة: {current_status}")
        except: pass
