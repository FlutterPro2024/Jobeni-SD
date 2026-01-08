# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # قائمة الـ 30 نموذجاً (تركيز مكثف على النماذج الصغيرة والسريعة لضمان الاستجابة)
        self.models = [
            "google/gemini-2.0-flash-001",
            "google/gemini-2.0-flash-exp:free",
            "google/gemini-flash-1.5-8b",
            "google/gemini-flash-1.5-8b-exp",
            "meta-llama/llama-3.2-1b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "meta-llama/llama-3-8b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "mistralai/pixtral-12b:free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "microsoft/phi-3-medium-128k-instruct:free",
            "qwen/qwen-2.5-72b-instruct",
            "qwen/qwen-2-7b-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free",
            "open-theory/gryphe-mythomax-l2-13b:free",
            "huggingfaceh4/zephyr-7b-beta:free",
            "undi95/toppy-m-7b:free",
            "liquid/lfm-40b:free",
            "nvidia/llama-3.1-nemotron-70b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-8b",
            "anthropic/claude-3-haiku",
            "meta-llama/llama-3.1-70b-instruct:free",
            "01-ai/yi-large",
            "gryphe/mythomax-l2-13b",
            "cognitivecomputations/dolphin-mixtral-8x7b",
            "perplexity/llama-3-sonar-small-32k-chat",
            "meta-llama/llama-3.1-405b-instruct",
            "sophosympathizer/rogue-rose-103b-v0.2:free",
            "alpindale/magnum-72b-v2:free"
        ]

    def _call_ai(self, prompt, temperature=0.3):
        """المحرك الأساسي: يلف على الـ 30 نموذجاً لضمان عدم الفشل"""
        if not self.api_key:
            print("❌ API Key missing!")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni AI Engine"
        }

        # محاولة الاتصال بكل النماذج بالترتيب
        for model in self.models:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 3500
                }
                
                # تقليل المهلة لـ 10 ثواني للتنقل السريع بين النماذج المشغولة
                res = requests.post(self.url.strip(), headers=headers, json=payload, timeout=10)

                if res.status_code == 200:
                    response_json = res.json()
                    if 'choices' in response_json and len(response_json['choices']) > 0:
                        content = response_json['choices'][0]['message']['content']
                        if content and len(content.strip()) > 5:
                            print(f"✅ Success with model: {model}")
                            return content

                print(f"⚠️ Model {model} failed (Status: {res.status_code}), moving to next...")
                continue
            except Exception as e:
                print(f"❌ Error with model {model}: {str(e)}")
                # انتظر نصف ثانية قبل المحاولة التالية لتجنب الـ Rate Limit
                time.sleep(0.5)
                continue

        return "عذراً يا هندسة، جميع المحركات الذكية مشغولة حالياً. جرب بعد دقيقة."

    def get_ai_response(self, prompt, temperature=0.5):
        """دالة عامة لاستقبال الطلبات"""
        return self._call_ai(prompt, temperature=temperature)

    def analyze_cv_complete(self, cv_text):
        """تحليل السيرة الذاتية لاستخراج البيانات المهنية بدقة"""
        prompt = f"""
        Act as a Senior Tech Recruiter. Analyze this CV text.
        Return ONLY a raw JSON object.
        Format: {{"skills": ["Skill1", "Skill2"], "profession": "Job Title", "overall_score": 85, "feedback": "Arabic Advice"}}

        CV Text: {cv_text[:3500]}
        """
        content = self._call_ai(prompt, temperature=0.1)
        if content:
            try:
                # تنظيف النص لاستخراج الـ JSON فقط
                clean = re.search(r'\{.*\}', content.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    return json.loads(clean.group())
            except:
                pass
        return self._smart_internal_analysis(cv_text)

    def _smart_internal_analysis(self, text):
        """نظام الطوارئ الداخلي الفائق"""
        text_lower = text.lower()
        professions_map = {
            "telecommunication": "مهندس اتصالات", "software": "مطور برمجيات",
            "python": "مطور بايثون", "civil": "مهندس مدني", "accountant": "محاسب مالي",
            "doctor": "طبيب", "teacher": "تربوي/معلم", "marketing": "متخصص تسويق",
            "ai": "مهندس ذكاء اصطناعي", "data": "محلل بيانات", "cloud": "مهندس سحابة"
        }
        found_prof = "متخصص تقني"
        for key, val in professions_map.items():
            if key in text_lower:
                found_prof = val
                break

        potential_skills = ["Python", "JavaScript", "Cloud", "AI", "React", "SQL", "Docker", "Git"]
        extracted_skills = [s for s in potential_skills if s.lower() in text_lower]
        if not extracted_skills: extracted_skills = ["تحليل بيانات", "مهارات تقنية"]

        return {
            "skills": extracted_skills[:6],
            "profession": found_prof,
            "overall_score": 60,
            "feedback": "تم التحليل بنظام الجدولة الداخلي لضمان السرعة."
        }

    def get_match_score(self, cv_text, job_desc):
        """مطابقة ATS ذكية للمقابلات والوظائف"""
        prompt = f"""
        Compare CV with Job Description.
        Return ONLY JSON: {{"score": 85, "reason": "Arabic Reason"}}
        Job: {job_desc[:1500]} | CV: {cv_text[:2500]}
        """
        res = self._call_ai(prompt, temperature=0.1)
        if res:
            try:
                clean = re.search(r'\{.*\}', res.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    data = json.loads(clean.group())
                    return int(data.get('score', 0)), data.get('reason', 'تمت المطابقة الذكية.')
            except:
                pass
        return 50, "تحليل مطابقة تقريبي."

    def generate_improved_text(self, cv_content):
        """محسن السي في الاحترافي (Re-writer)"""
        full_prompt = f"""
        Role: Expert ATS Resume Re-writer.
        Task: Rewrite the following CV into a professional, keyword-optimized English resume using Markdown.
        Ensure it includes: Professional Summary, Core Skills, and detailed Work Experience.
        Language of output: English (Main content) with professional Arabic tips at the end.
        
        CV Content:
        {cv_content}
        """
        return self._call_ai(full_prompt, temperature=0.7)

# تصدير الكائن للاستخدام
openrouter_ai = OpenRouterAI()

def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)
