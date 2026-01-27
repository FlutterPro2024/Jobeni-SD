# ~/jobeni-sD/app/admin.py
import os
from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from app.models import User, Job, Application, CV, db, Post
from sqlalchemy import func, or_
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)
MAINTENANCE_FILE = "maintenance.flag"
ANNOUNCEMENT_FILE = "announcement.txt"

@admin_bp.route('/super-admin/stats')
@login_required
def global_dashboard():
    """لوحة التحكم السيادية - محرك البحث، الإحصائيات، وجرد الأعضاء الشامل"""
    if current_user.role != 'admin':
        abort(403)

    # محرك البحث الذكي (يوزر، إيميل، أو اسم)
    search_query = request.args.get('search', '')
    if search_query:
        all_users = User.query.filter(
            or_(
                User.username.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%'),
                User.full_name.ilike(f'%{search_query}%')
            )
        ).all()
    else:
        all_users = User.query.order_by(User.id.desc()).all()

    # جرد الإحصائيات الحية
    stats = {
        'total_users': User.query.count(),
        'total_jobs': Job.query.count(),
        'total_cvs': CV.query.count(),
        'total_apps': Application.query.count(),
        'total_posts': Post.query.count(),
        'tg_users': User.query.filter(User.telegram_id != None).count()
    }

    is_maintenance = os.path.exists(MAINTENANCE_FILE)
    all_jobs = Job.query.order_by(Job.created_at.desc()).limit(20).all()
    recent_analyses = CV.query.order_by(CV.created_at.desc()).limit(10).all()

    # قراءة التعميم الحالي لعرضه في لوحة التحكم
    current_announcement = None
    if os.path.exists(ANNOUNCEMENT_FILE):
        with open(ANNOUNCEMENT_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            current_announcement = content.split("|", 1)[1] if "|" in content else content

    return render_template('admin/global_dashboard.html',
                           stats=stats,
                           all_jobs=all_jobs,
                           is_maintenance=is_maintenance,
                           recent_analyses=recent_analyses,
                           all_users=all_users,
                           search_query=search_query,
                           global_announcement=current_announcement)

@admin_bp.route('/super-admin/broadcast', methods=['POST'])
@login_required
def broadcast():
    """إرسال تعميم سيادي مع اختيار اللون (danger, success, primary)"""
    if current_user.role != 'admin': abort(403)
    message = request.form.get('message', '').strip()
    color_type = request.form.get('color_type', 'danger')
    
    if message:
        with open(ANNOUNCEMENT_FILE, "w", encoding="utf-8") as f:
            f.write(f"{color_type}|{message}")
        flash(f"🚀 تم نشر التعميم بنجاح (النوع: {color_type}).", "success")
    return redirect(url_for('admin.global_dashboard'))

@admin_bp.route('/super-admin/clear-broadcast', methods=['POST'])
@login_required
def clear_broadcast():
    """حذف التعميم الحالي من الموقع"""
    if current_user.role != 'admin': abort(403)
    if os.path.exists(ANNOUNCEMENT_FILE):
        os.remove(ANNOUNCEMENT_FILE)
        flash("🗑️ تم سحب التعميم بنجاح.", "info")
    return redirect(url_for('admin.global_dashboard'))

@admin_bp.route('/super-admin/update-role/<int:user_id>/<string:new_role>')
@login_required
def update_user_role(user_id, new_role):
    """تعديل صلاحيات الوصول (أدمن / مستخدم)"""
    if current_user.role != 'admin': abort(403)
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("🛡️ حماية سيادية: لا يمكنك تغيير رتبة حسابك الحالي!", "danger")
    else:
        user.role = new_role
        db.session.commit()
        flash(f"✅ تم تحديث رتبة {user.username} إلى {new_role} بنجاح.", "success")
    return redirect(url_for('admin.global_dashboard'))

@admin_bp.route('/super-admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """طرد مستخدم نهائياً من المنصة"""
    if current_user.role != 'admin': abort(403)
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("❌ عملية غير مسموحة: لا يمكنك حذف حسابك الإداري!", "danger")
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f"👤 تم طرد المستخدم {user.username} بنجاح.", "info")
    return redirect(url_for('admin.global_dashboard'))

@admin_bp.route('/super-admin/export-users')
@login_required
def export_users():
    """تصدير قائمة المستخدمين كملف CSV"""
    if current_user.role != 'admin': abort(403)
    users = User.query.all()
    csv_data = "ID,Username,Full Name,Email,Role\n"
    for u in users:
        csv_data += f"{u.id},{u.username},{u.full_name or 'N/A'},{u.email},{u.role}\n"
    return Response(csv_data, mimetype="text/csv", 
                    headers={"Content-disposition": "attachment; filename=users_report.csv"})

@admin_bp.route('/super-admin/toggle-maintenance', methods=['POST'])
@login_required
def toggle_maintenance():
    """تفعيل أو إيقاف وضع الصيانة"""
    if current_user.role != 'admin': abort(403)
    if os.path.exists(MAINTENANCE_FILE):
        os.remove(MAINTENANCE_FILE)
        flash("✅ تم إلغاء وضع الصيانة.", "success")
    else:
        with open(MAINTENANCE_FILE, "w") as f: f.write("on")
        flash("⚠️ تم تفعيل وضع الصيانة.", "warning")
    return redirect(url_for('admin.global_dashboard'))

@admin_bp.route('/agent-stats')
@login_required
def agent_stats():
    """مراقبة أداء ذكاء الأيجنت"""
    if current_user.role != 'admin': abort(403)
    total_matches = Application.query.filter_by(status='suggested').count()
    recent_logs = Application.query.filter_by(status='suggested').order_by(Application.applied_at.desc()).limit(10).all()
    return render_template('admin/agent_stats.html', total_matches=total_matches, recent_logs=recent_logs)
