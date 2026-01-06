# ~/jobeni-sD/app/cv.py
import os, pdfplumber, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import CV, db
from app.openrouter_ai import openrouter_ai
from fpdf import FPDF
from app.telegram_bot import send_document

cv_bp = Blueprint('cv', __name__)

@cv_bp.route('/my-cvs')
@login_required
def my_cvs():
    # جلب جميع السير الذاتية الخاصة بالمستخدم الحالي مرتبة من الأحدث للأقدم
    cvs = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).all()
    return render_template('my_cvs.html', cvs=cvs)

@cv_bp.route('/upload-cv', methods=['GET', 'POST'])
@login_required
def upload_cv():
    if current_user.role not in ['jobseeker', 'seeker']:
        flash('هذه الصفحة للباحثين عن عمل فقط.', 'warning')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        file = request.files.get('cv_file')
        if not file or file.filename == '':
            flash('يرجى اختيار ملف (PDF أو TXT).', 'warning')
            return redirect(request.url)

        # إنشاء اسم فريد للملف لتجنب التداخل
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = secure_filename(f"user_{current_user.id}_{timestamp}_{file.filename}")
        ext = filename.split('.')[-1].lower()

        if ext not in ['pdf', 'txt']:
            flash('عذراً، النظام يدعم ملفات PDF و TXT فقط.', 'danger')
            return redirect(request.url)

        path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'cvs')
        os.makedirs(path, exist_ok=True)
        file_full_path = os.path.join(path, filename)
        file.save(file_full_path)

        text = ""
        try:
            if ext == 'pdf':
                with pdfplumber.open(file_full_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
            elif ext == 'txt':
                try:
                    with open(file_full_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                except UnicodeDecodeError:
                    with open(file_full_path, 'r', encoding='windows-1256') as f:
                        text = f.read()

            if not text.strip():
                flash('الملف فارغ أو لا يمكن قراءة النص منه.', 'danger')
                return redirect(request.url)

            clean_text = " ".join(text.split())[:2500]
            analysis = openrouter_ai.analyze_cv_complete(clean_text)

            new_cv = CV(
                user_id=current_user.id,
                file_path=filename,
                extracted_text=text,
                skills=analysis.get('skills', []),
                profession=analysis.get('profession', 'متخصص'),
                score=analysis.get('overall_score', 50),
                feedback=analysis.get('feedback', 'تم التحليل بنجاح.')
            )
            db.session.add(new_cv)
            db.session.commit()

            flash('تم رفع وتحليل السيرة الذاتية بنجاح!', 'success')
            return redirect(url_for('cv.my_cvs'))

        except Exception as e:
            db.session.rollback()
            flash(f'خطأ أثناء المعالجة: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('upload_cv.html')

@cv_bp.route('/cv/view/<int:cv_id>')
@login_required
def view_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    # السماح للمالك أو لصاحب العمل (عند التقديم) برؤية السيرة
    if cv.user_id != current_user.id and current_user.role != 'employer':
        abort(403)
    return render_template('view_cv.html', cv=cv)

@cv_bp.route('/cv/optimize/<int:cv_id>')
@login_required
def optimize_cv_view(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    prompt = (f"Write a professional ATS-optimized resume content for a {cv.profession}. "
              f"Based on: {cv.extracted_text[:1200]}. "
              f"No tags like <s> or [OUT]. Candidate: {current_user.username}")

    optimized_text = openrouter_ai._call_ai(prompt, temperature=0.4)

    if optimized_text and len(optimized_text.strip()) > 100:
        cleaned_text = optimized_text.replace("[OUT]", "").replace("[/OUT]", "").replace("<s>", "").replace("</s>", "").strip()

        final_text = cleaned_text.replace("[Jobseeker's Name]", current_user.username)\
                                .replace("[Your Name]", current_user.username)\
                                .replace("[Email Address]", current_user.email or "N/A")\
                                .replace("[Date]", datetime.date.today().strftime("%B %d, %Y"))

        return render_template('cv_comparison.html', cv_id=cv.id, old_text=cv.extracted_text, new_text=final_text)

    flash('المحرك المجاني مزدحم، تم إنشاء نسخة ذكية من بياناتك المخزنة.', 'info')
    backup_text = (f"RESUME: {current_user.username.upper()}\n"
                   f"PROFESSION: {cv.profession}\n"
                   f"SKILLS: {', '.join(cv.skills)}\n\n"
                   f"OBJECTIVE:\nHighly motivated {cv.profession} with expertise in {', '.join(cv.skills[:3])}. "
                   f"Proven ability to deliver professional results and drive technical innovation.")

    return render_template('cv_comparison.html', cv_id=cv.id, old_text=cv.extracted_text, new_text=backup_text)

@cv_bp.route('/cv/generate-pdf/<int:cv_id>', methods=['POST'])
@login_required
def generate_ats_pdf(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    new_content = request.form.get('optimized_content', '')
    cv.optimized_text = new_content
    cv.score = max((cv.score or 0), 85)
    db.session.commit()

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "ATS-OPTIMIZED RESUME", ln=True, align='C')
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        clean_text = new_content.encode("latin-1", "ignore").decode("latin-1")

        for line in clean_text.split('\n'):
            if line.strip():
                pdf.multi_cell(0, 7, txt=line.strip())
            else:
                pdf.ln(3)

        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"Optimized_CV_{cv.id}.pdf")
        pdf.output(pdf_path)

        if current_user.telegram_id:
            try:
                send_document(current_user.telegram_id, pdf_path, caption="✅ إليك سيرتك الذاتية المحسنة!")
            except: pass

        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        print(f"PDF Generation Error: {e}")
        flash('تم حفظ التعديلات، ولكن تعذر إنشاء ملف PDF حالياً.', 'warning')
        return redirect(url_for('cv.view_cv', cv_id=cv.id))

@cv_bp.route('/cv/delete/<int:cv_id>', methods=['POST'])
@login_required
def delete_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    
    # محاولة حذف الملف من السيرفر قبل حذف السجل من القاعدة
    try:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'cvs', cv.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"File Deletion Error: {e}")

    db.session.delete(cv)
    db.session.commit()
    flash('تم حذف السيرة الذاتية بنجاح.', 'info')
    return redirect(url_for('cv.my_cvs'))

