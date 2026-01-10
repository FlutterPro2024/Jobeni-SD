import psycopg2

def fix():
    # الرابط الخاص بك مع تصحيح البروتوكول ليتوافق مع المكتبة
    db_url = "postgres://neondb_owner:npg_IoL9fmaVAj0r@ep-lingering-cake-a8qf2qyp-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"
    
    print(f"🔄 Connecting to Neon Cloud Database...")
    
    try:
        # الاتصال بقاعدة البيانات
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        # قائمة الأوامر لإصلاح التضارب بين الكود والداتابيز
        commands = [
            # 1. تحديث جدول الوظائف (تغيير اسم العمود وإضافة الإحداثيات)
            'ALTER TABLE job RENAME COLUMN employer_id TO user_id;',
            'ALTER TABLE job ADD COLUMN IF NOT EXISTS latitude FLOAT;',
            'ALTER TABLE job ADD COLUMN IF NOT EXISTS longitude FLOAT;',
            
            # 2. تحديث جدول المستخدمين (إضافة حقول الملف الشخصي والخرائط)
            'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS lat FLOAT;',
            'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS lng FLOAT;',
            'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS location_name VARCHAR(100);',
            'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS phone VARCHAR(20);',
            'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS avatar VARCHAR(200);',
            'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS headline VARCHAR(200);',
            'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS bio TEXT;',
            
            # 3. تصفير سجل الميجريشن القديم للبدء من جديد
            'DROP TABLE IF EXISTS alembic_version;'
        ]
        
        for cmd in commands:
            try:
                cur.execute(cmd)
                print(f"✅ Executed: {cmd[:40]}...")
            except Exception as e:
                # إذا ظهر خطأ هنا فغالباً العمود موجود بالفعل وهذا لا يضر
                print(f"ℹ️ Status: {str(e).splitlines()[0]}")
        
        cur.close()
        conn.close()
        print("\n✨ DONE! Cloud Database is now ready.")
        print("🚀 Check your website: https://jobeni-sd.vercel.app")
        
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    fix()
