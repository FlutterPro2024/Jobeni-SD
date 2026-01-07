# ~/jobeni-sD/app/interview.py
import json, re
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Job, CV, InterviewSession, db, InterviewReport
# استدعاء المحرك المطور
from app.openrouter_ai import openrouter_ai 

interview_bp = Blueprint('interview', __name__)

@interview_bp.route('/interview/start/<int:job_id>')
@login_required
def start_interview(job_id):
    job = Job.query.get_or_404(job_id)
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    
    if not cv:
        return "⚠️ يرجى رفع وتحليل السيرة الذاتية أولاً لبدء المحاكاة المهنية.", 400

    # برومبت البداية: تقمص شخصية خبير تقني
    prompt = f"""
    تقمص شخصية 'Senior Technical Interviewer' في شركة عالمية. 
    ستقوم بإجراء مقابلة مع المهندس: {current_user.full_name or current_user.username}.
    الوظيفة المستهدفة: {job.title} في شركة {job.company_name}.
    وصف الوظيفة: {job.description[:500]}
    السيرة الذاتية للمرشح: {cv.extracted_text[:1200]}

    المطلوب منك:
    1. رحب بالمرشح بوقار مهني.
    2. اطرح سؤالاً تقنياً عميقاً يختبر مهاراته المذكورة في الـ CV وعلاقتها بالوظيفة.
    3. لغة الحوار: العربية الفصحى البسيطة والمهنية.
    """
    
    # استخدام المحرك الجديد
    first_question = openrouter_ai._call_ai(prompt, temperature=0.7)
    return render_template('interview/chat.html', job_title=job.title, first_question=first_question)

@interview_bp.route('/interview/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    user_answer = data.get('message')
    history = data.get('history', "")
    job_title = data.get('job_title')

    # برومبت المتابعة: تحليل الإجابة وتعميق النقاش
    prompt = f"""
    أنت في منتصف مقابلة تقنية لوظيفة: {job_title}.
    سجل الحوار السابق: {history}
    إجابة المرشح الأخيرة: "{user_answer}"

    المطلوب:
    1. قيم إجابة المرشح داخلياً (إذا كانت ناقصة أو خاطئة، وجهه أو اطلب منه توضيحاً).
    2. اطرح سؤالاً تالياً (تقني أو سلوكي) بناءً على إجابته الأخيرة.
    3. كن حازماً ومهنياً، ولا تخرج عن سياق الوظيفة.
    """
    
    ai_response = openrouter_ai._call_ai(prompt, temperature=0.8)
    return jsonify({'response': ai_response})

@interview_bp.route('/interview/finish', methods=['POST'])
@login_required
def finish_interview():
    data = request.json
    history = data.get('history', "")
    job_title = data.get('job_title')

    # برومبت التقييم النهائي: توليد تقرير JSON دقيق للرسم البياني
    analysis_prompt = f"""
    بصفتك لجنة تقييم خبراء، حلل هذه المقابلة لوظيفة '{job_title}'.
    سجل المقابلة الكامل: {history}

    المطلوب رد بصيغة JSON فقط بهذا التنسيق (مهم جداً للرسم البياني):
    {{
        "score": "رقم من 0-100 فقط متبوع بـ %",
        "strengths": ["نقطة قوة 1", "نقطة قوة 2"],
        "weaknesses": ["نقطة ضعف 1", "نقطة ضعف 2"],
        "overall_feedback": "تقييم شامل لأدائه المهني",
        "recommendation": "نصيحة محددة لتطوير نفسه"
    }}
    """
    
    raw_result = openrouter_ai._call_ai(analysis_prompt, temperature=0.3)
    
    try:
        # استخراج JSON من الرد (في حال أضاف الـ AI أي نص خارجي)
        json_match = re.search(r'\{.*\}', raw_result, re.DOTALL)
        if json_match:
            assessment = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found")

        # حفظ التقرير في قاعدة البيانات ليظهر في الـ Dashboard
        new_report = InterviewReport(
            user_id=current_user.id,
            job_title=job_title,
            full_report=assessment.get('overall_feedback', ''),
            score=assessment.get('score', '0%')
        )
        db.session.add(new_report)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error parsing assessment: {e}")
        assessment = {
            "score": "50%", 
            "overall_feedback": "نعتذر، حدث خطأ في تحليل التقرير ولكن أدائك كان جيداً.",
            "strengths": ["محاولة جيدة"],
            "weaknesses": ["خطأ تقني في التحليل"],
            "recommendation": "أعد المحاولة لاحقاً"
        }

    return jsonify(assessment)
