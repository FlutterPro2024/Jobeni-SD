# ~/jobeni-sD/app/tasks.py
import requests
from app import db
from app.models import User, Job, Application, CV, AgentMemory
from app.openrouter_ai import openrouter_ai
from datetime import datetime, timedelta
import os

def send_whatsapp_ai_agent(phone, message):
    """إرسال رسالة واتساب عبر بوابة Whapi باستخدام التوكن المحدث"""
    # استخدام التوكن من البيئة أو التوكن المباشر لضمان العمل
    api_token = os.getenv('WHAPI_TOKEN') or "90tVUSCZqLPu09doejXQ11NbncyMPJC7"
    url = "https://gate.whapi.cloud/messages/text"

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_token}",
        "content-type": "application/json"
    }

    # تنظيف وتجهيز رقم التلفون للصيغة العالمية (السودان 249)
    clean_phone = str(phone).strip().replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.startswith("249"):
        if clean_phone.startswith("0"):
            clean_phone = clean_phone[1:]
        clean_phone = "249" + clean_phone

    payload = {
        "to": f"{clean_phone}@s.whatsapp.net",
        "body": message,
        "typing_time": 2
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"⚠️ WhatsApp Error: {e}")
        return False

def run_ai_agent_discovery():
    """المحرك العملاق: مطابقة صارمة + ذاكرة ذكية + فحص الأهداف (Autonomous Engine)"""
    print("🛡️ جوبيني أيجنت: بدء الفحص الفني المعمق (Autonomous Mode)...")

    # جلب المستخدمين الذين فعلوا الوكيل ولديهم رقم واتساب وسيرة ذاتية
    active_users = User.query.filter(
        User.agent_enabled == True,
        User.agent_active == True,
        User.whatsapp_number != None
    ).all()

    for user in active_users:
        cv = CV.query.filter_by(user_id=user.id).order_by(CV.created_at.desc()).first()
        if not cv or not cv.extracted_text:
            continue

        # جلب الوظائف الجديدة التي لم يتم فحصها من قبل لهذا المستخدم (باستخدام الذاكرة)
        # الوظائف المضافة في آخر 48 ساعة فقط لضمان الطزاجة
        recent_time = datetime.utcnow() - timedelta(hours=48)
        available_jobs = Job.query.filter(Job.is_active == True, Job.created_at >= recent_time).all()

        for job in available_jobs:
            # 1. فحص الذاكرة: هل تعاملنا مع هذه الوظيفة من قبل؟
            already_processed = AgentMemory.query.filter_by(user_id=user.id, job_id=str(job.id)).first()
            if already_processed:
                continue

            # 2. فحص الأهداف (Work Type): ريموت أم حضوري؟
            job_text = (job.description + job.title).lower()
            job_is_remote = any(word in job_text for word in ['remote', 'عن بعد', 'home', 'من المنزل'])

            if user.agent_work_type == 'remote' and not job_is_remote:
                continue
            if user.agent_work_type == 'onsite' and job_is_remote:
                continue

            # 3. التحليل بالذكاء الاصطناعي (البرومبت الصارم)
            prompt = (
                f"أنت خبير توظيف تقني سوداني. قارن بدقة بين السيرة الذاتية:\n({cv.extracted_text[:1200]})\n"
                f"ومتطلبات الوظيفة:\n({job.title}: {job.description[:800]}).\n\n"
                f"القواعد:\n"
                f"1. إذا كانت المطابقة أقل من {user.agent_target_score or 75}%، رد بكلمة 'REJECT' فقط.\n"
                f"2. إذا كانت مناسبة، ابدأ بكلمة 'MATCH' ثم صغ التقرير باللهجة السودانية المهنية:\n"
                f"- نسبة المطابقة: [النسبة]%\n"
                f"- ليه الوظيفة دي مكنة ليك: [نقاط القوة]\n"
                f"- ركز على الحاجات دي: [فجوات المهارات]\n"
                f"- نصيحة للمقابلة: [نصيحة ذكية]"
            )

            try:
                ai_response = openrouter_ai.get_ai_response(prompt, temperature=0.1)

                if ai_response and "MATCH" in ai_response.upper():
                    report = ai_response.upper().replace('MATCH', '').strip()
                    if report.startswith(':'): report = report[1:].strip()

                    # إرسال الواتساب
                    wa_message = (
                        f"🎯 *رادار جوبيني لقى ليك فرصة مكنة!* 🎯\n\n"
                        f"يا {user.full_name or user.username}، دي وظيفة طابقت معاييرك: *{job.title}*\n\n"
                        f"{report}\n\n"
                        f"🔗 *التفاصيل:* https://jobeni-sd.com/jobs/{job.id}\n\n"
                        f"🤖 _تم الفحص بواسطة وكيلك الذكي بناءً على هدفك ({user.agent_work_type})_"
                    )

                    if send_whatsapp_ai_agent(user.whatsapp_number, wa_message):
                        # تسجيل في الذاكرة لمنع التكرار
                        memory = AgentMemory(
                            user_id=user.id,
                            job_id=str(job.id),
                            job_title=job.title,
                            action='sent',
                            score=user.agent_target_score
                        )
                        db.session.add(memory)

                        # إضافة تطبيق مقترح في قاعدة البيانات
                        new_app = Application(
                            user_id=user.id, job_id=job.id, status='suggested',
                            match_score=85, match_explanation=report
                        )
                        db.session.add(new_app)
                        db.session.commit()
                        print(f"✅ تم إرسال {job.title} للمستخدم {user.username}")

                else:
                    # حتى لو رفضنا، نسجل في الذاكرة إننا فحصناها عشان ما نرجع ليها تاني
                    memory = AgentMemory(user_id=user.id, job_id=str(job.id), action='ignored', job_title=job.title)
                    db.session.add(memory)
                    db.session.commit()

            except Exception as e:
                db.session.rollback()
                print(f"⚠️ Error processing job {job.id} for user {user.id}: {e}")

    print("🏁 جوبيني أيجنت: انتهت جولة الفحص والذاكرة محدثة.")

def send_weekly_agent_summary():
    """إرسال تقرير الأداء الأسبوعي وتحليل الذاكرة للمستخدم"""
    print("📊 جوبيني أيجنت: جاري تجهيز التقارير الأسبوعية...")
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    active_users = User.query.filter(User.agent_enabled == True, User.whatsapp_number != None).all()

    for user in active_users:
        total_scanned = AgentMemory.query.filter(AgentMemory.user_id == user.id, AgentMemory.created_at >= one_week_ago).count()
        matches = AgentMemory.query.filter(AgentMemory.user_id == user.id, AgentMemory.action == 'sent', AgentMemory.created_at >= one_week_ago).count()

        if total_scanned == 0: continue

        summary_msg = (
            f"📅 *ملخص رادار جوبيني الأسبوعي* 📊\n\n"
            f"يا {user.full_name or user.username}، ده أداء وكيلك الذكي في آخر 7 أيام:\n\n"
            f"🔍 *فرص تم فحصها:* {total_scanned}\n"
            f"✅ *فرص تم إرسالها ليك:* {matches}\n"
            f"⏭️ *فرص استبعدها الأيجنت:* {total_scanned - matches}\n\n"
            f"💡 *تحليل الأداء:* الأيجنت شغال بفلتر ({user.agent_target_score}%). لو الفرص قليلة، جرب تقلل نسبة المطابقة شوية من الإعدادات.\n\n"
            f"ركز في أهدافك.. جوبيني معاك! 🚀"
        )
        send_whatsapp_ai_agent(user.whatsapp_number, summary_msg)

    print("🏁 جوبيني أيجنت: تم إرسال التقارير الأسبوعية.")
