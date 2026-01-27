# ~/jobeni-sD/app/admin.py
import os
from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, Job, Application, CV, db, Post
from sqlalchemy import func
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)
MAINTENANCE_FILE = "maintenance.flag"

@admin_bp.route('/super-admin/stats')
@login_required
def global_dashboard():
    """لوحة التحكم الشاملة لمدير النظام"""
    if current_user.role != 'admin':
        abort(403)

    stats = {
        'total_users': User.query.count(),
        'total_jobs': Job.query.count(),
        'total_cvs': CV.query.count(),
        'total_apps': Application.query.count(),
        'total_posts': Post.query.count(),  # أضفنا إحصائية المنشورات
        'tg_users': User.query.filter(User.telegram_id != None).count()
    }

    is_maintenance = os.path.exists(MAINTENANCE_FILE)
    all_jobs = Job.query.order_by(Job.created_at.desc()).all()
    recent_analyses = CV.query.order_by(CV.created_at.desc()).limit(10).all()
    
    # جلب قائمة بكل المستخدمين للجرد (الإيميلات والأسماء)
    all_users = User.query.order_by(User.id.desc()).all()

    # إحصائيات إضافية للرسم البياني للمهن
    professions_data = db.session.query(CV.profession, func.count(CV.id)).group_by(CV.profession).limit(5).all()

    return render_template('admin/global_dashboard.html',
                           stats=stats,
                           all_jobs=all_jobs,
                           is_maintenance=is_maintenance,
                           recent_analyses=recent_analyses,
                           professions=professions_data,
                           all_users=all_users) # نرسل قائمة المستخدمين للقالب

@admin_bp.route('/super-admin/toggle-maintenance', methods=['POST'])
@login_required
def toggle_maintenance():
    """تفعيل أو إيقاف وضع الصيانة للموقع بالكامل"""
    if current_user.role != 'admin':
        abort(403)

    if os.path.exists(MAINTENANCE_FILE):
        os.remove(MAINTENANCE_FILE)
        flash("✅ تم إيقاف وضع الصيانة.. الموقع متاح الآن للجميع.", "success")
    else:
        with open(MAINTENANCE_FILE, "w") as f:
            f.write("on")
        flash("⚠️ تم تفعيل وضع الصيانة.. الموقع مغلق الآن عن المستخدمين.", "warning")

    return redirect(url_for('admin.global_dashboard'))

@admin_bp.route('/agent-stats')
@login_required
def agent_stats():
    """لوحة مراقبة الأيجنت الذكي - تتبع مطابقات الواتساب والذكاء الاصطناعي"""
    if current_user.role != 'admin':
        return "غير مسموح", 403

    total_matches = Application.query.filter_by(status='suggested').count()

    today_matches = Application.query.filter(
        Application.status == 'suggested',
        Application.applied_at >= datetime.utcnow() - timedelta(days=1)
    ).count()

    top_jobs = db.session.query(Job.title, func.count(Application.id).label('count'))\
        .join(Application)\
        .filter(Application.status == 'suggested')\
        .group_by(Job.id)\
        .order_by(db.text('count DESC'))\
        .limit(5).all()

    recent_logs = Application.query.filter_by(status='suggested')\
        .order_by(Application.applied_at.desc()).limit(10).all()

    return render_template('admin/agent_stats.html',
                           total_matches=total_matches,
                           today_matches=today_matches,
                           top_jobs=top_jobs,
                           recent_logs=recent_logs)

# --- [ قسم تفعيل الأدمن السري لشركة جوبيني ] ---
@admin_bp.route('/activate-jobeni-boss-2026')
@login_required
def activate_admin_boss():
    """رابط سري لتفعيل صلاحيات الأدمن لأول مرة"""
    user = User.query.filter_by(full_name='Jobeni SD Company').first()
    if user:
        user.role = 'admin'
        db.session.commit()
        return f"✅ تم ترقية {user.full_name} إلى مدير نظام بنجاح! امسح هذا الروابط الآن."
    return "❌ لم يتم العثور على حساب بهذا الاسم الكامل (Jobeni SD Company)."
