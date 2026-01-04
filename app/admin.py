# ~/jobeni-sD/app/admin.py
import os
from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, Job, Application, CV, db
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)
MAINTENANCE_FILE = "maintenance.flag"

@admin_bp.route('/super-admin/stats')
@login_required
def global_dashboard():
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
    
    # إحصائيات إضافية للرسم البياني
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
