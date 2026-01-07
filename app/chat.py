# ~/jobeni-sD/app/chat.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Message, User, Job, CV, db
from app.telegram_bot import notify_new_message
# استيراد محرك OpenRouter المطور مباشرة
from app.openrouter_ai import openrouter_ai 

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat/<int:job_id>/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def open_chat(job_id, recipient_id):
    # إذا كان المستلم هو المعرف 0، فهذا يعني الدردشة مع الوكيل الذكي
    is_ai_agent = (recipient_id == 0)

    if is_ai_agent:
        recipient = User(id=0, username="ai_assistant", full_name="مساعد جوبيني الذكي 🤖")
        job = None
    else:
        job = Job.query.get(job_id) if job_id != 0 else None
        recipient = User.query.get_or_404(recipient_id)

    if request.method == 'POST':
        body = request.form.get('message')
        if body:
            try:
                # 1. حفظ رسالة المستخدم في قاعدة البيانات
                new_msg = Message(
                    sender_id=current_user.id,
                    recipient_id=recipient_id,
                    job_id=job_id if job_id != 0 else None,
                    body=body
                )
                db.session.add(new_msg)
                db.session.commit()

                # 2. إذا كانت الدردشة مع الوكيل الذكي (AI)
                if is_ai_agent:
                    # جلب السيرة الذاتية للمستخدم ليعرف المساعد مع من يتحدث
                    user_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
                    cv_text = user_cv.extracted_text if user_cv else "لا توجد سيرة ذاتية مرفوعة حالياً."
                    user_profession = user_cv.profession if user_cv else "باحث عن عمل"

                    # بناء "برومبت المستشار الخبير"
                    system_context = (
                        f"أنت الآن 'مساعد جوبيني الذكي'، مستشار مهني خبير في سوق العمل السوداني والعالمي. "
                        f"تتحدث مع المستخدم: {current_user.full_name or current_user.username}. "
                        f"تخصصه: {user_profession}. "
                        f"سيرته الذاتية المختصرة: {cv_text[:1000]}. "
                        "\nقواعدك الصارمة:\n"
                        "1. ردودك يجب أن تكون ذكية، مهنية، ومبنية على بيانات حقيقية.\n"
                        "2. ممنوع الهلوسة أو الكلام عن مواضيع خارج السياق المهني (مثل الزراعة أو المبيدات إلا لو كان المستخدم مهندس زراعي).\n"
                        "3. قدم نصائح عن الـ Remote Work، شركات الخليج، وكيفية تطوير مهارات الـ AI والبرمجيات.\n"
                        "4. استخدم لغة عربية بيضاء واضحة ومحفزة."
                    )

                    # استدعاء المحرك الجديد (الـ 23 نموذج)
                    full_prompt = f"{system_context}\n\nسؤال المستخدم: {body}"
                    ai_response = openrouter_ai._call_ai(full_prompt, temperature=0.7)

                    if not ai_response:
                        ai_response = "عذراً يا هندسة، حصل ضغط على السيرفر. ممكن تسألني تاني؟"

                    # حفظ رد الوكيل في قاعدة البيانات
                    ai_msg = Message(
                        sender_id=0,
                        recipient_id=current_user.id,
                        job_id=None,
                        body=ai_response,
                        is_read=True
                    )
                    db.session.add(ai_msg)
                    db.session.commit()

                else:
                    # 3. دردشة عادية بين أشخاص
                    if recipient.telegram_id:
                        notify_new_message(
                            recipient.telegram_id,
                            current_user.full_name or current_user.username,
                            job.title if job else "دردشة عامة",
                            body
                        )
            except Exception as e:
                db.session.rollback()
                flash(f"حدث خطأ: {str(e)}", "danger")

            return redirect(url_for('chat.open_chat', job_id=job_id, recipient_id=recipient_id))

    # جلب الرسائل السابقة
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) |
        ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    # تحديث الرسائل كمقروءة
    try:
        unread_msgs = Message.query.filter_by(recipient_id=current_user.id, sender_id=recipient_id, is_read=False).all()
        for m in unread_msgs:
            m.is_read = True
        db.session.commit()
    except:
        db.session.rollback()

    return render_template('chat.html', messages=messages, recipient=recipient, job=job, is_ai_agent=is_ai_agent)
