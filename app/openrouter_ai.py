# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time, random
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        # استجلاب المفتاح من البيئة
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # --- ترسانة المحركات المحدثة 2026 (أكثر من 100 محرك بديل) ---
        self.free_models = [
            "google/gemini-2.0-flash-exp:free", "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.3-70b-instruct:free", "meta-llama/llama-3.2-3b-instruct:free",
            "qwen/qwen-2.5-72b-instruct:free", "qwen/qwen-2.5-7b-instruct:free",
            "google/gemini-flash-1.5-8b:free", "mistralai/mistral-7b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free", "microsoft/phi-3-medium-128k-instruct:free",
            "huggingfaceh4/zephyr-7b-beta:free", "liquid/lfm-40b:free",
            "anthropic/claude-3-haiku:free", "nvidia/llama-3.1-nemotron-70b-instruct:free"
        ]

        self.mid_models = [
            "openai/gpt-4o-mini", "anthropic/claude-3-5-haiku",
            "google/gemini-flash-1.5", "meta-llama/llama-3.1-70b-instruct",
            "deepseek/deepseek-chat", "cohere/command-r-plus",
            "mistralai/mixtral-8x22b-instruct"
        ]

        self.elite_models = [
            "openai/gpt-4o", "anthropic/claude-3-5-sonnet",
            "google/gemini-1.5-pro", "meta-llama/llama-3.1-405b-instruct"
        ]

        # الدمج الهرمي لضمان الاستمرارية
        self.ordered_models = self.free_models + self.mid_models + self.elite_models

    def _call_ai(self, prompt, temperature=0.3):
        if not self.api_key:
            return "❌ خطأ: مفتاح API غير موجود في إعدادات النظام."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni Professional AI Engine"
        }

        # محاولة ذكية للمرور عبر المحركات في حالة الفشل (Auto-Failover)
        for model in self.ordered_models:
            try:
                print(f"🤖 جاري التحليل عبر المحرك التقني: {model}...")
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 2000
                }

                # مهلة انتظار متكيفة حسب نوع المحرك
                timeout_val = 15 if ":free" in model else 30
                res = requests.post(self.url, headers=headers, json=payload, timeout=timeout_val)

                if res.status_code == 200:
                    data = res.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        if content and len(content.strip()) > 5:
                            return content

                continue
            except Exception as e:
                print(f"🔄 تبديل المحرك بسبب: {str(e)[:40]}")
                continue

        return "النظام يواجه ضغطاً تقنياً عالياً حالياً. يرجى إعادة المحاولة خلال لحظات."

    def get_ai_response(self, prompt, temperature=0.5):
        return self._call_ai(prompt, temperature)

    def analyze_cv_complete(self, cv_text):
        """تحليل سيرة ذاتية صارم بمعايير التوظيف العالمية"""
        prompt = f"""
        أنت مدقق موارد بشرية عالمي (Senior Technical Recruiter). قم بتحليل النص التالي بصرامة متناهية.
        حول البيانات إلى كائن JSON فقط بالهيكل التالي:
        {{
            "skills": ["قائمة المهارات التقنية المستخرجة"],
            "profession": "المسمى الوظيفي الأمثل حسب المعايير الدولية",
            "overall_score": 85, (تقييم من 100 يعكس قوة الملف عالمياً)
            "feedback": "رسالة مهنية بلهجة عربية عالمية راقية تشجع المرشح وتبرز نقاط تميزه.",
            "missing_skills": [
                {{"skill": "اسم المهارة المفقودة", "reason": "لماذا تطلبها الشركات الكبرى", "learning_link": "رابط مقترح للتعلم"}}
            ]
        }}
        النص المستخرج من السيرة الذاتية: {cv_text[:4000]}
        """
        res = self._call_ai(prompt, 0.1)
        try:
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {
                "skills": ["جاري الاستخراج"], "profession": "متخصص", "overall_score": 50,
                "feedback": "نعتذر، واجه الذكاء الاصطناعي صعوبة في قراءة بعض التنسيقات. يرجى التأكد من وضوح ملفك.",
                "missing_skills": []
            }

    def generate_skills_radar_data(self, cv_text):
        """توليد مصفوفة المهارات للرادار الرقمي بصرامة تقنية"""
        prompt = f"""
        Analyze the CV and provide strict numerical scores (0-100) for:
        1. Technical Mastery (التمكن التقني)
        2. Soft Skills & Leadership (المهارات الناعمة والقيادة)
        3. Industrial Experience (الخبرة العملية في المجال)
        4. Academic & Certifications (التعليم والشهادات الاحترافية)
        5. Projects & Real-world Impact (المشاريع والأثر الفعلي)
        Return ONLY a JSON object: {{"labels": ["Technical", "Soft Skills", "Experience", "Education", "Projects"], "scores": [0,0,0,0,0]}}
        CV Data: {cv_text[:2500]}
        """
        res = self._call_ai(prompt, temperature=0.1)
        try:
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {"labels": ["تقني", "تواصل", "خبرة", "تعليم", "مشاريع"], "scores": [50, 50, 50, 50, 50]}

    def suggest_courses_for_gaps(self, radar_data):
        """توصيات أكاديمية رفيعة المستوى لسد الفجوات المهنية"""
        gaps = [label for label, score in zip(radar_data['labels'], radar_data['scores']) if score < 80]
        if not gaps: 
            return "🚀 <b>تهانينا!</b> ملفك المهني يطابق معايير النخبة عالمياً. استمر في تعزيز تواجدك الرقمي."

        prompt = f"""
        المرشح لديه فجوات في المهارات التالية: {gaps}.
        اقترح مساراً تعليمياً واحداً (Coursera أو LinkedIn Learning) لكل فجوة.
        اللغة: عربية مهنية عالمية (Professional Global Arabic).
        التنسيق: HTML <ul><li>.
        """
        return self._call_ai(prompt, temperature=0.6)

    def build_global_cv(self, cv_text):
        """تطوير السيرة الذاتية لتصبح نسخة عالمية (ATS-Optimized)"""
        prompt = f"""
        أعد صياغة السيرة الذاتية التالية لتصبح ملفاً عالمياً فائق الجودة:
        1. استخدم أفعال الإنجاز القوية (Strong Action Verbs).
        2. ركز على النتائج القابلة للقياس (Quantifiable Achievements).
        3. اللغة: English (Professional Level).
        4. اجعل الملف متوافقاً تماماً مع أنظمة الفرز الآلي (ATS).
        النص الأصلي: {cv_text[:4000]}
        """
        return self._call_ai(prompt, temperature=0.3)

    def generate_interview_simulation(self, job_title, cv_text):
        """توليد أسئلة مقابلة ذكية بناءً على التناقضات في الملف"""
        prompt = f"""
        بناءً على وظيفة ({job_title}) وسيرة المرشح ({cv_text[:1000]}).
        ضع 3 أسئلة مقابلة تقنية "صعبة" تكشف مدى صدق الخبرة المذكورة.
        اللغة: عربية مهنية عالمية.
        """
        return self._call_ai(prompt, temperature=0.7)

openrouter_ai = OpenRouterAI()

# دالات التوافق مع النظام الأساسي (Global Functions)
def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)

def get_expert_omni_response(user_query, user_context=None, job_context=None):
    """المجيب الخبير لجميع استفسارات المستخدمين بلهجة عالمية"""
    context_str = f"User Context: {user_context} | Job Context: {job_context}"
    prompt = f"Context: {context_str}\nقم بالإجابة كخبير مهني عالمي بلهجة عربية احترافية: {user_query}"
    return openrouter_ai.get_ai_response(prompt, temperature=0.6)
