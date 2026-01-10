# ~/jobeni-sD/app/notifications.py
import threading
from flask import current_app, url_for
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
    """دالة داخلية لإرسال الإيميل في الخلفية دون تعطيل المستخدم"""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"📧 [Email Engine] Sent: {msg.subject}")
        except Exception as e:
            print(f"❌ [Mail Error]: {e}")

def send_welcome_email(email, username, user_id):
    """إرسال ترحيب عند التسجيل"""
    app = current_app._get_current_object()
    
    # إشعار داخل الموقع
    add_notification(user_id, "مرحباً بك في جوبيني! 🎉", f"يا {username}، نحن سعداء بانضمامك إلينا. ابدأ برفع سيرتك الذاتية الآن.", "success")

    msg = MailMessage(subject="مرحباً بك في جوبيني SD 🌍", recipients=[email])
    msg.body = f"أهلاً بك يا {username} في جوبيني، منصة التوظيف الذكية الأولى في السودان.\nنتمنى لك رحلة بحث موفقة عن وظيفة أحلامك."
    
    # تشغيل في خيط منفصل لسرعة الاستجابة
    threading.Thread(target=send_async_email, args=[app, msg]).start()

def send_new_application_email(employer, job, applicant, match_score):
    """إشعار صاحب العمل عند وجود متقدم جديد"""
    app = current_app._get_current_object()

    # 1. إشعار الجرس داخل الموقع
    add_notification(
        employer.id,
        "تقديم جديد 🎯",
        f"قدم {applicant.full_name or applicant.username} على وظيفة {job.title} بنسبة مطابقة {match_score}%",
        "primary"
    )

    # 2. إرسال إيميل
    msg = MailMessage(subject=f"🔔 تقديم جديد لوظيفة: {job.title}", recipients=[employer.email])
    msg.body = f"هناك متقدم جديد لوظيفتك.\nالمتقدم: {applicant.username}\nنسبة المطابقة الذكية: {match_score}%"
    threading.Thread(target=send_async_email, args=[app, msg]).start()

    # 3. إشعار تلجرام إذا كان مفعلاً
    if employer.telegram_id:
        tg_text = (f"🎯 <b>تقديم جديد!</b>\n"
                   f"💼 الوظيفة: {job.title}\n"
                   f"👤 المتقدم: {applicant.username}\n"
                   f"📊 المطابقة: {match_score}%")
        try: 
            send_message(employer.telegram_id, tg_text)
        except Exception as e:
            print(f"❌ [Telegram Error]: {e}")

def send_application_status_email(applicant, job_title, status):
    """إشعار المتقدم بتحديث حالة طلبه (قبول/رفض/مقابلة)"""
    app = current_app._get_current_object()

    status_map = {
        'accepted': 'مقبول مبدئياً ✅',
        'rejected': 'نعتذر منك ❌',
        'interview': 'دعوة لمقابلة 📅',
        'pending': 'قيد الانتظار ⏳'
    }
    current_status_ar = status_map.get(status, status)

    # 1. إشعار الجرس
    add_notification(
        applicant.id, 
        "تحديث حالة طلبك", 
        f"تم تحديث حالة طلبك لوظيفة ({job_title}) إلى: {current_status_ar}", 
        "info"
    )

    # 2. إرسال إيميل
    msg = MailMessage(subject=f"تحديث بخصوص طلبك لـ {job_title}", recipients=[applicant.email])
    msg.body = f"مرحباً، تم تحديث حالة طلبك للوظيفة {job_title} لتصبح: {current_status_ar}"
    threading.Thread(target=send_async_email, args=[app, msg]).start()

    # 3. إشعار تلجرام
    if applicant.telegram_id:
        tg_msg = f"🔔 <b>تحديث لطلبك:</b>\n💼 {job_title}\nالحالة: {current_status_ar}"
        try: 
            send_message(applicant.telegram_id, tg_msg)
        except: 
            pass
