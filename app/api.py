from flask import Blueprint, jsonify
from app.models import Job, User, Application

# تعريف الـ Blueprint - هذا هو المسار الرئيسي للـ API
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.route('/stats', methods=['GET'])
def get_platform_stats():
    """هذه النقطة تعيد إحصائيات المنصة بصيغة JSON"""
    try:
        stats = {
            "status": "success",
            "data": {
                "total_jobs": Job.query.count(),
                "total_users": User.query.count(),
                "total_applications": Application.query.count(),
                "platform_name": "Jobeni SD",
                "version": "1.0.0"
            }
        }
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/jobs/latest', methods=['GET'])
def get_latest_jobs():
    """جلب آخر 5 وظائف تمت إضافتها"""
    jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()
    jobs_list = []
    for job in jobs:
        jobs_list.append({
            "id": job.id,
            "title": job.title,
            "company": job.company_name,
            "location": job.location,
            "date_posted": job.created_at.strftime('%Y-%m-%d') if job.created_at else "N/A"
        })
    return jsonify({"status": "success", "jobs": jobs_list}), 200
