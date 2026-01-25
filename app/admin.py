# ~/jobeni-sD/app/admin.py
import os
from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, Job, Application, CV, db
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
        'tg_users': User.query.filter(User.telegram_id != None).count()
    }

    is_maintenance = os.path.exists(MAINTENANCE_FILE)
    all_jobs = Job.query.order_by(Job.created_at.desc()).all()
    recent_analyses = CV.query.order_by(CV.created_at.desc()).limit(10).all()

    # إحصائيات إضافية للرسم البياني للمهن
    professions_data = db.session.query(CV.profession, func.count(CV.id)).group_by(CV.profession).limit(5).all()

    return render_template('admin/global_dashboard.html',
                           stats=stats,
                           all_jobs=all_jobs,
                           is_maintenance=is_maintenance,
                           recent_analyses=recent_analyses,
                           professions=professions_data)

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
    if current_user.role != 'admin': # تأكد إن المستخدم أدمن
        return "غير مسموح", 403
        
    # إحصائيات عامة للمطابقات الصارمة (status='suggested')
    total_matches = Application.query.filter_by(status='suggested').count()
    
    # حساب مطابقات اليوم (آخر 24 ساعة)
    today_matches = Application.query.filter(
        Application.status == 'suggested',
        Application.applied_at >= datetime.utcnow() - timedelta(days=1)
    ).count()
    
    # أكثر الوظائف التي طابقها الأيجنت بنجاح
    top_jobs = db.session.query(Job.title, func.count(Application.id).label('count'))\
        .join(Application)\
        .filter(Application.status == 'suggested')\
        .group_by(Job.id)\
        .order_by(db.text('count DESC'))\
        .limit(5).all()

    # أحدث عمليات الإرسال والتحليلات الفنية الصادرة
    recent_logs = Application.query.filter_by(status='suggested')\
        .order_by(Application.applied_at.desc()).limit(10).all()

    return render_template('admin/agent_stats.html', 
                           total_matches=total_matches,
                           today_matches=today_matches,
                           top_jobs=top_jobs,
                           recent_logs=recent_logs)
