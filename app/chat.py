# ~/jobeni-sD/app/chat.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Message, User, Job, CV, db
from app.openrouter_ai import openrouter_ai
from datetime import datetime, timedelta
import cloudinary.uploader
import time

try:
    from app.telegram_bot import notify_new_message
except ImportError:
    def notify_new_message(*args, **kwargs): return None

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/typing/<int:recipient_id>', methods=['POST'])
@login_required
def set_typing(recipient_id):
    current_user.is_typing_now = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "ok"})

@chat_bp.route('/<int:job_id>/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def open_chat(job_id, recipient_id):
    is_ai_agent = (recipient_id == 0)
    if is_ai_agent:
        recipient = User(id=0, username="ai_assistant", full_name="مساعد جوبيني الذكي 🤖")
        job = None
    else:
        job = Job.query.get(job_id) if job_id != 0 else None
        recipient = User.query.get_or_404(recipient_id)

    if request.method == 'POST':
        body = request.form.get('message')
        file = request.files.get('file')
        file_url = None

        if file:
            try:
                upload_res = cloudinary.uploader.upload(file, folder="jobeni_chat")
                file_url = upload_res.get('secure_url')
            except Exception as e:
                print(f"Cloudinary Error: {e}")

        if body or file_url:
            new_msg = Message(
                sender_id=current_user.id,
                recipient_id=recipient_id if recipient_id != 0 else None,
                body=body,
                file_path=file_url
            )
            db.session.add(new_msg)
            db.session.commit()

            if is_ai_agent:
                user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
                cv_text = user_cv.extracted_text if user_cv else "لا توجد سيرة ذاتية."
                ai_prompt = f"المستخدم: {current_user.full_name}. السيرة: {cv_text[:500]}.\nالسؤال: {body}"
                ai_response = openrouter_ai.get_ai_response(ai_prompt)
                bot_user = User.query.filter(User.username.ilike('%bot%')).first()
                db.session.add(Message(sender_id=bot_user.id if bot_user else 1, recipient_id=current_user.id, body=ai_response))
                db.session.commit()
            elif recipient.telegram_id:
                notify_new_message(recipient.telegram_id, current_user.username, job.title if job else "تواصل عام", body or "أرسل ملفاً/صورة")

    bot_user = User.query.filter(User.username.ilike('%bot%')).first()
    target_id = recipient_id if recipient_id != 0 else (bot_user.id if bot_user else 1)
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == target_id)) |
        ((Message.sender_id == target_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    if request.args.get('json'):
        is_typing = recipient.is_typing_now > (datetime.utcnow() - timedelta(seconds=5)) if not is_ai_agent else False
        return jsonify({
            "is_online": (recipient.last_seen >= (datetime.utcnow() - timedelta(minutes=5))) if not is_ai_agent else False,
            "is_typing": is_typing,
            "messages": [{"id": m.id, "body": m.body, "file_path": m.file_path, "sender_id": m.sender_id} for m in messages[-10:]]
        })

    return render_template('chat.html', messages=messages, recipient=recipient, job=job, is_ai_agent=is_ai_agent, utcnow=datetime.utcnow())
