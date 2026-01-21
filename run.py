import os
from flask import request, jsonify
from app import create_app
from app.telegram_bot import handle_telegram_webhook

# تهيئة التطبيق - يختار إعدادات الإنتاج إذا كان على Vercel
app = create_app('production' if os.environ.get('VERCEL') else 'default')

# استقبال الرسائل من المسارين لضمان عدم حدوث 404 (Unified Webhook Handler)
@app.route('/webhook', methods=['POST'])
@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    try:
        # استلام البيانات بصيغة JSON من تليجرام
        data = request.get_json()
        if data:
            # تمرير البيانات للمعالج الأساسي للبوت الموجود في app/telegram_bot.py
            handle_telegram_webhook(data)
            return jsonify({"status": "success", "message": "Update processed"}), 200
        
        return jsonify({"status": "no data", "message": "No JSON payload received"}), 200
        
    except Exception as e:
        # طباعة الخطأ في سجلات Vercel للمتابعة
        print(f"❌ Error in Webhook Execution: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# مسار اختبار للتأكد من أن السيرفر يعمل عند الدخول عبر المتصفح
@app.route('/')
def index():
    return "🚀 Jobeni Bot is Running smoothly on Vercel!"

# تشغيل التطبيق محلياً (للتطوير في تيرمكس مثلاً)
if __name__ == "__main__":
    # تشغيل على بورت 5008 مع تفعيل وضع التصحيح محلياً
    app.run(debug=True, port=5008)
