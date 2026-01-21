import os
from flask import request
from app import create_app
# بنستورد معالج الرسايل اللي إنت كاتبه أصلاً في app/telegram_bot.py
from app.telegram_bot import handle_telegram_webhook

app = create_app('production' if os.environ.get('VERCEL') else 'default')

# المسار اللي تليجرام حيرسل فيه الرسايل
@app.route('/telegram/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        # استلام الداتا من تليجرام
        update = request.get_json()
        if update:
            # تمرير الداتا للمعالج الأصلي بتاعك
            handle_telegram_webhook(update)
        return "OK", 200
    return "Method Not Allowed", 405

if __name__ == "__main__":
    is_debug = False if os.environ.get('VERCEL') else True
    app.run(debug=is_debug, port=5008)
