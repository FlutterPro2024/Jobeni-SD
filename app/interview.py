# ~/jobeni-sD/app/interview.py
import json, re
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Job, CV, InterviewSession, db, InterviewReport
from app.openrouter_ai import get_ai_response

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

    المطلوب: رحب بالمرشح واطرح أول سؤال تقني عميق فوراً باللغة العربية.
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
    المناقشة لوظيفة: {job_title}. التاريخ: {history}. إجابة المرشح: "{user_answer}".
    قيم الإجابة واطرح السؤال التالي (تقني أو سلوكي) باختصار ومهنية.
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
    حلل المقابلة التالية لوظيفة '{job_title}' وأعطِ تقريراً احترافياً.
    سجل المقابلة: {history}
    يجب أن يكون الرد بصيغة JSON فقط:
    {{"score": "XX%", "strengths": [], "weaknesses": [], "overall_feedback": "", "recommendation": ""}}
    """
    raw_result = get_ai_response(analysis_prompt)

    try:
        json_match = re.search(r'\{.*\}', raw_result, re.DOTALL)
        assessment = json.loads(json_match.group())

        # حفظ التقرير في جدول التقارير لعرضه في الرسم البياني
        new_report = InterviewReport(
            user_id=current_user.id,
            job_title=job_title,
            full_report=assessment.get('overall_feedback', ''),
            score=assessment.get('score', '0%')
        )
        db.session.add(new_report)
        db.session.commit()
    except:
        assessment = {"score": "0%", "overall_feedback": "فشل في توليد التقرير"}

    return jsonify(assessment)
