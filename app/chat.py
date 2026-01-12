# ~/jobeni-sD/app/chat.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Message, User, Job, CV, Post, PostLike, Comment, db
from app.openrouter_ai import openrouter_ai

# استيراد آمن لمنع الـ ImportError
try:
    from app.telegram_bot import notify_new_message
except ImportError:
    def notify_new_message(*args, **kwargs): return None

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat/<int:job_id>/<int:recipient_id>', methods=['GET', 'POST'])
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
        if body:
            try:
                # 1. إرسال رسالة المستخدم (Sender هو المستخدم الحالي)
                new_msg = Message(
                    sender_id=current_user.id,
                    recipient_id=recipient_id if recipient_id != 0 else None,
                    body=body
                )
                db.session.add(new_msg)
                db.session.commit()

                if is_ai_agent:
                    # 2. الحصول على رد الذكاء الاصطناعي
                    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
                    cv_text = user_cv.extracted_text if user_cv else "لا توجد سيرة ذاتية مرفوعة حالياً."
                    system_context = f"أنت مساعد جوبيني. المستخدم: {current_user.full_name}. السيرة: {cv_text[:500]}."
                    ai_response = openrouter_ai.get_ai_response(f"{system_context}\nسؤال المستخدم: {body}")
                    
                    # --- الحل الجذري للخطأ هنا ---
                    # نبحث عن مستخدم البوت الموجود في قاعدتك (باسم bot أو Jobeni_Bot)
                    bot_user = User.query.filter(User.username.ilike('%bot%')).first()
                    # إذا لم نجده، نستخدم أول مستخدم (Admin) أو ID=1 كاحتياط لضمان عدم حدوث Error
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
                    if recipient and recipient.telegram_id:
                        notify_new_message(recipient.telegram_id, current_user.username, job.title if job else "تواصل عام", body)
            except Exception as e:
                db.session.rollback()
                flash(f"حدث خطأ أثناء الإرسال: {str(e)}", "danger")

    # جلب الرسائل للعرض
    # ملاحظة: للعرض فقط، نعتبر أن الرسائل من المساعد (recipient_id=0) هي الرسائل المرتبطة بالـ valid_bot_id
    bot_user = User.query.filter(User.username.ilike('%bot%')).first()
    actual_bot_id = bot_user.id if bot_user else 1

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == (recipient_id if recipient_id != 0 else actual_bot_id))) |
        ((Message.sender_id == (recipient_id if recipient_id != 0 else actual_bot_id)) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', messages=messages, recipient=recipient, job=job, is_ai_agent=is_ai_agent)

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
