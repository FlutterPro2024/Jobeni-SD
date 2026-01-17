from flask import Blueprint, jsonify, request, current_app
from app.models import Job, User, Application
from app import db
from functools import wraps
import logging
from datetime import datetime

# إعداد نظام التسجيل (Logging Setup)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('JOBENI_API')

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# --- دالة الحماية مع تسجيل المحاولات ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        ip_address = request.remote_addr # تسجيل عنوان الـ IP للطلب
        
        if api_key and api_key == current_app.config.get('API_KEY'):
            return f(*args, **kwargs)
        else:
            logger.warning(f"🚨 Unauthorized access attempt! IP: {ip_address} | Path: {request.path}")
            return jsonify({
                "status": "error",
                "message": "Unauthorized: Invalid or missing API Key."
            }), 401
    return decorated_function

# --- المسارات (Endpoints) مع نظام المراقبة ---

@api_bp.route('/stats', methods=['GET'])
@require_api_key
def get_platform_stats():
    logger.info(f"📊 Stats requested by API at {datetime.now()}")
    try:
        stats = {
            "status": "success",
            "data": {
                "total_jobs": Job.query.count(),
                "total_users": User.query.count(),
                "total_applications": Application.query.count(),
                "platform_name": "Jobeni SD",
                "version": "1.4.0" 
            }
        }
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"❌ Error in stats API: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/jobs/create', methods=['POST'])
@require_api_key
def create_job_via_api():
    data = request.get_json()
    if not data or not data.get('title'):
        return jsonify({"status": "error", "message": "Missing title"}), 400
    
    try:
        new_job = Job(
            title=data.get('title'),
            company_name=data.get('company'),
            is_active=True
        )
        db.session.add(new_job)
        db.session.commit()
        
        # تسجيل عملية الإضافة
        logger.info(f"🆕 Job Created via API: ID {new_job.id} | Title: {new_job.title}")
        
        return jsonify({"status": "success", "job_id": new_job.id}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Failed to create job via API: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/jobs/delete/<int:job_id>', methods=['DELETE'])
@require_api_key
def delete_job_via_api(job_id):
    try:
        job = Job.query.get(job_id)
        if not job:
            logger.warning(f"❓ Attempt to delete non-existent job ID: {job_id}")
            return jsonify({"status": "error", "message": "Job not found"}), 404
        
        job_title = job.title # حفظ العنوان قبل الحذف للـ log
        db.session.delete(job)
        db.session.commit()
        
        # تسجيل عملية الحذف (أهم جزء في المراقبة)
        logger.info(f"🗑️ Job Deleted via API: ID {job_id} | Title: {job_title}")
        
        return jsonify({"status": "success", "message": f"Job #{job_id} deleted."}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error deleting job {job_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
