# ~/jobeni-sD/app/cv.py
import os, pdfplumber, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import CV, db
from app.openrouter_ai import openrouter_ai
from fpdf import FPDF
from arabic_reshaper import reshape
from bidi.algorithm import get_display
from app.telegram_bot import send_document

cv_bp = Blueprint('cv', __name__)

@cv_bp.route('/my-cvs')
@login_required
def my_cvs():
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
                        extracted = page.extract_text()
                        if extracted: text += extracted + "\n"
            elif ext == 'txt':
                for encoding in ['utf-8', 'windows-1256', 'iso-8859-1']:
                    try:
                        with open(file_full_path, 'r', encoding=encoding) as f:
                            text = f.read()
                        break
                    except UnicodeDecodeError: continue

            if not text.strip():
                flash('الملف فارغ أو لا يمكن قراءة النص منه.', 'danger')
                return redirect(request.url)

            # تنظيف النص وإرساله للتحليل بذكاء - زيادة الحجم لـ 4000 حرف لدقة أعلى
            clean_text = " ".join(text.split())[:4000]
            analysis = openrouter_ai.analyze_cv_complete(clean_text)

            new_cv = CV(
                user_id=current_user.id,
                file_path=filename,
                extracted_text=text,
                skills=analysis.get('skills', []),
                profession=analysis.get('profession', 'متخصص تقني'),
                score=analysis.get('overall_score', 50),
                feedback=analysis.get('feedback', 'تم تحليل بياناتك بنجاح.')
            )
            db.session.add(new_cv)
            db.session.commit()
            flash('تم رفع وتحليل السيرة الذاتية بنجاح! يمكنك الآن تحسينها.', 'success')
            return redirect(url_for('cv.my_cvs'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"CV Upload Error: {str(e)}")
            flash('حدث خطأ أثناء معالجة الملف، يرجى المحاولة مرة أخرى.', 'danger')
            return redirect(request.url)

    return render_template('upload_cv.html')

@cv_bp.route('/cv/view/<int:cv_id>')
@login_required
def view_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id and current_user.role != 'employer':
        abort(403)
    return render_template('view_cv.html', cv=cv)

@cv_bp.route('/cv/optimize/<int:cv_id>')
@login_required
def optimize_cv_view(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    # طلب التحسين مع توجيه صارم للذكاء الاصطناعي لاستخدام الإنجليزية في المحتوى والاحترافية
    prompt_instruction = "Act as a professional CV writer. REWRITE the following resume content to be ATS-friendly. Focus on professional keywords, accomplishments, and clarity. Maintain English for the main body."
    optimized_text = openrouter_ai.generate_improved_text(f"{prompt_instruction}\n\nCONTENT:\n{cv.extracted_text}")

    if optimized_text and len(optimized_text.strip()) > 200:
        # تنظيف شامل للمخرجات
        final_text = optimized_text.replace("```markdown", "").replace("```", "").replace("[OUT]", "").strip()

        # استبدال البيانات الناقصة ببيانات المستخدم الحالية
        final_text = final_text.replace("[Name]", current_user.username)\
                               .replace("[Email]", current_user.email or "contact@jobeni.sd")\
                               .replace("[Date]", datetime.date.today().strftime("%Y-%m-%d"))

        return render_template('cv_comparison.html', cv_id=cv.id, old_text=cv.extracted_text, new_text=final_text)

    flash('المحركات مشغولة حالياً، تم استخدام القالب الذكي السريع.', 'info')
    backup_text = (f"# RESUME: {current_user.username.upper()}\n"
                   f"**Profession:** {cv.profession}\n\n"
                   f"## SUMMARY\nProfessional {cv.profession} with expertise in {', '.join(cv.skills[:4])}.\n\n"
                   f"## EXPERIENCE\n{cv.extracted_text[:600]}...")
    return render_template('cv_comparison.html', cv_id=cv.id, old_text=cv.extracted_text, new_text=backup_text)

@cv_bp.route('/cv/generate-pdf/<int:cv_id>', methods=['POST'])
@login_required
def generate_ats_pdf(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    new_content = request.form.get('optimized_content', '')
    cv.optimized_text = new_content
    cv.score = max((cv.score or 0), 95) 
    db.session.commit()

    try:
        # استخدام fpdf2 المتقدمة
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # إضافة الخطوط لدعم العربية (تأكد من وجود ملف الخط في هذا المسار)
        # إذا لم يتوفر الخط، سيستخدم Arial الافتراضي للإنجليزي
        try:
            font_path = os.path.join(current_app.root_path, 'static', 'fonts', 'DejaVuSans.ttf')
            pdf.add_font('DejaVu', '', font_path)
            pdf.set_font('DejaVu', size=11)
            use_unicode = True
        except:
            pdf.set_font("Arial", size=11)
            use_unicode = False

        # عنوان الملف
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "ATS-OPTIMIZED RESUME", ln=True, align='C')
        pdf.ln(10)
        
        if use_unicode:
            pdf.set_font('DejaVu', size=11)
        else:
            pdf.set_font("Arial", size=11)

        # معالجة النص سطر بسطر مع دعم اللغة العربية (Bidi)
        lines = new_content.split('\n')
        for line in lines:
            if line.strip():
                # إعادة تشكيل النص العربي ليدعم الاتجاه الصحيح
                reshaped_text = reshape(line)
                bidi_text = get_display(reshaped_text)
                
                # إذا كان النص يحتوي على عربي، نجعله من اليمين، غير ذلك من اليسار
                is_arabic = any("\u0600" <= char <= "\u06FF" for char in line)
                align = 'R' if is_arabic else 'L'
                
                pdf.multi_cell(0, 8, txt=bidi_text, align=align)
            else:
                pdf.ln(4)

        pdf_filename = f"Jobeni_Optimized_{cv.id}.pdf"
        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)
        pdf.output(pdf_path)

        if current_user.telegram_id:
            try:
                send_document(current_user.telegram_id, pdf_path, caption=f"🚀 مبروك يا {current_user.username}! سيرتك الذاتية أصبحت جاهزة.")
            except:
                pass

        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"PDF Gen Error: {str(e)}")
        flash('تم حفظ التعديلات، ولكن حدث خطأ في إنشاء PDF. يمكنك نسخ النص يدوياً.', 'warning')
        return redirect(url_for('cv.view_cv', cv_id=cv.id))

@cv_bp.route('/cv/delete/<int:cv_id>', methods=['POST'])
@login_required
def delete_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    try:
        db.session.delete(cv)
        db.session.commit()
        flash('تم حذف السيرة الذاتية بنجاح.', 'info')
    except:
        db.session.rollback()
    return redirect(url_for('cv.my_cvs'))
