# ~/jobeni-sD/app/community.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Post, db, Comment, PostLike, User, Message, Notification
from datetime import datetime, timedelta
from sqlalchemy import or_

community_bp = Blueprint('community', __name__)

# --- مسار تحديث قاعدة البيانات (لضمان وجود الجداول الجديدة) ---
@community_bp.route('/force-db-update-2026')
def force_db_update():
    try:
        db.create_all()
        return "<h1>✅ تم تحديث قاعدة البيانات بنجاح!</h1><p>كل الجداول الجديدة أصبحت جاهزة.</p><a href='/community'>العودة للمجتمع</a>"
    except Exception as e:
        return f"<h1>❌ حدث خطأ أثناء التحديث</h1><p>{str(e)}</p>"

@community_bp.route('/')
@login_required
def index():
    # تحديث آخر ظهور للمستخدم الحالي
    current_user.last_seen = datetime.utcnow()
    try:
        db.session.commit()
    except:
        db.session.rollback()

    # جلب المنشورات مع ترتيبها من الأحدث
    posts = Post.query.order_by(Post.timestamp.desc()).all()

    # جلب المستخدمين المتصلين (آخر 5 دقائق)
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    online_friends = User.query.filter(User.last_seen >= five_mins_ago, User.id != current_user.id).limit(10).all()

    # اقتراح أشخاص للمتابعة
    suggested_users = User.query.filter(User.id != current_user.id).limit(5).all()

    ai_suggestion = "شاركنا مهارة جديدة تعلمتها اليوم لتلهم زملاءك في السودان! 🇸🇩"

    return render_template('community.html',
                           posts=posts,
                           ai_suggestion=ai_suggestion,
                           suggested_users=suggested_users,
                           online_friends=online_friends,
                           Comment=Comment,
                           utcnow=datetime.utcnow(),
                           timedelta=timedelta)

@community_bp.route('/post/new', methods=['POST'])
@login_required
def new_post():
    content = request.form.get('body') or request.form.get('content')
    if content:
        try:
            post = Post(body=content, user_id=current_user.id)
            db.session.add(post)
            db.session.commit()
            flash('تم نشر منشورك بنجاح! 🚀', 'success')
        except Exception:
            db.session.rollback()
            flash('حدث خطأ أثناء النشر.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        like = PostLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        
        if like:
            db.session.delete(like)
            action = 'unliked'
        else:
            new_like = PostLike(user_id=current_user.id, post_id=post_id)
            db.session.add(new_like)
            action = 'liked'
            
            # إرسال إشعار لصاحب المنشور
            if post.user_id != current_user.id:
                notif = Notification(
                    user_id=post.user_id,
                    title="إعجاب جديد",
                    message=f"أعجب {current_user.username} بمنشورك.",
                    link=url_for('community.index') + f"#post-{post.id}"
                )
                db.session.add(notif)
        
        db.session.commit()
        likes_count = PostLike.query.filter_by(post_id=post_id).count()
        return jsonify({'action': action, 'likes_count': likes_count})
    except:
        db.session.rollback()
        return jsonify({'error': 'failed'}), 500

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('comment_body') or request.form.get('content')
    if content:
        try:
            post = Post.query.get_or_404(post_id)
            comment = Comment(body=content, user_id=current_user.id, post_id=post_id)
            db.session.add(comment)
            
            # إرسال إشعار لصاحب المنشور
            if post.user_id != current_user.id:
                notif = Notification(
                    user_id=post.user_id,
                    title="تعليق جديد",
                    message=f"علق {current_user.username} على منشورك: {content[:30]}...",
                    link=url_for('community.index') + f"#post-{post.id}"
                )
                db.session.add(notif)
                
            db.session.commit()
            flash('تم إضافة التعليق!', 'success')
        except:
            db.session.rollback()
    return redirect(url_for('community.index'))

@community_bp.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user != current_user:
        if user not in current_user.followed:
            current_user.followed.append(user)
            notif = Notification(
                user_id=user.id, 
                title="متابع جديد", 
                message=f"بدأ {current_user.username} بمتابعتك!"
            )
            db.session.add(notif)
            db.session.commit()
            flash(f'أنت الآن تتابع {username}', 'success')
    return redirect(request.referrer or url_for('community.index'))

@community_bp.route('/messages')
@login_required
def messages():
    try:
        # استبعاد رسائل البوت من القائمة العامة للدردشات البشرية
        bot_user = User.query.filter(User.username.ilike('%bot%')).first()
        bot_id = bot_user.id if bot_user else 0
        
        # جلب كل الرسائل التي يكون المستخدم طرفاً فيها
        all_messages = Message.query.filter(
            or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)
        ).filter(Message.sender_id != bot_id, Message.recipient_id != bot_id).order_by(Message.timestamp.desc()).all()
        
        conversations = {}
        for msg in all_messages:
            other_user_id = msg.recipient_id if msg.sender_id == current_user.id else msg.sender_id
            if other_user_id not in conversations:
                other_user = User.query.get(other_user_id)
                if other_user:
                    # فحص حالة الاتصال بدقة
                    is_online = False
                    if other_user.last_seen:
                        is_online = (datetime.utcnow() - other_user.last_seen).total_seconds() < 300
                    
                    conversations[other_user_id] = {
                        'other_user': other_user,
                        'last_message': msg,
                        'is_online': is_online
                    }
        
        return render_template('messages.html', 
                               messages=conversations.values(), 
                               utcnow=datetime.utcnow(), 
                               timedelta=timedelta)
    except Exception as e:
        print(f"Error in messages route: {e}")
        return render_template('messages.html', messages=[])
