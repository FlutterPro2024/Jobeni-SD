# ~/jobeni-sD/app/notifications.py
import threading
from flask import current_app, url_for, Blueprint, jsonify, request
from flask_mail import Message as MailMessage
from flask_login import login_required, current_user
from app import mail, db
from app.models import Notification
from app.telegram_bot import send_message

notifications_bp = Blueprint('notifications', __name__)

# --- وظائف المساعدة (Helper Functions) ---

def add_notification(user_id, title, message, category='info', link=None):
    """إضافة تنبيه جديد لقاعدة البيانات"""
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

# --- روابط الـ API للتنبيهات اللحظية (AJAX Endpoints) ---

@notifications_bp.route('/api/unread_count')
@login_required
def unread_count():
    """يرجع عدد التنبيهات غير المقروءة فقط"""
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@notifications_bp.route('/api/latest')
@login_required
def latest_notifications():
    """يرجع آخر 5 تنبيهات للمستخدم"""
    try:
        notifs = Notification.query.filter_by(user_id=current_user.id)\
                                   .order_by(Notification.created_at.desc()).limit(5).all()
        return jsonify([{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'link': n.link or '#',
            'is_read': n.is_read,
            'category': n.category or 'info',
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
        } for n in notifs])
    except Exception as e:
        print(f"❌ Error fetching notifications: {e}")
        return jsonify([])

@notifications_bp.route('/api/mark_read', methods=['POST'])
@login_required
def mark_read():
    """تحويل كل التنبيهات إلى 'تمت القراءة'"""
    try:
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({Notification.is_read: True})
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@notifications_bp.route('/api/mark_single_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_single_read(notif_id):
    """تحويل تنبيه واحد فقط إلى مقروء"""
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'forbidden'}), 403

# --- نظام البريد الإلكتروني والتنبيهات الخارجية ---

def send_async_email(app, msg):
    """إرسال إيميل في الخلفية لمنع ثقل السيرفر"""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"❌ [Mail Error]: {e}")

def send_welcome_email(email, username, user_id):
    """تنبيه ترحيبي عند التسجيل"""
    app = current_app._get_current_object()
    add_notification(user_id, "مرحباً بك في جوبيني! 🎉", f"يا {username}، نحن سعداء بانضمامك إلينا. ابدأ بتكملة ملفك الشخصي الآن.", "success", url_for('auth.profile'))
    
    msg = MailMessage(subject="مرحباً بك في جوبيني SD 🌍", recipients=[email])
    msg.body = f"أهلاً بك يا {username} في جوبيني. نتمنى لك رحلة بحث موفقة عن وظيفتك القادمة."
    threading.Thread(target=send_async_email, args=[app, msg]).start()

def send_new_application_email(employer, job, applicant, match_score):
    """تنبيه لصاحب العمل عند وجود تقديم جديد"""
    app = current_app._get_current_object()
    add_notification(employer.id, "تقديم جديد 🎯", f"قدم {applicant.username} على وظيفة {job.title} بنسبة مطابقة {match_score}%", "primary", url_for('jobs.view_applications', job_id=job.id))
    
    msg = MailMessage(subject=f"🔔 تقديم جديد: {job.title}", recipients=[employer.email])
    msg.body = f"هناك متقدم جديد بنسبة مطابقة {match_score}% لوظيفة {job.title}."
    threading.Thread(target=send_async_email, args=[app, msg]).start()
    
    if employer.telegram_id:
        try:
            send_message(employer.telegram_id, f"🎯 تقديم جديد لوظيفة {job.title}\nالمتقدم: {applicant.username}\nالمطابقة: {match_score}%")
        except:
            pass

def send_application_status_email(applicant, job_title, status):
    """تنبيه للموظف عند قبول/رفض طلبه"""
    app = current_app._get_current_object()
    add_notification(applicant.id, "تحديث حالة طلبك", f"حالة طلبك لـ ({job_title}) هي الآن: {status}", "info")
    
    msg = MailMessage(subject="تحديث بخصوص طلبك", recipients=[applicant.email])
    msg.body = f"تم تحديث حالة طلبك للوظيفة {job_title} إلى {status}."
    threading.Thread(target=send_async_email, args=[app, msg]).start()
