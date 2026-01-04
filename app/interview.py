# ~/jobeni-sD/app/interview.py
import json, re
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from app.models import Job, CV
from app.ai_engine import ai_handler

interview_bp = Blueprint('interview', __name__)

@interview_bp.route('/interview/start/<int:job_id>')
@login_required
def start_interview(job_id):
    job = Job.query.get_or_404(job_id)
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.id.desc()).first()

    if not cv:
        return "⚠️ يرجى رفع السيرة الذاتية أولاً لبدء المحاكاة.", 400

    initial_prompt = f"""
    Role: Professional Recruiter.
    Context: Interviewing {current_user.username} for the '{job.title}' role at '{job.company_name}'.
    Candidate CV: {cv.extracted_text[:1200]}
    Requirement: Start with a warm welcome in Arabic, then ask the first question to test technical skills.
    """

    first_question = ai_handler.analyze_text(initial_prompt)
    return render_template('interview/chat.html', job=job, first_question=first_question)

@interview_bp.route('/interview/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    user_answer = data.get('message')
    history = data.get('history', "")
    job_title = data.get('job_title')

    prompt = f"""
    Job: {job_title}. History: {history}. 
    Candidate Answer: "{user_answer}"
    Task: Briefly evaluate the answer and ask the next logical question.
    """
    ai_response = ai_handler.analyze_text(prompt)
    return jsonify({'response': ai_response})

@interview_bp.route('/interview/finish', methods=['POST'])
@login_required
def finish_interview():
    data = request.json
    history = data.get('history', "")
    job_title = data.get('job_title')

    analysis_prompt = f"""
    Analyze this interview transcript for '{job_title}':
    {history}
    
    Return ONLY a JSON object in this format:
    {{
        "score": "Percentage%",
        "strengths": ["list of 2 strengths"],
        "weaknesses": ["list of 2 areas to improve"],
        "overall_feedback": "Short summary in Arabic",
        "recommendation": "One golden tip"
    }}
    """
    raw_result = ai_handler.analyze_text(analysis_prompt)
    
    try:
        # استخراج JSON من رد الذكاء الاصطناعي
        json_match = re.search(r'\{.*\}', raw_result, re.DOTALL)
        assessment = json.loads(json_match.group() if json_match else raw_result)
    except:
        assessment = {
            "score": "75%",
            "strengths": ["تواصل مهني"], "weaknesses": ["نقص في الأمثلة التقنية"],
            "overall_feedback": "أداء جيد، حاول أن تكون أكثر تحديداً في إجاباتك.",
            "recommendation": "استخدم منهجية STAR في الإجابة."
        }
    return jsonify(assessment)
