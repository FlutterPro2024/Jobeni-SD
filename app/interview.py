# ~/jobeni-sD/app/interview.py
import json, re
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Job, CV, db, InterviewReport
from app.openrouter_ai import openrouter_ai
from app.notifications import add_notification

interview_bp = Blueprint('interview', __name__)

@interview_bp.route('/interview/start/<int:job_id>')
@login_required
def start_interview(job_id):
    job = Job.query.get_or_404(job_id)
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()

    if not cv:
        return "⚠️ يرجى رفع وتحليل السيرة الذاتية أولاً لبدء المحاكاة المهنية.", 400

    prompt = f"""
    تقمص شخصية 'Senior Technical Interviewer'.
    ستقوم بإجراء مقابلة مع: {current_user.full_name or current_user.username}.
    الوظيفة: {job.title} في {job.company_name}.
    وصف الوظيفة: {job.description[:500]}
    السيرة الذاتية للمرشح: {cv.extracted_text[:1200]}

    المطلوب: رحب بالمرشح واطرح أول سؤال تقني عميق بناءً على خبراته. لغة الحوار: العربية المهنية.
    """
    first_question = openrouter_ai._call_ai(prompt, temperature=0.7)
    return render_template('interview/chat.html', job_title=job.title, first_question=first_question)

@interview_bp.route('/interview/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    user_answer = data.get('message')
    history = data.get('history', "")
    job_title = data.get('job_title')

    prompt = f"""
    سجل الحوار: {history}
    إجابة المرشح الأخيرة: "{user_answer}"
    أنت المحاور، قيم الإجابة واطرح السؤال التالي لوظيفة {job_title}.
    """
    ai_response = openrouter_ai._call_ai(prompt, temperature=0.8)
    return jsonify({'response': ai_response})

@interview_bp.route('/interview/finish', methods=['POST'])
@login_required
def finish_interview():
    data = request.json
    history = data.get('history', "")
    job_title = data.get('job_title')

    analysis_prompt = f"""
    حلل المقابلة لوظيفة '{job_title}'. السجل: {history}
    رد بصيغة JSON حصراً: {{"score": "XX%", "overall_feedback": ""}}
    """
    raw_result = openrouter_ai._call_ai(analysis_prompt, temperature=0.3)
    try:
        json_match = re.search(r'\{.*\}', raw_result, re.DOTALL)
        assessment = json.loads(json_match.group()) if json_match else {"score": "50%", "overall_feedback": "تحليل عام"}
        
        new_report = InterviewReport(
            user_id=current_user.id,
            job_title=job_title,
            full_report=assessment.get('overall_feedback', ''),
            score=assessment.get('score', '0%')
        )
        db.session.add(new_report)
        db.session.commit()
        
        add_notification(current_user.id, "اكتمل تقرير المقابلة 📊", f"تقرير {job_title} جاهز بنسبة {assessment.get('score')}", "success", "/dashboard")
    except:
        db.session.rollback()
        assessment = {"score": "50%", "overall_feedback": "حدث خطأ أثناء التحليل"}
    
    return jsonify(assessment)
