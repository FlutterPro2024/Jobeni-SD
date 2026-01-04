from app import create_app, db
from app.models import User, Job, CV

app = create_app()
with app.app_context():
    users_count = User.query.count()
    jobs_count = Job.query.count()
    cvs_count = CV.query.count()
    
    print(f"--- تقرير النظام ---")
    print(f"👤 عدد المستخدمين: {users_count}")
    print(f"💼 عدد الوظائف المتاحة: {jobs_count}")
    print(f"📄 عدد السير المرفوعة: {cvs_count}")
    print(f"✅ الربط سليم!")
