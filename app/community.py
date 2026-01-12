# ~/jobeni-sD/app/community.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Post, db, Comment, PostLike
from datetime import datetime

community_bp = Blueprint('community', __name__)

@community_bp.route('/')
@login_required
def index():
    # التأكد من عدم وجود قيمة None في الـ avatar لمنع انهيار القالب
    if not current_user.avatar:
        current_user.avatar = 'default_avatar.png'
        try:
            db.session.commit()
        except:
            db.session.rollback()

    # استخدام timestamp بدلاً من created_at ليتوافق مع تعريف موديل Post في models.py
    try:
        posts = Post.query.order_by(Post.timestamp.desc()).all()
    except Exception as e:
        # كخيار احتياطي إذا فشل الترتيب
        print(f"Error fetching posts: {e}")
        posts = Post.query.all()

    ai_suggestion = "شاركنا مهارة جديدة تعلمتها اليوم لتلهم زملاءك في السودان!"

    return render_template('community.html', posts=posts, ai_suggestion=ai_suggestion, Comment=Comment)

@community_bp.route('/post/new', methods=['POST'])
@login_required
def new_post():
    # استلام النص من النموذج
    text_to_post = request.form.get('body') or request.form.get('content')
    
    if text_to_post:
        try:
            # تم التغيير من content= إلى body= ليتوافق مع كلاس Post في models.py
            post = Post(body=text_to_post, user_id=current_user.id)
            db.session.add(post)
            db.session.commit()
            flash('تم نشر منشورك بنجاح!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء النشر: {str(e)}', 'danger')
            print(f"Database Error: {e}")
    else:
        flash('لا يمكن نشر منشور فارغ.', 'warning')
        
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
    # استخدام body للتعليقات أيضاً ليتوافق مع كلاس Comment في models.py
    comment_text = request.form.get('comment_body') or request.form.get('content') or request.form.get('body')
    
    if comment_text:
        try:
            new_comment = Comment(body=comment_text, user_id=current_user.id, post_id=post_id)
            db.session.add(new_comment)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Comment Error: {e}")
            
    return redirect(url_for('community.index'))
