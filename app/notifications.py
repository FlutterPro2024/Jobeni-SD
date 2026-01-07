# ~/jobeni-sD/app/notifications.py
import threading
from flask import current_app
from flask_mail import Message as MailMessage
from app import mail, db
from app.models import Notification
from app.telegram_bot import send_message

def add_notification(user_id, title, message, category='info', link=None):
    """إضافة إشعار لقاعدة البيانات ليظهر في الجرس"""
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
            if not msg.sender:
                msg.sender = app.config.get('MAIL_USERNAME') or app.config.get('MAIL_DEFAULT_SENDER')
            mail.send(msg)
            print(f"📧 [Email Engine] Sent: {msg.subject}")
        except Exception as e:
            print(f"❌ [Mail Error]: {e}")

def send_welcome_email(email, username, user_id):
    app = current_app._get_current_object()
    sender = app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME')
    
    # إشعار داخل المنصة
    add_notification(user_id, "مرحباً بك في جوبيني! 🎉", f"يا {username}، نحن سعداء بانضمامك إلينا. ابدأ برفع سيرتك الذاتية الآن.", "success", "/upload-cv")

    msg = MailMessage(subject="مرحباً بك في جوبيني الذكي 🌍", recipients=[email], sender=sender)
    msg.html = f"<h2>أهلاً بك يا {username}!</h2><p>شكراً لانضمامك إلى جوبيني SD.</p>"
    threading.Thread(target=send_async_email, args=[app, msg]).start()

def send_new_application_email(employer, job, applicant, match_score):
    app = current_app._get_current_object()
    sender = app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME')

    # إشعار الجرس لصاحب العمل
    add_notification(
        employer.id, 
        "تقديم جديد على وظيفتك 🎯", 
        f"قدم {applicant.username} على وظيفة {job.title} بنسبة مطابقة {match_score}%", 
        "job_alert", 
        f"/job/{job.id}/candidates"
    )

    msg = MailMessage(subject=f"🔔 تقديم جديد: {job.title}", recipients=[employer.email], sender=sender)
    msg.html = f"<h3>تنبيه توظيف جديد</h3><p>المتقدم: {applicant.username} بنسبة {match_score}%</p>"
    threading.Thread(target=send_async_email, args=[app, msg]).start()

    if employer.telegram_id:
        tg_text = f"🎯 <b>تقديم جديد!</b>\n💼 الوظيفة: {job.title}\n📊 المطابقة: {match_score}%"
        try: send_message(employer.telegram_id, tg_text)
        except: pass

def send_application_status_email(applicant, job_title, status):
    app = current_app._get_current_object()
    sender = app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME')

    status_map = {
        'accepted': ('مقبول ✅', 'success'),
        'interview': ('دعوة لمقابلة 📅', 'info'),
        'rejected': ('نعتذر منك ❌', 'warning'),
        'pending': ('قيد الانتظار ⏳', 'info')
    }
    ar_status, cat = status_map.get(status, (status, 'info'))

    # إشعار الجرس للمتقدم
    add_notification(applicant.id, "تحديث حالة طلبك", f"تم تغيير حالة طلبك لوظيفة {job_title} إلى: {ar_status}", cat, "/my-applications")

    msg = MailMessage(subject=f"تحديث لطلبك: {job_title}", recipients=[applicant.email], sender=sender)
    msg.html = f"<h3>تحديث الحالة</h3><p>الحالة الجديدة: {ar_status}</p>"
    threading.Thread(target=send_async_email, args=[app, msg]).start()

    if applicant.telegram_id:
        try: send_message(applicant.telegram_id, f"🔔 <b>تحديث طلبك:</b>\n💼 {job_title}\nالحالة: {ar_status}")
        except: pass
