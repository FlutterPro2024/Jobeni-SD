# ~/jobeni-sD/app/notifications.py
import threading
from flask import current_app, url_for, Blueprint, jsonify
from flask_mail import Message as MailMessage
from flask_login import login_required, current_user
from app import mail, db
from app.models import Notification
from app.telegram_bot import send_message

notifications_bp = Blueprint('notifications', __name__)

def add_notification(user_id, title, message, category='info', link=None):
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

@notifications_bp.route('/api/unread_count')
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@notifications_bp.route('/api/latest')
@login_required
def latest_notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id)\
                               .order_by(Notification.created_at.desc()).limit(5).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'link': n.link or '#',
        'is_read': n.is_read
    } for n in notifs])

@notifications_bp.route('/api/mark_read', methods=['POST'])
@login_required
def mark_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({Notification.is_read: True})
    db.session.commit()
    return jsonify({'status': 'success'})

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"❌ [Mail Error]: {e}")

def send_welcome_email(email, username, user_id):
    app = current_app._get_current_object()
    add_notification(user_id, "مرحباً بك في جوبيني! 🎉", f"يا {username}، نحن سعداء بانضمامك إلينا.", "success")
    msg = MailMessage(subject="مرحباً بك في جوبيني SD 🌍", recipients=[email])
    msg.body = f"أهلاً بك يا {username} في جوبيني."
    threading.Thread(target=send_async_email, args=[app, msg]).start()

def send_new_application_email(employer, job, applicant, match_score):
    app = current_app._get_current_object()
    add_notification(employer.id, "تقديم جديد 🎯", f"قدم {applicant.username} على وظيفة {job.title}", "primary")
    msg = MailMessage(subject=f"🔔 تقديم جديد: {job.title}", recipients=[employer.email])
    msg.body = f"هناك متقدم جديد بنسبة مطابقة {match_score}%"
    threading.Thread(target=send_async_email, args=[app, msg]).start()
    if employer.telegram_id:
        try: send_message(employer.telegram_id, f"🎯 تقديم جديد لوظيفة {job.title}")
        except: pass

def send_application_status_email(applicant, job_title, status):
    app = current_app._get_current_object()
    add_notification(applicant.id, "تحديث حالة طلبك", f"حالة طلبك لـ ({job_title}) هي الآن: {status}", "info")
    msg = MailMessage(subject="تحديث بخصوص طلبك", recipients=[applicant.email])
    msg.body = f"تم تحديث حالة طلبك للوظيفة {job_title}"
    threading.Thread(target=send_async_email, args=[app, msg]).start()
