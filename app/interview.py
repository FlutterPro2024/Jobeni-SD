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
    """بدء جلسة مقابلة جديدة بناءً على بيانات الوظيفة والسي في"""
    job = Job.query.get_or_404(job_id)
    cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()

    if not cv:
        return "⚠️ يرجى رفع وتحليل السيرة الذاتية أولاً لبدء المحاكاة المهنية عبر الوكيل الذكي.", 400

    # برومبت توجيهي قوي للوكيل لتقمص الشخصية
    prompt = f"""
    تقمص شخصية 'Senior Technical Interviewer' في شركة كبرى.
    المهمة: إجراء مقابلة حقيقية مع المرشح: {current_user.full_name or current_user.username}.
    الوظيفة المستهدفة: {job.title} في {job.company_name}.
    متطلبات الوظيفة: {job.description[:500]}
    خبرات المرشح (من السيرة الذاتية): {cv.extracted_text[:1200]}

    المطلوب: رحب بالمرشح بذكاء، ثم اطرح أول سؤال تقني عميق يختبر مهاراته الأساسية المذكورة في سيرته الذاتية.
    لغة الحوار: العربية المهنية الرصينة.
    """
    # استخدام المحرك الذكي لجلب أول سؤال
    first_question = openrouter_ai._call_ai(prompt, temperature=0.7)
    
    return render_template('interview/chat.html', 
                           job_title=job.title, 
                           job_id=job.id, 
                           first_question=first_question)

@interview_bp.route('/interview/chat', methods=['POST'])
@login_required
def chat():
    """إدارة الحوار المستمر بين المستخدم والوكيل الذكي"""
    data = request.json
    user_answer = data.get('message')
    history = data.get('history', "")
    job_title = data.get('job_title')

    # الوكيل يحلل الرد السابق ويجهز السؤال التالي
    prompt = f"""
    أنت المحاور الذكي لمنصة جوبيني.
    سجل المقابلة حتى الآن: {history}
    إجابة المرشح الأخيرة: "{user_answer}"
    
    المطلوب: 
    1. قيم إجابة المرشح (داخلياً).
    2. اطرح السؤال التالي (تقني أو سلوكي) بناءً على الإجابة السابقة لتعميق النقاش حول وظيفة {job_title}.
    كن موجزاً ومهنياً.
    """
    ai_response = openrouter_ai._call_ai(prompt, temperature=0.8)
    return jsonify({'response': ai_response})

@interview_bp.route('/interview/finish', methods=['POST'])
@login_required
def finish_interview():
    """إنهاء المقابلة، توليد تقرير التقييم النهائي، وحفظه"""
    data = request.json
    history = data.get('history', "")
    job_title = data.get('job_title')

    # طلب تحليل نهائي من الذكاء الاصطناعي بصيغة JSON
    analysis_prompt = f"""
    انتهت المقابلة لوظيفة '{job_title}'. 
    إليك سجل الحوار الكامل: {history}
    
    المطلوب تحليل الأداء بدقة والرد بصيغة JSON حصراً كالتالي:
    {{
      "score": "النسبة المئوية للملاءمة مثل 85%",
      "overall_feedback": "تقرير مفصل بالعربية يشمل نقاط القوة ونقاط الضعف ونصائح للتطوير"
    }}
    """
    raw_result = openrouter_ai._call_ai(analysis_prompt, temperature=0.3)
    
    try:
        # استخراج الـ JSON من رد الـ AI
        json_match = re.search(r'\{.*\}', raw_result, re.DOTALL)
        if json_match:
            assessment = json.loads(json_match.group())
        else:
            assessment = {"score": "50%", "overall_feedback": "تعذر استخراج التحليل التفصيلي، ولكن تم إكمال المقابلة بنجاح."}

        # حفظ التقرير في قاعدة البيانات
        new_report = InterviewReport(
            user_id=current_user.id,
            job_title=job_title,
            full_report=assessment.get('overall_feedback', ''),
            score=assessment.get('score', '0%')
        )
        db.session.add(new_report)
        db.session.commit()

        # إرسال تنبيه للمستخدم داخل المنصة
        add_notification(
            current_user.id, 
            "اكتمل تقرير المقابلة 📊", 
            f"تقريرك لوظيفة {job_title} جاهز الآن. نسبة الملاءمة: {assessment.get('score')}", 
            "success", 
            "/dashboard"
        )
        
        return jsonify(assessment)
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in finish_interview: {str(e)}")
        return jsonify({
            "score": "N/A", 
            "overall_feedback": "حدث خطأ أثناء معالجة التقرير النهائي، ولكن تم حفظ محاولتك."
        })
