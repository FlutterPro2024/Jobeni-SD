import os
from flask import request, jsonify
from app import create_app
from app.telegram_bot import handle_telegram_webhook

# تهيئة التطبيق
app = create_app('production' if os.environ.get('VERCEL') else 'default')

# استقبال الرسائل من المسارين لضمان عدم حدوث 404
@app.route('/webhook', methods=['POST'])
@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        if data:
            # تمرير البيانات للمعالج الموجود في telegram_bot.py
            handle_telegram_webhook(data)
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "no data"}), 200
    except Exception as e:
        print(f"❌ Error in Webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# مسار إضافي للتأكد أن السيرفر شغال
@app.route('/')
def index():
    return "Jobeni Bot is Running on Vercel!"

if __name__ == "__main__":
    app.run(debug=True, port=5008)
