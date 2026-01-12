# ~/jobeni-sD/app/community.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Post, db, Comment, PostLike, User, Message, Notification
from datetime import datetime, timedelta
from sqlalchemy import or_

community_bp = Blueprint('community', __name__)

@community_bp.route('/')
@login_required
def index():
    # تحديث حالة الاتصال للمستخدم الحالي
    current_user.last_seen = datetime.utcnow()
    db.session.commit()

    if not current_user.avatar:
        current_user.avatar = 'https://ui-avatars.com/api/?name=' + current_user.username
        db.session.commit()

    try:
        posts = Post.query.order_by(Post.timestamp.desc()).all()
    except Exception as e:
        posts = Post.query.all()

    # جلب المستخدمين المتصلين (خلال آخر 5 دقائق)
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    online_friends = User.query.filter(User.last_seen >= five_mins_ago, User.id != current_user.id).limit(10).all()

    # اقتراح مستخدمين
    suggested_users = User.query.filter(User.id != current_user.id).limit(5).all()
    ai_suggestion = "شاركنا مهارة جديدة تعلمتها اليوم لتلهم زملاءك في السودان!"

    return render_template('community.html',
                           posts=posts,
                           ai_suggestion=ai_suggestion,
                           suggested_users=suggested_users,
                           online_friends=online_friends,
                           Comment=Comment)

@community_bp.route('/post/new', methods=['POST'])
@login_required
def new_post():
    content = request.form.get('body') or request.form.get('content')
    if content:
        try:
            post = Post(body=content, user_id=current_user.id)
            db.session.add(post)
            db.session.commit()
            flash('تم نشر منشورك بنجاح!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('حدث خطأ أثناء النشر.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    like = PostLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        action = 'unliked'
    else:
        new_like = PostLike(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        action = 'liked'
    db.session.commit()
    likes_count = PostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'action': action, 'likes_count': likes_count})

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('comment_body') or request.form.get('content')
    if content:
        comment = Comment(body=content, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('community.index'))

@community_bp.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user and user != current_user:
        if user not in current_user.followed:
            current_user.followed.append(user)
            notif = Notification(user_id=user.id, title="متابع جديد", message=f"بدأ {current_user.username} بمتابعتك!")
            db.session.add(notif)
            db.session.commit()
            flash(f'أنت الآن تتابع {username}', 'success')
    return redirect(request.referrer or url_for('community.index'))

@community_bp.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user:
        current_user.followed.remove(user)
        db.session.commit()
        flash(f'ألغيت متابعة {username}', 'info')
    return redirect(request.referrer or url_for('community.index'))

@community_bp.route('/messages')
@login_required
def messages():
    # تحديد ID البوت لاستبعاده
    bot_user = User.query.filter(User.username.ilike('%bot%')).first()
    bot_id = bot_user.id if bot_user else 8

    # جلب الرسائل البشرية فقط (ليست مع البوت)
    all_messages = Message.query.filter(
        or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)
    ).filter(
        Message.sender_id != bot_id,
        Message.recipient_id != bot_id
    ).order_by(Message.timestamp.desc()).all()

    conversations = {}
    for msg in all_messages:
        other_user_id = msg.recipient_id if msg.sender_id == current_user.id else msg.sender_id
        
        if other_user_id not in conversations:
            other_user = User.query.get(other_user_id)
            if other_user:
                # التحقق هل المستخدم متصل؟
                is_online = False
                if other_user.last_seen:
                    is_online = other_user.last_seen >= (datetime.utcnow() - timedelta(minutes=5))
                
                conversations[other_user_id] = {
                    'other_user': other_user,
                    'last_message': msg,
                    'is_online': is_online
                }

    return render_template('messages.html', messages=conversations.values())
