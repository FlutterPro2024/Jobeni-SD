# ~/jobeni-sD/app/community.py
import os
import secrets
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import Post, db, Comment, PostLike, User, Notification, Job
from datetime import datetime, timedelta
from sqlalchemy import text, or_

community_bp = Blueprint('community', __name__)

def upload_to_gyazo(form_file):
    """رفع الوسائط إلى Gyazo وتجنب مشاكل التخزين المحلي في Vercel"""
    token = os.environ.get('GYAZO_TOKEN')
    if not token:
        print("GYAZO_TOKEN is missing in environment variables")
        return None

    url = "https://upload.gyazo.com/api/upload"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # تحضير الملف للرفع
    files = {
        'imagedata': (form_file.filename, form_file.read(), form_file.content_type)
    }

    try:
        response = requests.post(url, headers=headers, files=files)
        if response.status_code == 200:
            # نأخذ 'url' لضمان الحصول على الرابط المباشر للملف
            return response.json().get('url')
    except Exception as e:
        print(f"Upload Error: {e}")
    return None

@community_bp.route('/')
@login_required
def index():
    """الرئيسية: عرض المنشورات، الأصدقاء المتصلين، واقتراحات المتابعة المهنية"""
    current_user.last_seen = datetime.utcnow()
    try:
        db.session.commit()
    except:
        db.session.rollback()

    # جلب المنشورات مرتبة من الأحدث للأقدم
    posts = Post.query.order_by(Post.timestamp.desc()).all()

    # تحديد المستخدمين المتصلين حالياً
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    online_friends = User.query.filter(
        User.last_seen >= five_mins_ago,
        User.id != current_user.id
    ).limit(10).all()

    # اقتراحات متابعة
    suggested_users = User.query.filter(
        User.id != current_user.id,
        ~User.followers.any(id=current_user.id)
    ).order_by(text("random()")).limit(5).all()

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
    """إنشاء منشور جديد مع ضمان عدم إرسال NULL لعمود body"""
    # جلب النص وضمان أنه ليس None لتجنب NotNullViolation
    content = request.form.get('body') or request.form.get('content') or ""
    
    media_file = request.files.get('media')
    media_url = None

    if media_file and media_file.filename != '':
        media_url = upload_to_gyazo(media_file)

    # السماح بالنشر إذا كان هناك نص أو رابط ميديا
    if content.strip() or media_url:
        try:
            post = Post(
                body=content, # سيرسل "" بدلاً من None إذا رفع صورة فقط
                user_id=current_user.id,
                image_file=media_url
            )
            db.session.add(post)
            db.session.commit()
            flash('تم نشر منشورك بنجاح! 🚀', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Database Error: {e}")
            flash(f'حدث خطأ أثناء حفظ المنشور في قاعدة البيانات.', 'danger')
    else:
        flash('لا يمكن نشر منشور فارغ.', 'warning')
    return redirect(url_for('community.index'))

@community_bp.route('/post/<int:post_id>/edit', methods=['POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('لا تملك صلاحية تعديل هذا المنشور.', 'danger')
        return redirect(url_for('community.index'))

    new_body = request.form.get('body')
    if new_body is not None:
        post.body = new_body
        db.session.commit()
        flash('تم تحديث المنشور بنجاح! ✨', 'success')
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
            notification = Notification(
                user_id=post.user_id,
                sender_id=current_user.id,
                post_id=post.id,
                title="إعجاب جديد",
                message=f"قام {current_user.username} بالإعجاب بمنشورك.",
                category='like'
            )
            db.session.add(notification)
    db.session.commit()
    return jsonify({'action': action, 'likes_count': post.likes.count()})

@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('comment_body')
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
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                sender_id=current_user.id,
                post_id=post.id,
                title="تعليق جديد",
                message=f"علق {current_user.username} على منشورك.",
                category='comment'
            )
            db.session.add(notification)
        db.session.commit()
        flash('تم إضافة تعليقك.', 'success')
    return redirect(url_for('community.index'))

@community_bp.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id == current_user.id or comment.post.user_id == current_user.id:
        db.session.delete(comment)
        db.session.commit()
        flash('تم حذف التعليق.', 'info')
    else:
        flash('ليس لديك صلاحية الحذف.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/follow/<username>')
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
        notification = Notification(
            user_id=user.id,
            sender_id=current_user.id,
            title="متابع جديد",
            message=f"بدأ {current_user.username} بمتابعتك الآن.",
            category='follow'
        )
        db.session.add(notification)
        flash(f'أنت الآن تتابع {username}', 'success')

    db.session.commit()
    return redirect(request.referrer or url_for('community.index'))

@community_bp.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id == current_user.id or current_user.role == 'admin':
        db.session.delete(post)
        db.session.commit()
        flash('تم حذف المنشور.', 'info')
    else:
        flash('ليس لديك صلاحية الحذف.', 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('community.index'))

    users = User.query.filter(or_(User.username.ilike(f'%{query}%'), User.full_name.ilike(f'%{query}%'))).limit(5).all()
    jobs = Job.query.filter(or_(Job.title.ilike(f'%{query}%'), Job.company_name.ilike(f'%{query}%'))).limit(5).all()
    posts = Post.query.filter(Post.body.ilike(f'%{query}%')).order_by(Post.timestamp.desc()).limit(15).all()

    return render_template('search_results.html', query=query, users=users, jobs=jobs, posts=posts)

@community_bp.route('/force-db-update-2026')
def force_db_update():
    """تحديث قاعدة البيانات برمجياً لضمان وجود الأعمدة الجديدة لعام 2026"""
    try:
        db.session.execute(text('ALTER TABLE post ADD COLUMN IF NOT EXISTS image_file VARCHAR(200)'))
        db.session.execute(text('ALTER TABLE post ADD COLUMN IF NOT EXISTS video_file VARCHAR(200)'))
        db.session.execute(text('ALTER TABLE comment ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES comment(id)'))
        db.session.commit()
        return "✅ تم تحديث هيكل قاعدة البيانات بنجاح لعام 2026.", 200
    except Exception as e:
        db.session.rollback()
        return f"❌ خطأ في التحديث: {str(e)}", 500
