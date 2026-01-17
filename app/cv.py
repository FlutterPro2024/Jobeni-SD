# ~/jobeni-sD/app/cv.py
import os
import pdfplumber
import datetime
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_file, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import CV, db, Application, Job  # أضفنا Application و Job للتحقق من الصلاحيات
from app.openrouter_ai import openrouter_ai
from fpdf import FPDF
from arabic_reshaper import reshape
from bidi.algorithm import get_display
from app.telegram_bot import send_document

cv_bp = Blueprint('cv', __name__)

@cv_bp.route('/my-cvs')
@login_required
def my_cvs():
    """عرض قائمة السير الذاتية الخاصة بالمستخدم"""
    cvs = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).all()
    return render_template('my_cvs.html', cvs=cvs)

@cv_bp.route('/view-cv/<int:user_id>')
@login_required
def view_cv_by_user(user_id):
    """يسمح لصاحب العمل برؤية الـ CV الخاص بالمتقدم لوظائفه عبر الـ User ID"""
    # التأكد من أن المشاهد هو صاحب الـ CV نفسه أو صاحب عمل قدم له هذا المستخدم
    is_candidate = Application.query.join(Job).filter(
        Application.user_id == user_id,
        Job.employer_id == current_user.id
    ).first()

    if not is_candidate and current_user.id != user_id:
        flash("غير مسموح لك باستعراض هذه السيرة الذاتية.", "danger")
        return redirect(url_for('auth.dashboard'))

    cv = CV.query.filter_by(user_id=user_id).order_by(CV.created_at.desc()).first_or_404()
    
    # جلب التحليل من الجلسة أو توليده
    analysis_key = f'analysis_{cv.id}'
    analysis = session.get(analysis_key)
    if not analysis:
        clean_sample = " ".join(cv.extracted_text.split())[:3000]
        analysis = openrouter_ai.analyze_cv_complete(clean_sample)
        session[analysis_key] = analysis

    return render_template('view_cv.html', cv=cv, analysis=analysis)

@cv_bp.route('/view/<int:cv_id>')
@login_required
def view_cv(cv_id):
    """عرض تفاصيل سيرة ذاتية محددة والتحليل الخاص بها (معدلة للصلاحيات)"""
    cv = CV.query.get_or_404(cv_id)
    
    # السماح لصاحب الـ CV أو لصاحب العمل المرتبط بتقديم
    is_employer_of_user = Application.query.join(Job).filter(
        Application.user_id == cv.user_id,
        Job.employer_id == current_user.id
    ).first()

    if cv.user_id != current_user.id and not is_employer_of_user:
        abort(403)

    analysis_key = f'analysis_{cv.id}'
    analysis = session.get(analysis_key)

    if not analysis:
        clean_sample = " ".join(cv.extracted_text.split())[:3000]
        analysis = openrouter_ai.analyze_cv_complete(clean_sample)
        session[analysis_key] = analysis

    return render_template('view_cv.html', cv=cv, analysis=analysis)

@cv_bp.route('/upload-cv', methods=['GET', 'POST'])
@login_required
def upload_cv():
    """رفع سيرة ذاتية جديدة وتحليلها فوراً بواسطة الذكاء الاصطناعي"""
    if current_user.role not in ['jobseeker', 'seeker']:
        flash('هذه الصفحة للباحثين عن عمل فقط.', 'warning')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        file = request.files.get('cv_file')
        if not file or file.filename == '':
            flash('يرجى اختيار ملف (PDF أو TXT).', 'warning')
            return redirect(request.url)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        original_ext = file.filename.split('.')[-1].lower()
        filename = secure_filename(f"user_{current_user.id}_{timestamp}.{original_ext}")

        if original_ext not in ['pdf', 'txt']:
            flash('عذراً، النظام يدعم ملفات PDF و TXT فقط.', 'danger')
            return redirect(request.url)

        path = current_app.config['UPLOAD_FOLDER']
        os.makedirs(path, exist_ok=True)
        file_full_path = os.path.join(path, filename)
        file.save(file_full_path)

        extracted_text = ""
        try:
            if original_ext == 'pdf':
                with pdfplumber.open(file_full_path) as pdf:
                    for page in pdf.pages:
                        page_content = page.extract_text()
                        if page_content:
                            extracted_text += page_content + "\n"
            elif original_ext == 'txt':
                for encoding in ['utf-8', 'windows-1256', 'iso-8859-1']:
                    try:
                        with open(file_full_path, 'r', encoding=encoding) as f:
                            extracted_text = f.read()
                        break
                    except UnicodeDecodeError:
                        continue

            if not extracted_text.strip():
                flash('الملف فارغ أو تعذر استخراج النص منه.', 'danger')
                return redirect(request.url)

            clean_sample = " ".join(extracted_text.split())[:4000]
            analysis = openrouter_ai.analyze_cv_complete(clean_sample)

            new_cv = CV(
                user_id=current_user.id,
                filename=filename,
                extracted_text=extracted_text,
                skills=analysis.get('skills', []),
                profession=analysis.get('profession', 'متخصص تقني'),
                score=analysis.get('overall_score', 50)
            )
            db.session.add(new_cv)
            db.session.commit()

            session[f'analysis_{new_cv.id}'] = analysis

            flash('تم رفع وتحليل سيرتك الذاتية بنجاح! 🎯 تم تحديد مسار تطوير مهاراتك.', 'success')
            return redirect(url_for('cv.view_cv', cv_id=new_cv.id))
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء المعالجة: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('upload_cv.html')

@cv_bp.route('/cv/optimize/<int:cv_id>')
@login_required
def optimize_cv_view(cv_id):
    """تحسين السيرة الذاتية لتكون متوافقة مع أنظمة الـ ATS باستخدام AI"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    prompt = f"REWRITE the following resume professionally for ATS. Focus on achievements, use dynamic verbs, and keep it in English. Format with clear bullet points. Content:\n{cv.extracted_text[:3000]}"

    optimized_text = openrouter_ai.generate_improved_text(prompt)

    if optimized_text and len(optimized_text) > 100:
        final_text = optimized_text.replace("```markdown", "").replace("```", "").strip()
        final_text = final_text.replace("[Name]", current_user.full_name or current_user.username)
        final_text = final_text.replace("[Email]", current_user.email)

        return render_template('cv_comparison.html', cv_id=cv.id, old_text=cv.extracted_text, new_text=final_text)

    flash('جميع المحركات مشغولة حالياً، يرجى إعادة المحاولة.', 'info')
    return redirect(url_for('cv.view_cv', cv_id=cv.id))

@cv_bp.route('/cv/generate-pdf/<int:cv_id>', methods=['POST'])
@login_required
def generate_ats_pdf(cv_id):
    """تحويل النص المحسن إلى ملف PDF احترافي يدعم العربية والانجليزية"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    new_content = request.form.get('optimized_content', '')

    try:
        pdf = FPDF()
        pdf.add_page()

        font_path = os.path.join(current_app.root_path, 'static', 'fonts', 'Amiri-Regular.ttf')
        if os.path.exists(font_path):
            pdf.add_font('Amiri', '', font_path, uni=True)
            pdf.set_font('Amiri', size=12)
            use_unicode = True
        else:
            pdf.set_font("Arial", size=11)
            use_unicode = False

        pdf.cell(0, 10, "ATS-OPTIMIZED RESUME", ln=True, align='C')
        pdf.ln(10)

        for line in new_content.split('\n'):
            if line.strip():
                if use_unicode:
                    reshaped = reshape(line)
                    bidi_text = get_display(reshaped)
                    is_arabic = any("\u0600" <= char <= "\u06FF" for char in line)
                    pdf.multi_cell(0, 8, txt=bidi_text, align='R' if is_arabic else 'L')
                else:
                    pdf.multi_cell(0, 8, txt=line, align='L')
            else:
                pdf.ln(4)

        pdf_filename = f"Optimized_CV_{cv.id}.pdf"
        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)
        pdf.output(pdf_path)

        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        flash(f'حدث خطأ أثناء إنشاء ملف الـ PDF: {str(e)}', 'warning')
        return redirect(url_for('cv.my_cvs'))

@cv_bp.route('/cv/delete/<int:cv_id>', methods=['POST'])
@login_required
def delete_cv(cv_id):
    """حذف السيرة الذاتية وقاعدة البيانات"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    try:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cv.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    except: pass

    db.session.delete(cv)
    db.session.commit()
    flash('تم حذف السيرة الذاتية بنجاح.', 'info')
    return redirect(url_for('cv.my_cvs'))
