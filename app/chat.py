# ~/jobeni-sD/app/chat.py
import requests
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Message, User, Job, CV, db, Application
from app.openrouter_ai import openrouter_ai
from datetime import datetime, timedelta
from sqlalchemy import or_, and_

# مفتاح ImgBB
IMGBB_API_KEY = "673cbd292e4b734899cf1d846ff9f40b"

try:
    from app.telegram_bot import notify_new_message
except ImportError:
    def notify_new_message(*args, **kwargs): return None

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/messages')
@login_required
def my_messages():
    """عرض صندوق الوارد مقسم لـ 3 أنظمة"""
    # 1. نظام رسائل الوظائف (بين صاحب عمل وباحث)
    # جلب الرسائل اللي فيها job_id
    raw_job_messages = Message.query.filter(
        and_(
            Message.job_id.isnot(None),
            or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)
        )
    ).order_by(Message.timestamp.desc()).all()

    # تجميعها حسب الوظيفة والشخص الآخر
    job_chats = []
    seen_combinations = set()
    for msg in raw_job_messages:
        other_id = msg.recipient_id if msg.sender_id == current_user.id else msg.sender_id
        combo = f"{msg.job_id}-{other_id}"
        if combo not in seen_combinations:
            other_user = User.query.get(other_id)
            job = Job.query.get(msg.job_id)
            job_chats.append({
                'job_id': msg.job_id,
                'job_title': job.title if job else "وظيفة غير معروفة",
                'other_user': other_user,
                'last_message_time': msg.timestamp
            })
            seen_combinations.add(combo)

    # 2. نظام رسائل الأصدقاء (تواصل عام بدون job_id)
    # نجلب المستخدمين الذين تواصلت معهم بدون رقم وظيفة وبدون بوت الذكاء
    bot_user = User.query.filter(User.username.ilike('%bot%')).first()
    bot_id = bot_user.id if bot_user else 1
    
    partners_ids = db.session.query(Message.sender_id).filter(Message.recipient_id == current_user.id, Message.job_id == None, Message.sender_id != bot_id).union(
        db.session.query(Message.recipient_id).filter(Message.sender_id == current_user.id, Message.job_id == None, Message.recipient_id != bot_id)
    ).all()
    
    chat_partners = User.query.filter(User.id.in_([p[0] for p in partners_ids])).all()

    return render_template('messages.html', 
                           job_chats=job_chats, 
                           chat_partners=chat_partners, 
                           utcnow=datetime.utcnow())

@chat_bp.route('/start/<int:recipient_id>')
@login_required
def start_chat(recipient_id):
    """توجيه من زر 'دردشة' في صفحة المتقدمين"""
    last_app = Application.query.join(Job).filter(
        Application.user_id == recipient_id,
        Job.user_id == current_user.id
    ).order_by(Application.applied_at.desc()).first()

    job_id = last_app.job_id if last_app else 0
    return redirect(url_for('chat.open_chat', job_id=job_id, recipient_id=recipient_id))

@chat_bp.route('/<int:job_id>/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def open_chat(job_id, recipient_id):
    is_ai_agent = (recipient_id == 0)
    bot_user = User.query.filter(User.username.ilike('%bot%')).first()
    
    if is_ai_agent:
        recipient = User(id=0, username="ai_assistant", full_name="مساعد جوبيني الذكي 🤖")
        job = None
        target_id = bot_user.id if bot_user else 1
    else:
        job = db.session.get(Job, job_id) if job_id != 0 else None
        recipient = User.query.get_or_404(recipient_id)
        target_id = recipient_id

    if request.method == 'POST':
        body = request.form.get('message')
        file = request.files.get('file')
        file_url = None

        if file:
            try:
                img_data = file.read()
                files = {'image': img_data}
                response = requests.post(f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}", files=files)
                res_json = response.json()
                if res_json.get('success'):
                    file_url = res_json['data']['url']
            except Exception as e:
                print(f"ImgBB Upload Error: {e}")

        if body or file_url:
            new_msg = Message(
                sender_id=current_user.id,
                recipient_id=target_id,
                body=body,
                file_path=file_url,
                job_id=job_id if job_id != 0 else None
            )
            db.session.add(new_msg)
            db.session.commit()

            if is_ai_agent:
                user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
                cv_text = user_cv.extracted_text if user_cv else "لا توجد سيرة ذاتية."
                ai_prompt = f"المستخدم: {current_user.full_name}. السيرة: {cv_text[:500]}.\nالسؤال: {body}"
                ai_response = openrouter_ai.get_ai_response(ai_prompt)
                bot_msg = Message(sender_id=bot_id, recipient_id=current_user.id, body=ai_response, job_id=None)
                db.session.add(bot_msg)
                db.session.commit()
            elif recipient.telegram_id:
                notify_new_message(recipient.telegram_id, current_user.username, job.title if job else "تواصل عام", body or "أرسل ملفاً")

    # جلب الرسائل
    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == target_id),
            and_(Message.sender_id == target_id, Message.recipient_id == current_user.id)
        )
    )
    if job_id != 0:
        messages = messages.filter(Message.job_id == job_id)
    
    messages = messages.order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', messages=messages, recipient=recipient, job=job, is_ai_agent=is_ai_agent, utcnow=datetime.utcnow())
