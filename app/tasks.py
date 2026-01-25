# ~/jobeni-sD/app/tasks.py
import requests
from app import db
from app.models import User, Job, Application, CV
from app.openrouter_ai import openrouter_ai
from datetime import datetime, timedelta

def send_whatsapp_ai_agent(phone, message):
    """إرسال رسالة واتساب عبر بوابة Whapi باستخدام التوكن الخاص بك"""
    # التوكن الخاص بك
    api_token = "90tVUSCZqLPu09doejXQ11NbncyMPJC7"

    url = "https://gate.whapi.cloud/messages/text"

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_token}",
        "content-type": "application/json"
    }

    # تنظيف وتجهيز رقم التلفون للصيغة العالمية للسودان (إزالة المسافات، الشرطات، والزائد)
    clean_phone = str(phone).strip().replace("+", "").replace(" ", "").replace("-", "")
    
    if not clean_phone.startswith("249"):
        if clean_phone.startswith("0"):
            clean_phone = clean_phone[1:]
        clean_phone = "249" + clean_phone

    payload = {
        "to": f"{clean_phone}@s.whatsapp.net",
        "body": message,
        "typing_time": 1
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            print(f"✅ تم إرسال الواتساب بنجاح إلى: {clean_phone}")
            return True
        else:
            print(f"❌ فشل إرسال الواتساب: {response.text}")
            return False
    except Exception as e:
        print(f"⚠️ خطأ تقني في الاتصال ببوابة الواتساب: {e}")
        return False

def run_ai_agent_discovery():
    """المحرك العملاق: مطابقة صارمة + تحليل نقاط القوة والضعف (بدون مجاملة)"""
    print("🛡️ جوبيني أيجنت: بدء الفحص الفني المعمق (Zero Compromise)...")

    # جلب المستخدمين الذين فعلوا الرادار ووضعوا رقم واتساب
    active_users = User.query.filter(User.agent_enabled == True, User.whatsapp_number != None).all()

    for user in active_users:
        # جلب أحدث سيرة ذاتية للمستخدم
        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
        if not cv or not cv.extracted_text:
            continue

        # جلب الوظائف النشطة في النظام
        available_jobs = Job.query.filter_by(is_active=True).all()

        for job in available_jobs:
            # التأكد من عدم اقتراح هذه الوظيفة مسبقاً لهذا المستخدم
            already_processed = Application.query.filter_by(user_id=user.id, job_id=job.id).first()
            if already_processed:
                continue

            # البرومبت "الجراح التقني" لضمان القيمة الحقيقية
            prompt = (
                f"أنت مدقق فني صارم جداً. قارن بدقة متناهية بين CV المرشح: ({cv.extracted_text[:1000]}) "
                f"والمتطلبات الوظيفية: ({job.title}: {job.description[:600]}).\n\n"
                f"المطلوب منك تحليل حقيقي احترافي وليس مجاملة:\n"
                f"1. إذا كانت المطابقة أقل من 85%، رد بكلمة 'REJECT' فقط ولا تضف أي حرف آخر.\n"
                f"2. إذا تجاوزت المطابقة 85%، رد بكلمة 'MATCH' ثم اتبع التنسيق التالي بدقة باللهجة السودانية المهنية:\n"
                f"- نسبة الملاءمة: [النسبة]%\n"
                f"- نقاط القوة: [ما يجعله مناسباً فعلاً لهذه الوظيفة]\n"
                f"- فجوات المهارات: [ما ينقصه أو يحتاج لتطويره لسد الثغرات]\n"
                f"- نصيحة المقابلات: [نصيحة تقنية واحدة ذكية للمقابلة في هذه الوظيفة]"
            )

            try:
                ai_response = openrouter_ai.get_ai_response(prompt)
            except Exception as e:
                print(f"⚠️ خطأ في استجابة AI للمستخدم {user.username}: {e}")
                continue

            # التحقق من قرار الـ AI الصارم
            if ai_response and "MATCH" in ai_response.upper():
                # تنظيف النص من كلمة MATCH لإرسال التقرير الصافي
                report = ai_response.upper().replace('MATCH', '').strip()
                if report.startswith(':'): report = report[1:].strip()

                # صياغة رسالة الواتساب الاحترافية (الاستشارة المهنية)
                wa_message = (
                    f"🔬 *تحليل مطابقة تقني صارم* 🔬\n\n"
                    f"يا {user.full_name or user.username}، تم فحص ملفك مقابل وظيفة: *{job.title}*\n\n"
                    f"{report}\n\n"
                    f"🔗 *رابط التفاصيل والتقديم:* https://jobeni-sd.com/job/{job.id}\n\n"
                    f"⚠️ *ملاحظة:* هذا التحليل ناتج عن ذكاء اصطناعي مدقق، ننصحك بمعالجة فجوات المهارات المذكورة أعلاه لزيادة فرصك. بالتوفيق! 🇸🇩"
                )

                # تنفيذ الإرسال الحقيقي عبر الواتساب
                if send_whatsapp_ai_agent(user.whatsapp_number, wa_message):
                    # تسجيل الاقتراح في قاعدة البيانات لمنع التكرار وحفظ التحليل
                    new_app = Application(
                        user_id=user.id,
                        job_id=job.id,
                        status='suggested',
                        match_score=90, # درجة افتراضية للقبول الصارم
                        match_explanation=report
                    )
                    db.session.add(new_app)
                    db.session.commit()
                    print(f"✅ تم إرسال تقرير مفصل لـ {user.username} بخصوص {job.title}")
            else:
                # في حالة الرفض الصارم من قبل الأيجنت
                print(f"⏭️ تجاوز: المستخدم {user.username} غير مؤهل كفاية لوظيفة {job.title}")

    print("🏁 جوبيني أيجنت: انتهت جولة الفحص الصارمة بنجاح.")

def send_weekly_agent_summary():
    """إرسال تقرير أسبوعي للمستخدمين يوضح نشاط الأيجنت"""
    print("📊 جوبيني أيجنت: جاري تجهيز التقارير الأسبوعية...")
    
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    
    active_users = User.query.filter(User.agent_enabled == True, User.whatsapp_number != None).all()
    
    for user in active_users:
        # حساب عدد الوظائف التي تم فحصها (كل المحاولات في آخر 7 أيام)
        total_scanned = Job.query.filter(Job.created_at >= one_week_ago).count()
        
        # حساب عدد الوظائف التي تم ترشيحها فعلياً (MATCH)
        matches = Application.query.filter(
            Application.user_id == user.id,
            Application.status == 'suggested',
            Application.applied_at >= one_week_ago
        ).count()
        
        # حساب عدد الوظائف المستبعدة (REJECT)
        rejected = total_scanned - matches
        
        summary_msg = (
            f"📅 *تقرير رادار جوبيني الأسبوعي* 📊\n\n"
            f"يا {user.full_name or user.username}، ده ملخص نشاط الأيجنت الذكي حقك في آخر 7 أيام:\n\n"
            f"🔍 *وظائف تم فحصها:* {total_scanned}\n"
            f"✅ *فرص طابقت ملفك:* {matches}\n"
            f"⏭️ *فرص تم استبعادها لعدم الملاءمة:* {rejected}\n\n"
            f"💡 *نصيحة:* 'الاستبعاد' يعني إننا بنحمي وقتك من وظائف ما بتشبه خبرتك. لو عايز نتائج أدق، حدث الـ CV حقك باستمرار.\n\n"
            f"بالتوفيق في أسبوعك الجديد! 🚀"
        )
        
        # إرسال التقرير فقط إذا كان هناك نشاط حقيقي في النظام
        if total_scanned > 0:
            send_whatsapp_ai_agent(user.whatsapp_number, summary_msg)

    print("🏁 جوبيني أيجنت: تم إرسال التقارير الأسبوعية.")
