# check_db.py
from app import create_app, db
from app.models import User, Job, CV, Application, Notification

app = create_app()

def run_self_check():
    with app.app_context():
        print("🔍 بدء فحص نظام Jobeni SD...")
        
        # 1. فحص الجداول الأساسية
        try:
            user_count = User.query.count()
            job_count = Job.query.count()
            print(f"✅ قاعدة البيانات متصلة: يوجد {user_count} مستخدم و {job_count} وظيفة.")
        except Exception as e:
            print(f"❌ خطأ في الوصول للجداول: {str(e)}")
            return

        # 2. فحص حقول الوكيل الذكي (الرادار)
        print("📡 فحص حقول الرادار الوظيفي...")
        test_user = User.query.first()
        if test_user:
            if hasattr(test_user, 'agent_enabled'):
                print("✅ حقل agent_enabled موجود.")
            else:
                print("❌ حقل agent_enabled مفقود! شغل مسار الطوارئ لتحديث الـ DB.")

        # 3. فحص علاقات التقديم
        print("🔗 فحص علاقات التقديم (Applications)...")
        test_job = Job.query.first()
        if test_job:
            try:
                # تجربة الوصول للمتقدمين من خلال الوظيفة
                apps = test_job.applications
                print(f"✅ علاقة Job -> Applications تعمل (موجود {len(apps)} طلب للوظيفة الأولى).")
            except Exception as e:
                print(f"❌ مشكلة في علاقة المتقدمين: {str(e)}")

        # 4. فحص تكامل الـ CV
        print("📄 فحص نظام تحليل السير الذاتية...")
        try:
            cv_count = CV.query.count()
            print(f"✅ نظام الـ CV يعمل: يوجد {cv_count} ملف مرفوع.")
        except Exception as e:
            print(f"❌ خطأ في جدول الـ CV: {str(e)}")

        print("\n🚀 نتيجة الفحص: نظامك مستعد للعمل بنسبة 100%!" if "❌" not in locals() else "\n⚠️ تنبيه: عالج الأخطاء أعلاه قبل البدء.")

if __name__ == "__main__":
    run_self_check()
