from flask import Blueprint, jsonify, request, current_app
from app.models import Job, User, Application
from app import db
from functools import wraps

# تعريف الـ Blueprint - هذا هو المسار الرئيسي للـ API
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# --- دالة الحماية (المزخرف الآمن) ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # البحث عن المفتاح في الـ Header باسم X-API-KEY
        api_key = request.headers.get('X-API-KEY')

        # مقارنة المفتاح المرسل بالمفتاح الموجود في config.py
        if api_key and api_key == current_app.config.get('API_KEY'):
            return f(*args, **kwargs)
        else:
            return jsonify({
                "status": "error",
                "message": "Unauthorized: Invalid or missing API Key. Please provide X-API-KEY in headers."
            }), 401
    return decorated_function

# --- المسارات (Endpoints) ---

@api_bp.route('/stats', methods=['GET'])
@require_api_key  # تفعيل الحماية لهذا المسار
def get_platform_stats():
    """هذه النقطة تعيد إحصائيات المنصة بصيغة JSON محمية"""
    try:
        stats = {
            "status": "success",
            "data": {
                "total_jobs": Job.query.count(),
                "total_users": User.query.count(),
                "total_applications": Application.query.count(),
                "platform_name": "Jobeni SD",
                "version": "1.3.0" 
            }
        }
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/jobs/latest', methods=['GET'])
@require_api_key  # تفعيل الحماية لهذا المسار أيضاً
def get_latest_jobs():
    """جلب آخر 5 وظائف تمت إضافتها بشكل مؤمن"""
    try:
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
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ميزة إضافة وظيفة جديدة عبر الـ API (POST Method) ---

@api_bp.route('/jobs/create', methods=['POST'])
@require_api_key
def create_job_via_api():
    """إضافة وظيفة جديدة لقاعدة البيانات عبر طلب JSON خارجي"""
    data = request.get_json()
    
    # التحقق من وجود البيانات المطلوبة
    if not data or not data.get('title') or not data.get('company'):
        return jsonify({
            "status": "error", 
            "message": "Missing required fields: title and company are mandatory."
        }), 400
    
    try:
        new_job = Job(
            title=data.get('title'),
            company_name=data.get('company'),
            description=data.get('description', 'No description provided via API'),
            location=data.get('location', 'Sudan / Remote'),
            job_type=data.get('job_type', 'Full-time'),
            is_active=True
        )
        
        db.session.add(new_job)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Job successfully created!",
            "job_id": new_job.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# --- ميزة حذف وظيفة عبر الـ API (DELETE Method) ---

@api_bp.route('/jobs/delete/<int:job_id>', methods=['DELETE'])
@require_api_key
def delete_job_via_api(job_id):
    """حذف وظيفة محددة باستخدام الـ ID الخاص بها"""
    try:
        job = Job.query.get(job_id)
        if not job:
            return jsonify({
                "status": "error", 
                "message": f"Job with ID {job_id} not found."
            }), 404
        
        db.session.delete(job)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": f"Job #{job_id} deleted successfully."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
