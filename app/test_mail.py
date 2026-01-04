import os
from app.notifications import send_job_alert

# اختبر الإرسال لبريدك
test_jobs = [
    {'title': 'AI Engineer', 'link': 'https://linkedin.com'},
    {'title': 'Data Scientist', 'link': 'https://indeed.com'}
]

print("⏳ جاري محاولة إرسال إيميل تجريبي...")
success = send_job_alert("jobeni-sd7@gmail.com", "مطور جوبيني", "الذكاء الاصطناعي", test_jobs)

if success:
    print("✨ نجحت العملية! افحص بريدك الإلكتروني الآن (البريد الوارد أو Junk).")
else:
    print("💥 فشلت العملية. راقب الأخطاء في الأعلى وتأكد من الـ .env")
