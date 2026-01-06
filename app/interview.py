# ~/jobeni-sD/app/interview.py
import json, re
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Job, CV, InterviewSession, db
from app.openrouter_ai import get_ai_response # استخدام المحرك الموحد

interview_bp = Blueprint('interview', __name__)

@interview_bp.route('/interview/start/<int:job_id>')
@login_required
def start_interview(job_id):
    job = Job.query.get_or_404(job_id)
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()

    if not cv:
        return "⚠️ يرجى رفع وتحليل السيرة الذاتية أولاً لبدء المحاكاة.", 400

    prompt = f"""
    أنت الآن 'مدير توظيف' خبير. ستقوم بإجراء مقابلة مع {current_user.full_name or current_user.username}.
    الوظيفة: {job.title} في شركة {job.company_name}.
    وصف الوظيفة: {job.description[:500]}
    السيرة الذاتية للمرشح: {cv.extracted_text[:1000]}

    المطلوب:
    1. رحب بالمرشح بحرارة باللغة العربية.
    2. اطرح أول سؤال تقني عميق بناءً على التداخل بين خبرته ومتطلبات الوظيفة.
    3. اجعل الأسلوب مهنياً جداً.
    """

    first_question = get_ai_response(prompt)
    return render_template('interview/chat.html', job_title=job.title, first_question=first_question)

@interview_bp.route('/interview/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    user_answer = data.get('message')
    history = data.get('history', "")
    job_title = data.get('job_title')

    prompt = f"""
    المناقشة الحالية لوظيفة: {job_title}. 
    تاريخ الحوار: {history}
    إجابة المرشح الأخيرة: "{user_answer}"
    
    المطلوب:
    - قم بتقييم الإجابة سريعاً (صححها إذا أخطأ بذكاء).
    - اطرح السؤال التالي (نوع بين الأسئلة التقنية والسلوكية).
    - لا تخرج عن سياق المقابلة.
    """
    ai_response = get_ai_response(prompt)
    return jsonify({'response': ai_response})

@interview_bp.route('/interview/finish', methods=['POST'])
@login_required
def finish_interview():
    data = request.json
    history = data.get('history', "")
    job_title = data.get('job_title')

    analysis_prompt = f"""
    قم بتحليل سجل المقابلة التالي لوظيفة '{job_title}':
    {history}

    يجب أن يكون الرد JSON حصراً بهذا التنسيق:
    {{
        "score": "النسبة مئوية",
        "strengths": ["نقطة قوة 1", "نقطة قوة 2"],
        "weaknesses": ["نقطة تحتاج تطوير 1", "نقطة تحتاج تطوير 2"],
        "overall_feedback": "ملخص عام للأداء بالعربي",
        "recommendation": "نصيحة ذهبية للقبول"
    }}
    """
    raw_result = get_ai_response(analysis_prompt)

    try:
        json_match = re.search(r'\{.*\}', raw_result, re.DOTALL)
        assessment = json.loads(json_match.group())
        
        # حفظ النتيجة في قاعدة البيانات
        session = InterviewSession(
            user_id=current_user.id,
            skill_name=job_title,
            questions_content=json.dumps(assessment, ensure_ascii=False)
        )
        db.session.add(session)
        db.session.commit()
    except:
        assessment = {"score": "لم يتم التقييم", "overall_feedback": "حدث خطأ في معالجة النتائج."}

    return jsonify(assessment)
