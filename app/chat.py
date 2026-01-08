# ~/jobeni-sD/app/chat.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Message, User, Job, CV, Post, PostLike, Comment, db
from app.telegram_bot import notify_new_message
from app.openrouter_ai import openrouter_ai

chat_bp = Blueprint('chat', __name__)

# ==========================================
# 1. نظام الدردشة (الذكية وبين المستخدمين)
# ==========================================
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
                # حفظ رسالة المستخدم
                new_msg = Message(
                    sender_id=current_user.id,
                    recipient_id=recipient_id if recipient_id != 0 else None,
                    body=body
                )
                db.session.add(new_msg)
                db.session.commit()

                if is_ai_agent:
                    # جلب بيانات المستخدم لـ AI لتخصيص الرد
                    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
                    cv_text = user_cv.extracted_text if user_cv else "لا توجد سيرة ذاتية مرفوعة حالياً."

                    system_context = (
                        f"أنت 'مساعد جوبيني الذكي'. المستخدم الحالي هو: {current_user.full_name}. "
                        f"سيرته المهنية ملخصة في: {cv_text[:500]}. "
                        "أجب بلهجة مهنية سودانية محببة، واستخدم الرموز التعبيرية والنقاط لتنظيم الإجابة."
                    )
                    ai_response = openrouter_ai.get_ai_response(f"{system_context}\nسؤال المستخدم: {body}")

                    # حفظ رد الـ AI في قاعدة البيانات ليظهر في المحادثة
                    ai_msg = Message(sender_id=0, recipient_id=current_user.id, body=ai_response, is_read=True)
                    db.session.add(ai_msg)
                    db.session.commit()
                else:
                    # إشعار تلجرام للمستخدمين الحقيقيين عند استلام رسالة
                    if recipient.telegram_id:
                        notify_new_message(recipient.telegram_id, current_user.username, job.title if job else "تواصل عام", body)
            except Exception as e:
                db.session.rollback()
                flash(f"حدث خطأ أثناء الإرسال: {str(e)}", "danger")

    # جلب أرشيف الرسائل بين الطرفين
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) |
        ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', messages=messages, recipient=recipient, job=job, is_ai_agent=is_ai_agent)

# ==========================================
# 2. نظام المجتمع (Community Feed)
# ==========================================
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

    # نظام اقتراح المنشورات باستخدام AI (بناءً على تخصص المستخدم)
    ai_suggestion = "ما هي نصيحتك للشباب السوداني الباحث عن عمل في مجالك اليوم؟"
    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if user_cv and user_cv.profession:
        ai_suggestion = f"بصفتك خبير في {user_cv.profession}، شاركنا سراً من أسرار النجاح في هذا التخصص."

    posts = Post.query.order_by(Post.timestamp.desc()).all()
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
        flash('تم إضافة التعليق.', 'success')
    return redirect(url_for('chat.community'))

# ==========================================
# 3. نظام المتابعة
# ==========================================
@chat_bp.route('/follow/<int:user_id>')
@login_required
def follow(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user:
        flash('لا يمكنك متابعة نفسك!', 'warning')
    else:
        if user not in current_user.followed:
            current_user.followed.append(user)
            db.session.commit()
            flash(f'أنت الآن تتابع {user.username}', 'success')
        else:
            flash(f'أنت تتابع {user.username} بالفعل.', 'info')
    return redirect(request.referrer or url_for('chat.community'))
