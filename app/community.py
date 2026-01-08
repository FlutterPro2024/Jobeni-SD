# ~/jobeni-sD/app/community.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Post, db, Comment, PostLike
from datetime import datetime

community_bp = Blueprint('community', __name__)

@community_bp.route('/community')
@login_required
def index():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    ai_suggestion = "شاركنا مهارة جديدة تعلمتها اليوم لتلهم زملاءك في السودان!"
    return render_template('community.html', posts=posts, ai_suggestion=ai_suggestion)

@community_bp.route('/community/post/new', methods=['POST'])
@login_required
def new_post():
    body = request.form.get('body')
    if body:
        post = Post(body=body, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('تم نشر منشورك بنجاح!', 'success')
    return redirect(url_for('community.index'))

@community_bp.route('/community/like/<int:post_id>', methods=['POST'])
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

@community_bp.route('/community/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    body = request.form.get('comment_body')
    if body:
        comment = Comment(body=body, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('community.index'))

