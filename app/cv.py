# ~/jobeni-sD/app/cv.py
import os
import pdfplumber
import datetime
import json
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_file, session, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import CV, db, Application, Job
from app.openrouter_ai import openrouter_ai
from fpdf import FPDF
from app.telegram_bot import send_document

cv_bp = Blueprint('cv', __name__)

@cv_bp.route('/my-cvs')
@login_required
def my_cvs():
    """عرض قائمة السير الذاتية الخاصة بالمستخدم (وظائف أو منح)"""
    cvs = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).all()
    return render_template('my_cvs.html', cvs=cvs)

@cv_bp.route('/view-cv/<int:user_id>')
@login_required
def view_cv_by_user(user_id):
    """رؤية الـ CV الخاص بالمتقدم (لصاحب العمل أو لجان المنح)"""
    # التحقق من الصلاحية: هل العارض صاحب عمل تقدم له المستخدم؟
    is_candidate = Application.query.join(Job).filter(
        Application.user_id == user_id,
        Job.user_id == current_user.id
    ).first()

    if not is_candidate and current_user.id != user_id:
        flash("غير مسموح لك باستعراض هذه السيرة الذاتية.", "danger")
        return redirect(url_for('auth.dashboard'))

    cv = CV.query.filter_by(user_id=user_id).order_by(CV.created_at.desc()).first_or_404()
    analysis_key = f'analysis_{cv.id}'
    analysis = session.get(analysis_key)

    if not analysis:
        # تحديد نمط التحليل: أكاديمي للمنح أو مهني للوظائف
        is_academic = True if current_user.role == 'scholarship_seeker' else False
        analysis = openrouter_ai.analyze_cv_complete(cv.extracted_text[:3000], is_academic=is_academic)
        session[analysis_key] = analysis

    return render_template('view_cv.html', cv=cv, analysis=analysis)

@cv_bp.route('/view/<int:cv_id>')
@login_required
def view_cv(cv_id):
    """عرض تفاصيل السيرة الذاتية والتحليل الذكي"""
    cv = CV.query.get_or_404(cv_id)
    is_employer = Application.query.join(Job).filter(Application.user_id == cv.user_id, Job.user_id == current_user.id).first()

    if cv.user_id != current_user.id and not is_employer:
        abort(403)

    analysis_key = f'analysis_{cv.id}'
    analysis = session.get(analysis_key)
    if not analysis:
        is_academic = True if current_user.role == 'scholarship_seeker' else False
        analysis = openrouter_ai.analyze_cv_complete(cv.extracted_text[:3000], is_academic=is_academic)
        session[analysis_key] = analysis
        
    return render_template('view_cv.html', cv=cv, analysis=analysis)

@cv_bp.route('/upload-cv', methods=['GET', 'POST'])
@login_required
def upload_cv():
    """رفع وتحليل السيرة الذاتية بنظام الجلاد الصارم 2026"""
    if current_user.role not in ['jobseeker', 'seeker', 'scholarship_seeker']:
        flash('هذه الصفحة مخصصة للباحثين عن الفرص فقط.', 'warning')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        file = request.files.get('cv_file')
        if not file or file.filename == '':
            flash('يرجى اختيار ملف (PDF أو TXT).', 'warning')
            return redirect(request.url)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        original_ext = file.filename.split('.')[-1].lower()
        filename = secure_filename(f"user_{current_user.id}_{timestamp}.{original_ext}")
        
        path = current_app.config['UPLOAD_FOLDER']
        os.makedirs(path, exist_ok=True)
        file_full_path = os.path.join(path, filename)
        file.save(file_full_path)

        extracted_text = ""
        try:
            # استخراج النص بناءً على نوع الملف
            if original_ext == 'pdf':
                with pdfplumber.open(file_full_path) as pdf:
                    for page in pdf.pages:
                        page_content = page.extract_text()
                        if page_content: extracted_text += page_content + "\n"
            else:
                extracted_text = file.read().decode('utf-8', errors='ignore')

            # --- محرك التحليل الخبير (Scholarship vs Jobs) ---
            is_academic = (current_user.role == 'scholarship_seeker')
            
            strict_prompt = f"""
            Act as a Senior Academic Auditor and Global Technical Recruiter.
            Analyze the CV and extract metadata for {'Scholarship' if is_academic else 'Job'} matching.
            
            TEXT:
            {extracted_text[:3500]}

            RETURN ONLY VALID JSON:
            {{
                "profession": "Field of study or Job title",
                "academic_level": "BSc/MSc/PhD/HighSchool",
                "gpa": "GPA/Percentage",
                "graduation_year": YYYY,
                "university": "Name of Institution",
                "skills": ["Skill 1", "Skill 2"],
                "overall_score": 0-100,
                "feedback": "Critique for {'academic' if is_academic else 'ATS'} success"
            }}
            """
            
            analysis_res = openrouter_ai.get_ai_response(strict_prompt, temperature=0.1)

            try:
                clean_json = re.search(r'\{.*\}', analysis_res, re.DOTALL).group()
                analysis = json.loads(clean_json)
            except:
                analysis = {"profession": "باحث", "overall_score": 50, "skills": [], "gpa": "N/A"}

            # توليد بيانات الرادار المرئية
            radar_data = openrouter_ai.generate_skills_radar_data(extracted_text[:2000])

            # حفظ الكائن في قاعدة البيانات مع الحقول الأكاديمية والمهنية
            new_cv = CV(
                user_id=current_user.id,
                filename=filename,
                extracted_text=extracted_text,
                skills=analysis.get('skills', []),
                profession=analysis.get('profession'),
                score=analysis.get('overall_score', 50),
                radar_labels=radar_data.get('labels'),
                radar_scores=radar_data.get('scores'),
                gpa=str(analysis.get('gpa')),
                graduation_year=analysis.get('graduation_year') if isinstance(analysis.get('graduation_year'), int) else None,
                academic_level=analysis.get('academic_level'),
                university_name=analysis.get('university')
            )

            db.session.add(new_cv)
            db.session.commit()

            session[f'analysis_{new_cv.id}'] = analysis
            msg = 'تم تحليل ملفك الأكاديمي بنجاح! 🎓' if is_academic else 'تم تحليل سيرتك الذاتية بنجاح! 🚀'
            flash(msg, 'success')
            return redirect(url_for('cv.view_cv', cv_id=new_cv.id))

        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ في المعالجة: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('upload_cv.html')

@cv_bp.route('/cv/optimize/<int:cv_id>')
@login_required
def optimize_cv_view(cv_id):
    """تحسين الـ CV ليطابق معايير المنح العالمية أو الـ ATS"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id:
        abort(403)

    if not getattr(cv, 'optimized_text', None):
        try:
            mode = 'scholarship' if current_user.role == 'scholarship_seeker' else 'job'
            optimized_text = openrouter_ai.build_global_cv(cv.extracted_text[:4000], mode=mode)
            cv.optimized_text = optimized_text
            db.session.commit()
        except Exception as e:
            flash(f"خطأ في التحسين: {str(e)}", "danger")
            return redirect(url_for('cv.view_cv', cv_id=cv.id))

    return render_template('view_cv_optimized.html', cv=cv)

@cv_bp.route('/cv/generate-pdf/<int:cv_id>')
@login_required
def generate_ats_pdf(cv_id):
    """تحويل النسخة المحسنة إلى ملف PDF جاهز للتقديم"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    
    mode = 'scholarship' if current_user.role == 'scholarship_seeker' else 'job'
    optimized_en_text = cv.optimized_text if cv.optimized_text else openrouter_ai.build_global_cv(cv.extracted_text, mode=mode)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", 'B', 16)
    title = "Academic CV" if mode == 'scholarship' else "Professional CV"
    pdf.cell(200, 10, txt=f"{title}: {current_user.username}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=11)
    clean_text = optimized_en_text.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean_text)

    output_filename = f"Jobeni_{mode}_{current_user.id}.pdf"
    output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], output_filename)
    pdf.output(output_path)
    
    return send_file(output_path, as_attachment=True)

@cv_bp.route('/cv/send-telegram/<int:cv_id>')
@login_required
def send_cv_telegram(cv_id):
    """إرسال ملف الـ PDF المحسن مباشرة لهاتف المستخدم"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    
    if not current_user.telegram_id:
        flash("اربط تليجرام أولاً من الإعدادات.", "warning")
        return redirect(url_for('auth.profile'))

    mode = 'scholarship' if current_user.role == 'scholarship_seeker' else 'job'
    output_filename = f"Jobeni_{mode}_{current_user.id}.pdf"
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], output_filename)

    if os.path.exists(file_path):
        send_document(current_user.telegram_id, file_path, caption="ملفك الاحترافي جاهز! 🇸🇩")
        flash("وصلك الملف على تليجرام! ✅", "success")
    else:
        flash("يرجى الضغط على زر تحميل PDF أولاً لتوليد الملف.", "info")
    return redirect(url_for('cv.optimize_cv_view', cv_id=cv.id))

@cv_bp.route('/cv/delete/<int:cv_id>', methods=['POST'])
@login_required
def delete_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    try:
        os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], cv.filename))
    except: pass
    db.session.delete(cv)
    db.session.commit()
    flash('تم الحذف بنجاح.', 'info')
    return redirect(url_for('cv.my_cvs'))
