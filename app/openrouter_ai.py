# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        
        # قائمة الـ 23 نموذج المحدثة لعام 2026 (مرتبة من الأذكى للأسرع)
        self.models = [
            "google/gemini-2.0-flash-001", 
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.1-405b-instruct",
            "meta-llama/llama-3.1-70b-instruct:free",
            "google/gemini-flash-1.5-8b",
            "qwen/qwen-2.5-72b-instruct",
            "anthropic/claude-3-haiku",
            "mistralai/mistral-7b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "microsoft/phi-3-medium-128k-instruct:free",
            "open-theory/gryphe-mythomax-l2-13b:free",
            "huggingfaceh4/zephyr-7b-beta:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "meta-llama/llama-3-8b-instruct:free",
            "qwen/qwen-2-7b-instruct:free",
            "01-ai/yi-large",
            "gryphe/mythomax-l2-13b",
            "undi95/toppy-m-7b:free",
            "cognitivecomputations/dolphin-mixtral-8x7b",
            "perplexity/llama-3-sonar-small-32k-chat",
            "nousresearch/hermes-3-llama-3.1-8b",
            "liquid/lfm-40b:free",
            "nvidia/llama-3.1-nemotron-70b-instruct:free"
        ]

    def _call_ai(self, prompt, temperature=0.3):
        """المحرك الأساسي: يجرب الـ 23 نموذجاً تلقائياً في حال الفشل"""
        if not self.api_key:
            print("❌ API Key missing!")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni AI Engine"
        }

        for model in self.models:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 3000
                }
                # تقليل الـ timeout لسرعة التنقل بين النماذج في حال التعليق
                res = requests.post(self.url.strip(), headers=headers, json=payload, timeout=15)
                
                if res.status_code == 200:
                    response_json = res.json()
                    if 'choices' in response_json and len(response_json['choices']) > 0:
                        content = response_json['choices'][0]['message']['content']
                        if content: return content
                
                print(f"⚠️ Model {model} failed (Status: {res.status_code}), trying next...")
                continue
            except Exception as e:
                print(f"❌ Error with model {model}: {str(e)}")
                continue
        
        return "عذراً يا هندسة، جميع المحركات الذكية مشغولة حالياً. جرب بعد دقيقة."

    def get_ai_response(self, prompt, temperature=0.5):
        """دالة عامة لاستقبال الطلبات"""
        return self._call_ai(prompt, temperature=temperature)

    def analyze_cv_complete(self, cv_text):
        """تحليل السيرة الذاتية لاستخراج البيانات المهنية بدقة"""
        prompt = f"""
        Act as a Senior Tech Recruiter. Analyze this CV text.
        Return ONLY a raw JSON object (no markdown, no explanations).
        Format: {{"skills": ["Skill1", "Skill2"], "profession": "Job Title", "overall_score": 85, "feedback": "Arabic Advice"}}
        
        CV Text: {cv_text[:3000]}
        """
        content = self._call_ai(prompt, temperature=0.2)
        if content:
            try:
                # تنظيف الرد لاستخراج الـ JSON فقط ومنع أخطاء التنسيق
                clean = re.search(r'\{.*\}', content.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    return json.loads(clean.group())
            except:
                pass
        return self._smart_internal_analysis(cv_text)

    def _smart_internal_analysis(self, text):
        """نظام الطوارئ (Fallback) في حال فشل كل النماذج"""
        text_lower = text.lower()
        professions_map = {
            "telecommunication": "مهندس اتصالات", "software": "مطور برمجيات",
            "python": "مطور بايثون", "civil": "مهندس مدني", "accountant": "محاسب مالي",
            "doctor": "طبيب", "teacher": "تربوي/معلم", "marketing": "متخصص تسويق",
            "ai": "مهندس ذكاء اصطناعي", "data": "محلل بيانات"
        }
        found_prof = "متخصص تقني"
        for key, val in professions_map.items():
            if key in text_lower:
                found_prof = val
                break
        
        potential_skills = ["Python", "JavaScript", "Management", "Cloud", "AI", "React", "SQL"]
        extracted_skills = [s for s in potential_skills if s.lower() in text_lower]
        if not extracted_skills: extracted_skills = ["مهارات تقنية"]

        return {
            "skills": extracted_skills[:5],
            "profession": found_prof,
            "overall_score": 50,
            "feedback": "تم التحليل بنظام الحماية الداخلي نظراً لضغط السيرفرات."
        }

    def get_match_score(self, cv_text, job_desc):
        """مطابقة ATS ذكية"""
        prompt = f"""
        Compare CV with Job Description. 
        Return ONLY JSON: {{"score": 85, "reason": "Arabic Reason"}}
        Job: {job_desc[:1000]} | CV: {cv_text[:2000]}
        """
        res = self._call_ai(prompt, temperature=0.1)
        if res:
            try:
                clean = re.search(r'\{.*\}', res.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    data = json.loads(clean.group())
                    return int(data.get('score', 0)), data.get('reason', 'تمت المطابقة.')
            except:
                pass
        return 40, "تحليل تقريبي."

    def generate_improved_text(self, cv_content):
        """محسن السي في الاحترافي"""
        full_prompt = f"""
        Role: Professional Resume Writer. 
        Task: Rewrite this CV into a high-impact, keyword-rich professional resume (Markdown format).
        Language: Arabic/English (Professional Mix).
        Content: {cv_content}
        """
        return self._call_ai(full_prompt, temperature=0.7)

# تصدير الكائن للاستخدام في ملفات المشروع
openrouter_ai = OpenRouterAI()

def get_ai_response(prompt, temperature=0.5):
    """وظيفة المساعدة السريعة للملفات الأخرى"""
    return openrouter_ai.get_ai_response(prompt, temperature)
