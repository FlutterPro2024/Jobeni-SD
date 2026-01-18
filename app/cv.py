# ~/jobeni-sD/app/cv.py
import os
import pdfplumber
import datetime
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_file, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import CV, db, Application, Job
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
    # تصحيح: استخدام user_id بدلاً من employer_id بناءً على موديل Job
    is_candidate = Application.query.join(Job).filter(
        Application.user_id == user_id,
        Job.user_id == current_user.id  # تم التصحيح هنا
    ).first()

    if not is_candidate and current_user.id != user_id:
        flash("غير مسموح لك باستعراض هذه السيرة الذاتية.", "danger")
        return redirect(url_for('auth.dashboard'))

    cv = CV.query.filter_by(user_id=user_id).order_by(CV.created_at.desc()).first_or_404()

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
    """عرض تفاصيل سيرة ذاتية محددة والتحليل الخاص بها"""
    cv = CV.query.get_or_404(cv_id)

    # تصحيح: استخدام Job.user_id للتحقق من صاحب العمل
    is_employer_of_user = Application.query.join(Job).filter(
        Application.user_id == cv.user_id,
        Job.user_id == current_user.id  # تم التصحيح هنا
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
                        if page_content:
                            extracted_text += page_content + "\n"
            elif original_ext == 'txt':
                with open(file_full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    extracted_text = f.read()

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
            flash('تم رفع وتحليل سيرتك الذاتية بنجاح! 🎯', 'success')
            return redirect(url_for('cv.view_cv', cv_id=new_cv.id))
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('upload_cv.html')

@cv_bp.route('/cv/optimize/<int:cv_id>')
@login_required
def optimize_cv_view(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    prompt = f"REWRITE this resume for ATS: {cv.extracted_text[:3000]}"
    optimized_text = openrouter_ai.generate_improved_text(prompt)
    if optimized_text:
        return render_template('cv_comparison.html', cv_id=cv.id, old_text=cv.extracted_text, new_text=optimized_text)
    flash('المحرك مشغول، حاول لاحقاً.', 'info')
    return redirect(url_for('cv.view_cv', cv_id=cv.id))

@cv_bp.route('/cv/generate-pdf/<int:cv_id>', methods=['POST'])
@login_required
def generate_ats_pdf(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    # ... بقية كود الـ PDF كما هو ...
    return redirect(url_for('cv.my_cvs'))

@cv_bp.route('/cv/delete/<int:cv_id>', methods=['POST'])
@login_required
def delete_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if cv.user_id != current_user.id: abort(403)
    db.session.delete(cv)
    db.session.commit()
    flash('تم حذف السيرة الذاتية.', 'info')
    return redirect(url_for('cv.my_cvs'))
