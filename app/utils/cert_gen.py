# ~/jobeni-sD/app/utils/cert_gen.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
import os

def generate_interview_cert(user_name, job_title, score):
    """
    توليد شهادة تميز احترافية بصيغة PDF
    user_name: اسم المستخدم
    job_title: الوظيفة التي تمت المقابلة عليها
    score: الدرجة من 10
    """
    # التأكد من وجود مجلد الرفع
    output_dir = "uploads"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    file_path = os.path.join(output_dir, f"cert_{user_name.replace(' ', '_')}.pdf")
    
    # إعداد الصفحة بالعرض (Landscape)
    c = canvas.Canvas(file_path, pagesize=landscape(A4))
    width, height = landscape(A4)

    # 1. رسم الخلفية والإطار الخارجي
    c.setStrokeColor(colors.gold)
    c.setLineWidth(10)
    c.rect(30, 30, width-60, height-60) # الإطار الذهبي الكبير
    
    c.setStrokeColor(colors.black)
    c.setLineWidth(2)
    c.rect(40, 40, width-80, height-80) # إطار داخلي رفيع

    # 2. إضافة شعار أو نص علوي
    c.setFont("Helvetica-BoldOblique", 14)
    c.setFillColor(colors.darkblue)
    c.drawCentredString(width/2, height-80, "JOBENI-SD SMART RECRUITMENT PLATFORM")

    # 3. العنوان الرئيسي
    c.setFont("Helvetica-Bold", 45)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height-180, "CERTIFICATE OF EXCELLENCE")

    # 4. نص التكريم
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height-240, "This prestigious certificate is proudly presented to")

    # 5. اسم المستخدم (بخط عريض ولون مميز)
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(colors.darkred)
    c.drawCentredString(width/2, height-300, user_name.upper())

    # 6. تفاصيل الإنجاز
    c.setFont("Helvetica", 18)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height-360, f"For outstanding performance in the AI-Driven Mock Interview")
    c.drawCentredString(width/2, height-390, f"Specialization: {job_title}")

    # 7. النتيجة النهائية
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(colors.darkgreen)
    c.drawCentredString(width/2, height-460, f"FINAL SCORE: {score} / 10")

    # 8. التذييل والتحقق
    c.setStrokeColor(colors.grey)
    c.line(width/2 - 150, 100, width/2 + 150, 100)
    c.setFont("Helvetica-Oblique", 12)
    c.setFillColor(colors.grey)
    c.drawCentredString(width/2, 80, "Verified by Jobeni-SD AI Career Agent")
    c.drawCentredString(width/2, 60, "Sudan's First Intelligent Job Matching Ecosystem 🇸🇩")

    c.showPage()
    c.save()
    
    return file_path

if __name__ == "__main__":
    # تجربة سريعة للملف
    test_path = generate_interview_cert("Test User", "Software Engineer", 9)
    print(f"✅ الشهادة جاهزة في: {test_path}")
