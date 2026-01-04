# ~/jobeni-sD/app/chat.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Message, User, Job, db
from app.telegram_bot import notify_new_message # استيراد الدالة الجديدة

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat/<int:job_id>/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def open_chat(job_id, recipient_id):
    job = Job.query.get(job_id) if job_id != 0 else None
    recipient = User.query.get_or_404(recipient_id)

    if request.method == 'POST':
        body = request.form.get('message')
        if body:
            new_msg = Message(sender_id=current_user.id, recipient_id=recipient_id, job_id=job_id if job_id != 0 else None, body=body)
            db.session.add(new_msg)
            db.session.commit()

            # إرسال تنبيه تلغرام فوري
            if recipient.telegram_id:
                notify_new_message(recipient.telegram_id, current_user.full_name or current_user.username, job.title if job else "دردشة عامة", body)

            return redirect(url_for('chat.open_chat', job_id=job_id, recipient_id=recipient_id))

    messages = Message.query.filter(((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) | ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))).order_by(Message.timestamp.asc()).all()
    unread_msgs = Message.query.filter_by(recipient_id=current_user.id, sender_id=recipient_id, is_read=False).all()
    for m in unread_msgs: m.is_read = True
    db.session.commit()
    return render_template('chat.html', messages=messages, recipient=recipient, job=job)
