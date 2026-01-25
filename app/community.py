# ~/jobeni-sD/app/community.py
import os
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, current_app
from flask_login import login_required, current_user
from app.models import Post, db, Comment, PostLike, User, Notification, Message, Job  # أضفنا Job هنا
from datetime import datetime, timedelta
from sqlalchemy import text, or_
from werkzeug.utils import secure_filename

community_bp = Blueprint('community', __name__)

def save_media(form_file):
    """دالة مساعدة لمعالجة وحفظ ملفات الميديا (صور/فيديو)"""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_file.filename)
    filename = random_hex + f_ext.lower()
    # المسار: static/uploads/post_media
    upload_path = os.path.join(current_app.root_path, 'static/uploads/post_media')

    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    file_path = os.path.join(upload_path, filename)
    form_file.save(file_path)
    return filename

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

    # جلب المنشورات مرتبة من الأحدث للأقدم
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    # تحديد المستخدمين المتصلين (آخر 5 دقائق)
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    online_friends = User.query.filter(
        User.last_seen >= five_mins_ago,
        User.id != current_user.id
    ).limit(10).all()

    # خوارزمية اقتراح متابعة
    suggested_users = User.query.filter(
        User.id != current_user.id,
        ~User.followers.any(id=current_user.id)
    ).order_by(text("random()")).limit(5).all()

    # ذكاء اصطناعي لتحفيز التفاعل
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
    """إنشاء منشور جديد مع دعم الصور والفيديوهات"""
    content = request.form.get('body') or request.form.get('content')
    media_file = request.files.get('media')
    img_name = None
    vid_name = None

    # معالجة الملف المرفوع إن وجد
    if media_file and media_file.filename != '':
        ext = os.path.splitext(media_file.filename)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif']:
            img_name = save_media(media_file)
        elif ext in ['.mp4', '.mov', '.avi', '.wmv']:
            vid_name = save_media(media_file)

    if (content and len(content.strip()) > 0) or img_name or vid_name:
        try:
            post = Post(
                body=content,
                user_id=current_user.id,
                image_file=img_name,
                video_file=vid_name
            )
            db.session.add(post)
            db.session.commit()
            flash('تم نشر منشورك بنجاح! 🚀', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء النشر: {str(e)}', 'danger')
    else:
        flash('لا يمكن نشر منشور فارغ بدون محتوى أو ميديا.', 'warning')
    return redirect(url_for('community.index'))

@community_bp.route('/post/<int:post_id>/edit', methods=['POST'])
@login_required
def edit_post(post_id):
    """تعديل المنشور الخاص بالمخدم"""
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('لا تملك صلاحية تعديل هذا المنشور.', 'danger')
        return redirect(url_for('community.index'))

    new_body = request.form.get('body') or request.form.get('content')
    if new_body:
        post.body = new_body
        db.session.commit()
        flash('تم تحديث المنشور بنجاح! ✨', 'success')
    return redirect(url_for('community.index'))

@community_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    """نظام الإعجاب التفاعلي (AJAX) مع الإشعارات"""
    post = Post.query.get_or_404(post_id)
    like = PostLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if like:
        db.session.delete(like)
        action = 'unliked'
    else:
        new_like = PostLike(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        action = 'liked'
        # إضافة إشعار لصاحب المنشور
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                sender_id=current_user.id,
                post_id=post.id,
                title="إعجاب جديد",
                message=f"قام {current_user.full_name or current_user.username} بالإعجاب بمنشورك.",
                category='like'
            )
            db.session.add(notification)
    db.session.commit()
    likes_count = post.likes.count()
    return jsonify({'action': action, 'likes_count': likes_count})

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    """إضافة تعليق أو رد مع الإشعارات"""
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
        # إشعار لصاحب المنشور
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                sender_id=current_user.id,
                post_id=post.id,
                title="تعليق جديد",
                message=f"علق {current_user.username} على منشورك: '{content[:30]}...'",
                category='comment'
            )
            db.session.add(notification)
        db.session.commit()
        flash('تم إضافة تعليقك.', 'success')
    return redirect(url_for('community.index'))

@community_bp.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """حذف التعليق الخاص بالمستخدم"""
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id and current_user.role != 'admin':
        flash('ليس لديك صلاحية لحذف هذا التعليق.', 'danger')
        return redirect(url_for('community.index'))
    try:
        # حذف الردود أولاً لتجنب مشاكل الـ Foreign Key
        Comment.query.filter_by(parent_id=comment_id).delete()
        db.session.delete(comment)
        db.session.commit()
        flash('تم حذف التعليق بنجاح.', 'info')
    except:
        db.session.rollback()
        flash('حدث خطأ أثناء الحذف.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/comment/edit/<int:comment_id>', methods=['POST'])
@login_required
def edit_comment(comment_id):
    """تعديل نص التعليق"""
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        flash('غير مسموح لك بتعديل هذا التعليق.', 'danger')
        return redirect(url_for('community.index'))

    new_body = request.form.get('body') or request.form.get('comment_body')
    if new_body and len(new_body.strip()) > 0:
        comment.body = new_body
        db.session.commit()
        flash('تم تحديث التعليق بنجاح! ✨', 'success')
    else:
        flash('التعليق لا يمكن أن يكون فارغاً.', 'warning')
    return redirect(url_for('community.index'))

@community_bp.route('/follow/<username>')
@login_required
def follow(username):
    """نظام المتابعة والمتابعة العكسية مع الإشعارات"""
    user = User.query.filter_by(username=username).first_or_404()
    if user == current_user:
        flash('لا يمكنك متابعة نفسك!', 'warning')
        return redirect(url_for('community.index'))

    if user in current_user.followed:
        current_user.followed.remove(user)
        flash(f'ألغيت متابعة {user.full_name or username}', 'info')
    else:
        current_user.followed.append(user)
        # إشعار للمستخدم الجديد
        notification = Notification(
            user_id=user.id,
            sender_id=current_user.id,
            title="متابع جديد",
            message=f"بدأ {current_user.username} بمتابعتك الآن! تابع مهاراته أيضاً.",
            category='follow'
        )
        db.session.add(notification)
        flash(f'أنت الآن تتابع {user.full_name or username}', 'success')

    db.session.commit()
    return redirect(request.referrer or url_for('community.index'))

@community_bp.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    """حذف المنشور مع كافة متعلقاته بما في ذلك ملفات الميديا"""
    post = Post.query.get_or_404(post_id)
    if post.user_id == current_user.id or current_user.role == 'admin':
        # مسح الملفات الفيزيائية
        for media_file in [post.image_file, post.video_file]:
            if media_file:
                file_path = os.path.join(current_app.root_path, 'static/uploads/post_media', media_file)
                if os.path.exists(file_path):
                    os.remove(file_path)
        db.session.delete(post)
        db.session.commit()
        flash('تم حذف المنشور نهائياً.', 'info')
    else:
        flash('ليس لديك صلاحية لحذف هذا المنشور.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/search')
@login_required
def search():
    """البحث العالمي المطور (أشخاص، وظائف، منشورات)"""
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('community.index'))

    # 1. البحث عن مستخدمين (بواسطة اسم المستخدم أو الاسم الكامل)
    users = User.query.filter(
        or_(User.username.ilike(f'%{query}%'), User.full_name.ilike(f'%{query}%'))
    ).limit(5).all()

    # 2. البحث عن وظائف (في العنوان، الشركة، أو الوصف)
    jobs = Job.query.filter(
        or_(
            Job.title.ilike(f'%{query}%'),
            Job.company.ilike(f'%{query}%'),
            Job.description.ilike(f'%{query}%')
        )
    ).limit(5).all()

    # 3. البحث عن منشورات (بواسطة محتوى المنشور)
    posts = Post.query.filter(Post.body.ilike(f'%{query}%')).order_by(Post.timestamp.desc()).limit(15).all()

    return render_template('search_results.html',
                           query=query,
                           users=users,
                           jobs=jobs,
                           posts=posts)

@community_bp.route('/force-db-update-2026')
def force_db_update():
    """تحديث قاعدة البيانات لعام 2026 ودعم الميديا والردود"""
    try:
        # إضافة أعمدة الميديا والردود إذا لم تكن موجودة
        db.session.execute(text('ALTER TABLE post ADD COLUMN IF NOT EXISTS image_file VARCHAR(100)'))
        db.session.execute(text('ALTER TABLE post ADD COLUMN IF NOT EXISTS video_file VARCHAR(100)'))
        db.session.execute(text('ALTER TABLE comment ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES comment(id)'))
        db.session.commit()
        return "✅ تم تحديث هيكل قاعدة البيانات بنجاح لعام 2026 لدعم الميديا والتعليقات.", 200
    except Exception as e:
        db.session.rollback()
        return f"❌ خطأ في التحديث: {str(e)}", 500
