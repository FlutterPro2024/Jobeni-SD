# ~/jobeni-sD/app/chat.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Message, User, Job, CV, Post, PostLike, Comment, db
from app.openrouter_ai import openrouter_ai
from datetime import datetime, timedelta

# استيراد آمن لمنع الـ ImportError لملف التليجرام
try:
    from app.telegram_bot import notify_new_message
except ImportError:
    def notify_new_message(*args, **kwargs): return None

chat_bp = Blueprint('chat', __name__)

# --- ميزة جاري الكتابة ---
@chat_bp.route('/typing/<int:recipient_id>', methods=['POST'])
@login_required
def set_typing(recipient_id):
    """تحديث وقت الكتابة للمستخدم لكي يظهر للطرف الآخر"""
    current_user.is_typing_now = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "ok"})

@chat_bp.route('/<int:job_id>/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def open_chat(job_id, recipient_id):
    is_ai_agent = (recipient_id == 0)
    
    # 1. تحديد المستلم
    if is_ai_agent:
        recipient = User(id=0, username="ai_assistant", full_name="مساعد جوبيني الذكي 🤖")
        job = None
    else:
        job = Job.query.get(job_id) if job_id != 0 else None
        recipient = User.query.get_or_404(recipient_id)

    # 2. معالجة الإرسال (POST)
    if request.method == 'POST':
        body = request.form.get('message')
        if body:
            try:
                new_msg = Message(
                    sender_id=current_user.id,
                    recipient_id=recipient_id if recipient_id != 0 else None,
                    body=body
                )
                db.session.add(new_msg)
                db.session.commit()

                if is_ai_agent:
                    # رد الذكاء الاصطناعي
                    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
                    cv_text = user_cv.extracted_text if user_cv else "لا توجد سيرة ذاتية مرفوعة."
                    system_context = f"أنت مساعد جوبيني. المستخدم: {current_user.full_name}. السيرة: {cv_text[:500]}."
                    ai_response = openrouter_ai.get_ai_response(f"{system_context}\nسؤال المستخدم: {body}")

                    bot_user = User.query.filter(User.username.ilike('%bot%')).first()
                    valid_bot_id = bot_user.id if bot_user else 1

                    ai_msg = Message(
                        sender_id=valid_bot_id,
                        recipient_id=current_user.id,
                        body=ai_response,
                        is_read=True
                    )
                    db.session.add(ai_msg)
                    db.session.commit()
                else:
                    # تنبيه التليجرام
                    if recipient and recipient.telegram_id:
                        notify_new_message(recipient.telegram_id, current_user.username, job.title if job else "تواصل عام", body)
            except Exception as e:
                db.session.rollback()
                flash(f"حدث خطأ أثناء الإرسال: {str(e)}", "danger")

    # 3. جلب الرسائل للعرض
    bot_user = User.query.filter(User.username.ilike('%bot%')).first()
    actual_bot_id = bot_user.id if bot_user else 1
    
    target_id = recipient_id if recipient_id != 0 else actual_bot_id
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == target_id)) |
        ((Message.sender_id == target_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    # 4. معالجة طلبات التحديث التلقائي (JSON)
    if request.args.get('json'):
        is_online = recipient.last_seen >= (datetime.utcnow() - timedelta(minutes=5)) if (not is_ai_agent and recipient.last_seen) else False
        is_typing = recipient.is_typing_now >= (datetime.utcnow() - timedelta(seconds=7)) if (not is_ai_agent and recipient.is_typing_now) else False
        
        return jsonify({
            "is_online": is_online,
            "is_typing": is_typing,
            "messages_count": len(messages),
            "messages": [{"id": m.id, "body": m.body, "sender_id": m.sender_id} for m in messages[-10:]] # آخر 10 رسائل للتحقق
        })

    return render_template('chat.html', 
                           messages=messages, 
                           recipient=recipient, 
                           job=job, 
                           is_ai_agent=is_ai_agent,
                           utcnow=datetime.utcnow(),
                           timedelta=timedelta)

@chat_bp.route('/community', methods=['GET', 'POST'])
@login_required
def community():
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            new_post = Post(body=content, author=current_user)
            db.session.add(new_post)
            db.session.commit()
            flash('تم نشر مشاركتك بنجاح! 🚀', 'success')
            return redirect(url_for('chat.community'))

    posts = Post.query.order_by(Post.timestamp.desc()).all()
    ai_suggestion = "شارك نصيحة مهنية اليوم!"
    return render_template('community.html', posts=posts, ai_suggestion=ai_suggestion)

@chat_bp.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = PostLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        action = 'unliked'
    else:
        new_like = PostLike(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        action = 'liked'
    db.session.commit()
    return jsonify({'action': action, 'likes_count': post.likes.count()})

@chat_bp.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    body = request.form.get('comment_body')
    if body:
        comment = Comment(body=body, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('chat.community'))

@chat_bp.route('/follow/<int:user_id>')
@login_required
def follow(user_id):
    user = User.query.get_or_404(user_id)
    if user != current_user and user not in current_user.followed:
        current_user.followed.append(user)
        db.session.commit()
    return redirect(request.referrer or url_for('chat.community'))
	
