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
    # تحديث حالة الاتصال بأمان
    try:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()

    # التأكد من وجود صورة
    if not current_user.avatar:
        current_user.avatar = 'https://ui-avatars.com/api/?name=' + current_user.username
        try:
            db.session.commit()
        except:
            db.session.rollback()

    # جلب المنشورات
    try:
        posts = Post.query.order_by(Post.timestamp.desc()).all()
    except Exception:
        posts = []

    # جلب المستخدمين المتصلين بأمان
    online_friends = []
    try:
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        online_friends = User.query.filter(User.last_seen >= five_mins_ago, User.id != current_user.id).limit(10).all()
    except Exception:
        online_friends = []

    # جلب المقترحات (استبعاد النفس والبوت)
    try:
        suggested_users = User.query.filter(User.id != current_user.id, User.id != 8).limit(5).all()
    except:
        suggested_users = []

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
        except Exception:
            db.session.rollback()
            flash('حدث خطأ أثناء النشر.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/post/edit/<int:post_id>', methods=['POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash('غير مصرح لك بتعديل هذا المنشور', 'danger')
        return redirect(url_for('community.index'))
    
    content = request.form.get('content')
    if content:
        post.body = content
        db.session.commit()
        flash('تم تحديث المنشور بنجاح', 'success')
    return redirect(url_for('community.index'))

@community_bp.route('/post/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash('غير مصرح لك بحذف هذا المنشور', 'danger')
        return redirect(url_for('community.index'))
    
    try:
        # حذف الملحقات أولاً
        Comment.query.filter_by(post_id=post_id).delete()
        PostLike.query.filter_by(post_id=post_id).delete()
        db.session.delete(post)
        db.session.commit()
        flash('تم حذف المنشور بنجاح', 'info')
    except:
        db.session.rollback()
        flash('حدث خطأ أثناء الحذف', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    try:
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
    except:
        return jsonify({'error': 'failed'}), 500

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('comment_body') or request.form.get('content')
    if content:
        try:
            comment = Comment(body=content, user_id=current_user.id, post_id=post_id)
            db.session.add(comment)
            db.session.commit()
        except:
            db.session.rollback()
    return redirect(url_for('community.index'))

@community_bp.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user and user != current_user:
        try:
            if user not in current_user.followed:
                current_user.followed.append(user)
                notif = Notification(user_id=user.id, title="متابع جديد", message=f"بدأ {current_user.username} بمتابعتك!")
                db.session.add(notif)
                db.session.commit()
                flash(f'أنت الآن تتابع {username}', 'success')
        except:
            db.session.rollback()
    return redirect(request.referrer or url_for('community.index'))

@community_bp.route('/messages')
@login_required
def messages():
    try:
        bot_user = User.query.filter(User.username.ilike('%bot%')).first()
        bot_id = bot_user.id if bot_user else 8
        all_messages = Message.query.filter(or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)).filter(Message.sender_id != bot_id, Message.recipient_id != bot_id).order_by(Message.timestamp.desc()).all()
        conversations = {}
        for msg in all_messages:
            other_user_id = msg.recipient_id if msg.sender_id == current_user.id else msg.sender_id
            if other_user_id not in conversations:
                other_user = User.query.get(other_user_id)
                if other_user:
                    is_online = False
                    if other_user.last_seen:
                        is_online = other_user.last_seen >= (datetime.utcnow() - timedelta(minutes=5))
                    conversations[other_user_id] = {'other_user': other_user, 'last_message': msg, 'is_online': is_online}
        return render_template('messages.html', messages=conversations.values())
    except:
        return render_template('messages.html', messages=[])
