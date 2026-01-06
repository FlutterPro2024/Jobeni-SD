# ~/jobeni-sD/app/chat.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Message, User, Job, CV, db
from app.telegram_bot import notify_new_message 
from app.agent_worker import JobeniAgent # استيراد الوكيل الذكي

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat/<int:job_id>/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def open_chat(job_id, recipient_id):
    # إذا كان المستلم هو المعرف 0، فهذا يعني الدردشة مع الوكيل الذكي
    is_ai_agent = (recipient_id == 0)
    
    if is_ai_agent:
        recipient = User(id=0, username="مساعد جobeni الذكي", full_name="الوكيل الذكي 🤖")
        job = None
    else:
        job = Job.query.get(job_id) if job_id != 0 else None
        recipient = User.query.get_or_404(recipient_id)

    if request.method == 'POST':
        body = request.form.get('message')
        if body:
            # 1. حفظ رسالة المستخدم في قاعدة البيانات
            new_msg = Message(
                sender_id=current_user.id, 
                recipient_id=recipient_id, 
                job_id=job_id if job_id != 0 else None, 
                body=body
            )
            db.session.add(new_msg)
            
            # 2. إذا كانت الدردشة مع الوكيل الذكي (AI)
            if is_ai_agent:
                # جلب السيرة الذاتية للمستخدم ليعرف الوكيل مع من يتحدث
                user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
                cv_text = user_cv.content if user_cv else ""
                
                # استدعاء رد الوكيل
                agent = JobeniAgent(user_cv_text=cv_text)
                ai_response = agent.get_career_advice(body, cv_text)
                
                # حفظ رد الوكيل كرسالة جديدة من المعرف 0
                ai_msg = Message(
                    sender_id=0,
                    recipient_id=current_user.id,
                    job_id=None,
                    body=ai_response,
                    is_read=True
                )
                db.session.add(ai_msg)
            
            else:
                # 3. إذا كانت دردشة عادية بين أشخاص (تنبيه تلغرام)
                if recipient.telegram_id:
                    notify_new_message(
                        recipient.telegram_id, 
                        current_user.full_name or current_user.username, 
                        job.title if job else "دردشة عامة", 
                        body
                    )

            db.session.commit()
            return redirect(url_for('chat.open_chat', job_id=job_id, recipient_id=recipient_id))

    # جلب الرسائل السابقة
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) | 
        ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    # تحديث الرسائل كمقروءة
    unread_msgs = Message.query.filter_by(recipient_id=current_user.id, sender_id=recipient_id, is_read=False).all()
    for m in unread_msgs: 
        m.is_read = True
    db.session.commit()

    return render_template('chat.html', messages=messages, recipient=recipient, job=job, is_ai_agent=is_ai_agent)
