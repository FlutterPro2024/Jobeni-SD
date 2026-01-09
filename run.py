import os
from app import create_app

# Vercel يحتاج فقط لرؤية الـ app بأقل قدر من الأخطاء الجانبية
app = create_app('production' if os.environ.get('VERCEL') else 'default')

if __name__ == "__main__":
    app.run()
