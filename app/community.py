# ~/jobeni-sD/app/community.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Post, db, Comment, PostLike, User, Notification
from datetime import datetime, timedelta
from sqlalchemy import text

community_bp = Blueprint('community', __name__)

@community_bp.route('/')
@login_required
def index():
    current_user.last_seen = datetime.utcnow()
    try:
        db.session.commit()
    except:
        db.session.rollback()

    posts = Post.query.order_by(Post.timestamp.desc()).all()
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

@community_bp.route('/force-db-update-2026')
def force_db_update():
    """تحديث قاعدة البيانات لإضافة أعمدة الوكيل الذكي"""
    try:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT FALSE'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agent_query VARCHAR(255)'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_agent_run TIMESTAMP'))
        db.session.commit()
        return "✅ تم تحديث قاعدة البيانات بنجاح (أعمدة الوكيل مضافة).", 200
    except Exception as e:
        db.session.rollback()
        return f"❌ خطأ أثناء التحديث: {str(e)}", 500

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
    post = Post.query.get_or_404(post_id)
    like = PostLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        action = 'unliked'
    else:
        new_like = PostLike(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        action = 'liked'
        if post.user_id != current_user.id:
            notif = Notification(user_id=post.user_id, title="إعجاب جديد",
                                 message=f"أعجب {current_user.username} بمنشورك.")
            db.session.add(notif)
    db.session.commit()
    likes_count = PostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'action': action, 'likes_count': likes_count})

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('comment_body')
    if content:
        post = Post.query.get_or_404(post_id)
        comment = Comment(body=content, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        if post.user_id != current_user.id:
            notif = Notification(user_id=post.user_id, title="تعليق جديد",
                                 message=f"علق {current_user.username} على منشورك.")
            db.session.add(notif)
        db.session.commit()
    return redirect(url_for('community.index'))
