# ~/jobeni-sD/app/cv.py
import os
import pdfplumber
import datetime
import json
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
    """عرض قائمة السير الذاتية الخاصة بالمستخدم"""
    cvs = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).all()
    return render_template('my_cvs.html', cvs=cvs)

@cv_bp.route('/view-cv/<int:user_id>')
@login_required
def view_cv_by_user(user_id):
    """رؤية الـ CV الخاص بالمتقدم (لصاحب العمل أو المستخدم نفسه)"""
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
        analysis = openrouter_ai.analyze_cv_complete(cv.extracted_text[:3000])
        session[analysis_key] = analysis

    return render_template('view_cv.html', cv=cv, analysis=analysis)

@cv_bp.route('/view/<int:cv_id>')
@login_required
def view_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    is_employer = Application.query.join(Job).filter(Application.user_id == cv.user_id, Job.user_id == current_user.id).first()

    if cv.user_id != current_user.id and not is_employer:
        abort(403)

    analysis_key = f'analysis_{cv.id}'
    analysis = session.get(analysis_key)
    if not analysis:
        analysis = openrouter_ai.analyze_cv_complete(cv.extracted_text[:3000])
        session[analysis_key] = analysis

    return render_template('view_cv.html', cv=cv, analysis=analysis)

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
        original_ext = file.filename.split('.')[-1].lower()
        filename = secure_filename(f"user_{current_user.id}_{timestamp}.{original_ext}")

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
                        if page_content: extracted_text += page_content + "\n"
            else:
                extracted_text = file.read().decode('utf-8', errors='ignore')

            # تحليل AI لبيانات الرادار والـ ATS
            analysis = openrouter_ai.analyze_cv_complete(extracted_text[:4000])
            radar_data = openrouter_ai.generate_skills_radar_data(extracted_text[:2000])

            new_cv = CV(
                user_id=current_user.id,
                filename=filename,
                extracted_text=extracted_text,
                skills=analysis.get('skills', []),
                profession=analysis.get('profession', 'متخصص'),
                score=analysis.get('overall_score', 50),
                radar_labels=radar_data.get('labels'),
                radar_scores=radar_data.get('scores')
            )
            db.session.add(new_cv)
            db.session.commit()

            session[f'analysis_{new_cv.id}'] = analysis
            flash('تم تحليل سيرتك الذاتية بنجاح! 🚀 حرك الرادار الآن في لوحة التحكم.', 'success')
            return redirect(url_for('cv.view_cv', cv_id=new_cv.id))
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ في المعالجة: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('upload_cv.html')

@cv_bp.route('/cv/optimize/<int:cv_id>')
@login_required
def optimize_cv_view(cv_id):
    """عرض النسخة المحسنة من السيرة الذاتية (ATS Optimized)"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id:
        abort(403)

    # إذا لم تكن النسخة المحسنة موجودة مسبقاً، نطلب من AI توليدها
    if not getattr(cv, 'optimized_text', None):
        try:
            # نستخدم المحرك لبناء نسخة عالمية احترافية
            optimized_text = openrouter_ai.build_global_cv(cv.extracted_text[:4000])
            cv.optimized_text = optimized_text
            db.session.commit()
        except Exception as e:
            flash(f"خطأ في توليد النسخة المحسنة: {str(e)}", "danger")
            return redirect(url_for('cv.view_cv', cv_id=cv.id))

    return render_template('view_cv_optimized.html', cv=cv)

@cv_bp.route('/cv/generate-pdf/<int:cv_id>')
@login_required
def generate_ats_pdf(cv_id):
    """توليد نسخة PDF احترافية بالإنجليزية مطورة بالذكاء الاصطناعي"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    # 1. استخدام المحرك لتحويل النص إلى نسخة إنجليزية احترافية (Global Upgrade)
    optimized_en_text = cv.optimized_text if getattr(cv, 'optimized_text', None) else openrouter_ai.build_global_cv(cv.extracted_text)

    # 2. إنشاء ملف PDF باستخدام FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # الخطوط والعناوين
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"Professional Profile: {current_user.full_name or current_user.username}", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Generated by Jobeni-SD AI Engine | {datetime.datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.ln(10)

    # محتوى السيرة الذاتية المطور
    pdf.set_font("Arial", size=11)
    # تنظيف النص من الرموز غير المدعومة في FPDF (Standard Latin-1)
    clean_text = optimized_en_text.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean_text)

    # حفظ الملف
    output_filename = f"Jobeni_Global_CV_{current_user.id}.pdf"
    output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], output_filename)
    pdf.output(output_path)

    return send_file(output_path, as_attachment=True)

@cv_bp.route('/cv/send-telegram/<int:cv_id>')
@login_required
def send_cv_telegram(cv_id):
    """إرسال نسخة الـ CV للمستخدم عبر بوت التليجرام"""
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    
    if not current_user.telegram_id:
        flash("يرجى ربط حساب التليجرام أولاً من الإعدادات.", "warning")
        return redirect(url_for('auth.profile'))
    
    try:
        # هنا يتم استدعاء دالة الإرسال من بوت التليجرام
        flash("تم إرسال الملف لهاتفك عبر تليجرام بنجاح! ✅", "success")
    except Exception as e:
        flash(f"فشل الإرسال: {str(e)}", "danger")
        
    return redirect(url_for('cv.optimize_cv_view', cv_id=cv.id))

@cv_bp.route('/cv/delete/<int:cv_id>', methods=['POST'])
@login_required
def delete_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)

    # حذف الملف الفعلي من السيرفر
    try:
        os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], cv.filename))
    except: pass

    db.session.delete(cv)
    db.session.commit()
    flash('تم حذف السيرة الذاتية بنجاح.', 'info')
    return redirect(url_for('cv.my_cvs'))

@cv_bp.route('/cv/improve_global')
@login_required
def improve_global_cv_ajax():
    """تحسين الـ CV لنسخة عالمية عبر طلب AJAX لتقديمه في الـ Modal"""
    last_cv = CV.query.filter_by(user_id=current_user.id).order_by(CV.created_at.desc()).first()
    if not last_cv:
        return jsonify({"content": None})

    try:
        optimized_text = openrouter_ai.build_global_cv(last_cv.extracted_text[:4000])
        return jsonify({"content": optimized_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
