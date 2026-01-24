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
    """الرئيسية: عرض المنشورات، الأصدقاء المتصلين، واقتراحات المتابعة"""
    # تحديث وقت ظهور المستخدم (Last Seen)
    current_user.last_seen = datetime.utcnow()
    try:
        db.session.commit()
    except:
        db.session.rollback()

    # جلب المنشورات مرتبة من الأحدث للأقدم مع دعم Pagination مستقبلاً
    posts = Post.query.order_by(Post.timestamp.desc()).all()

    # تحديد المستخدمين المتصلين (آخر 5 دقائق)
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    online_friends = User.query.filter(
        User.last_seen >= five_mins_ago, 
        User.id != current_user.id
    ).limit(10).all()

    # خوارزمية اقتراح متابعة (المستخدمين الأكثر نشاطاً أو الجدد)
    suggested_users = User.query.filter(
        User.id != current_user.id,
        ~User.followers.any(id=current_user.id) # اقتراح ناس ما متابعهم
    ).order_by(text("random()")).limit(5).all()

    # ذكاء اصطناعي لتحفيز التفاعل (نصيحة مهنية متغيرة)
    ai_suggestions_list = [
        "شاركنا مهارة جديدة تعلمتها اليوم لتلهم زملاءك في السودان! 🇸🇩",
        "هل تبحث عن نصيحة في مجال تقني؟ اسأل المجتمع الآن!",
        "تحديث سيرتك الذاتية هو أول خطوة للنجاح، هل جربت محلل الـ AI الخاص بنا؟",
        "الشبكات المهنية القوية تفتح أبواباً لا تفتحها الشهادات وحدها."
    ]
    import random
    ai_suggestion = random.choice(ai_suggestions_list)

    return render_template('community.html',
                           posts=posts,
                           ai_suggestion=ai_suggestion,
                           suggested_users=suggested_users,
                           online_friends=online_friends,
                           Comment=Comment)

@community_bp.route('/post/new', methods=['POST'])
@login_required
def new_post():
    """إنشاء منشور جديد مع دعم الوسائط (نصي فقط حالياً)"""
    content = request.form.get('body') or request.form.get('content')
    if content and len(content.strip()) > 0:
        try:
            post = Post(body=content, user_id=current_user.id)
            db.session.add(post)
            db.session.commit()
            flash('تم نشر منشورك بنجاح! 🚀', 'success')
        except:
            db.session.rollback()
            flash('حدث خطأ أثناء النشر، حاول مرة أخرى.', 'danger')
    else:
        flash('لا يمكن نشر منشور فارغ.', 'warning')
    return redirect(url_for('community.index'))

@community_bp.route('/post/<int:post_id>/edit', methods=['POST'])
@login_required
def edit_post(post_id):
    """تعديل المنشور الخاص بالمستخدم"""
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('لا تملك صلاحية تعديل هذا المنشور.', 'danger')
        return redirect(url_for('community.index'))
    
    new_body = request.form.get('body')
    if new_body:
        post.body = new_body
        db.session.commit()
        flash('تم تحديث المنشور بنجاح! ✨', 'success')
    return redirect(url_for('community.index'))

@community_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    """نظام الإعجاب التفاعلي (AJAX)"""
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
            from app.notifications import add_notification
            add_notification(
                user_id=post.user_id,
                message=f"أعجب {current_user.full_name or current_user.username} بمنشورك.",
                category='info'
            )
            
    db.session.commit()
    likes_count = PostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'action': action, 'likes_count': likes_count})

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    """إضافة تعليق أو رد على تعليق (Nested Comments)"""
    content = request.form.get('comment_body') or request.form.get('body')
    parent_id = request.form.get('parent_id', type=int)

    if content:
        post = Post.query.get_or_404(post_id)
        comment = Comment(
            body=content,
            user_id=current_user.id,
            post_id=post_id,
            parent_id=parent_id if parent_id else None
        )
        db.session.add(comment)
        
        # إشعار صاحب المنشور
        if post.user_id != current_user.id:
            from app.notifications import add_notification
            add_notification(
                user_id=post.user_id,
                message=f"علق {current_user.username} على منشورك: '{content[:30]}...'",
                category='primary'
            )
            
        db.session.commit()
        flash('تم إضافة تعليقك.', 'success')
    return redirect(url_for('community.index'))

@community_bp.route('/follow/<username>')
@login_required
def follow(username):
    """نظام المتابعة والمتابعة العكسية"""
    user = User.query.filter_by(username=username).first_or_404()
    if user == current_user:
        flash('لا يمكنك متابعة نفسك!', 'warning')
        return redirect(url_for('community.index'))
    
    if user in current_user.followed:
        current_user.followed.remove(user)
        flash(f'ألغيت متابعة {user.full_name or username}', 'info')
    else:
        current_user.followed.append(user)
        from app.notifications import add_notification
        add_notification(
            user_id=user.id,
            message=f"بدأ {current_user.username} بمتابعتك الآن! تابع مهاراته أيضاً.",
            category='success'
        )
        flash(f'أنت الآن تتابع {user.full_name or username}', 'success')

    db.session.commit()
    return redirect(request.referrer or url_for('community.index'))

@community_bp.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    """حذف المنشور مع كافة متعلقاته (تعليقات وإعجابات)"""
    post = Post.query.get_or_404(post_id)
    if post.user_id == current_user.id or current_user.role == 'admin':
        # حذف الإعجابات والتعليقات المرتبطة أولاً (Clean up)
        Comment.query.filter_by(post_id=post_id).delete()
        PostLike.query.filter_by(post_id=post_id).delete()
        db.session.delete(post)
        db.session.commit()
        flash('تم حذف المنشور نهائياً.', 'info')
    else:
        flash('ليس لديك صلاحية لحذف هذا المنشور.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/search_community')
@login_required
def search():
    """البحث الذكي عن المستخدمين أو المنشورات"""
    q = request.args.get('q', '')
    users = User.query.filter(
        or_(User.username.ilike(f'%{q}%'), User.full_name.ilike(f'%{q}%'))
    ).limit(10).all()
    
    posts = Post.query.filter(Post.body.ilike(f'%{q}%')).limit(10).all()
    
    return render_template('search_results.html', users=users, posts=posts, query=q)

@community_bp.route('/force-db-update-2026')
def force_db_update():
    """تحديث قاعدة البيانات لعام 2026 ودعم الردود المتسلسلة"""
    try:
        db.session.execute(text('ALTER TABLE "comment" ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES comment(id)'))
        db.session.commit()
        return "✅ تم تحديث هيكل التعليقات (Nested Comments) بنجاح لعام 2026.", 200
    except Exception as e:
        db.session.rollback()
        return f"❌ خطأ في التحديث: {str(e)}", 500
