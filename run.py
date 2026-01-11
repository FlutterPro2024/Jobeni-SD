# ~/jobeni-sD/run.py
import os
from app import create_app

# هذا هو الكائن 'app' الذي يبحث عنه Vercel تلقائياً عند التشغيل
# يتم اختيار إعدادات 'production' إذا كان التطبيق يعمل على Vercel، وإلا يستخدم الإعداد الافتراضي
app = create_app('production' if os.environ.get('VERCEL') else 'default')

# ملاحظة: في بيئة Vercel، يتم تجاهل هذا الجزء لأن المنصة تستدعي كائن app مباشرة
# لكنه ضروري لتشغيل التطبيق محلياً للتطوير
if __name__ == "__main__":
    # تم ضبط الديباج (debug) ليعمل فقط في البيئة المحلية لسهولة اكتشاف الأخطاء
    is_debug = False if os.environ.get('VERCEL') else True
    
    # تشغيل التطبيق على بورت 5008 محلياً
    app.run(debug=is_debug, port=5008)
