# ~/jobeni-sD/app/community.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Post, db, Comment, PostLike, User, Notification, Message
from datetime import datetime, timedelta
from sqlalchemy import text, or_

community_bp = Blueprint('community', __name__)

@community_bp.route('/')
@login_required
def index():
    # تحديث وقت ظهور المستخدم (Last Seen)
    current_user.last_seen = datetime.utcnow()
    try:
        db.session.commit()
    except:
        db.session.rollback()

    # جلب المنشورات مرتبة من الأحدث للأقدم
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    
    # تحديد المستخدمين المتصلين (آخر 5 دقائق)
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    online_friends = User.query.filter(User.last_seen >= five_mins_ago, User.id != current_user.id).limit(10).all()
    
    suggested_users = User.query.filter(User.id != current_user.id).limit(5).all()
    ai_suggestion = "شاركنا مهارة جديدة تعلمتها اليوم لتلهم زملاءك في السودان! 🇸🇩"

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
            flash('تم نشر منشورك بنجاح! 🚀', 'success')
        except:
            db.session.rollback()
            flash('حدث خطأ أثناء النشر.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/like/<int:post_id>', methods=['POST'])
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
        # إشعار لصاحب المنشور
        if post.user_id != current_user.id:
            notif = Notification(user_id=post.user_id, title="إعجاب جديد",
                                 message=f"أعجب {current_user.full_name or current_user.username} بمنشورك.")
            db.session.add(notif)
    db.session.commit()
    likes_count = PostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'action': action, 'likes_count': likes_count})

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('comment_body')
    # دعم الردود المتداخلة (إذا وجد parent_id في الفورم)
    parent_id = request.form.get('parent_id', type=int)
    
    if content:
        post = Post.query.get_or_404(post_id)
        comment = Comment(
            body=content, 
            user_id=current_user.id, 
            post_id=post_id,
            parent_id=parent_id if parent_id else None # ربط التعليق بالأب إذا وجد
        )
        db.session.add(comment)
        
        # إشعار لصاحب المنشور
        if post.user_id != current_user.id:
            notif = Notification(user_id=post.user_id, title="تعليق جديد",
                                 message=f"علق {current_user.username} على منشورك.")
            db.session.add(notif)
            
        db.session.commit()
    return redirect(url_for('community.index'))

@community_bp.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id == current_user.id or current_user.role == 'admin':
        # حذف التعليقات المرتبطة أولاً لضمان سلامة قاعدة البيانات
        Comment.query.filter_by(post_id=post_id).delete()
        PostLike.query.filter_by(post_id=post_id).delete()
        db.session.delete(post)
        db.session.commit()
        flash('تم حذف المنشور بنجاح.', 'info')
    else:
        flash('ليس لديك صلاحية لحذف هذا المنشور.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/follow/<path:username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first_or_404()
    if user == current_user:
        flash('لا يمكنك متابعة نفسك!', 'warning')
        return redirect(url_for('community.index'))

    if user in current_user.followed:
        current_user.followed.remove(user)
        flash(f'ألغيت متابعة {username}', 'info')
    else:
        current_user.followed.append(user)
        notif = Notification(user_id=user.id, title="متابع جديد",
                             message=f"بدأ {current_user.username} بمتابعتك الآن!")
        db.session.add(notif)
        flash(f'أنت الآن تتابع {username}', 'success')

    db.session.commit()
    return redirect(request.referrer or url_for('community.index'))

@community_bp.route('/force-db-update-2026')
def force_db_update():
    """تحديث قاعدة البيانات لإضافة أعمدة التعليقات المتداخلة"""
    try:
        db.session.execute(text('ALTER TABLE "comment" ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES comment(id)'))
        db.session.commit()
        return "✅ تم تحديث هيكل التعليقات بنجاح.", 200
    except Exception as e:
        db.session.rollback()
        return f"❌ خطأ في التحديث: {str(e)}", 500
