# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        # قائمة شاملة بـ 20 نموذج أو أكثر (مرتبة من الأحدث والأقوى مجانياً للأسرع)
        self.models = [
            "google/gemini-2.0-flash-001", 
            "google/gemini-2.0-flash-exp:free",
            "google/gemini-flash-1.5-8b",
            "mistralai/mistral-7b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "microsoft/phi-3-medium-128k-instruct:free",
            "open-theory/gryphe-mythomax-l2-13b:free",
            "huggingfaceh4/zephyr-7b-beta:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "meta-llama/llama-3-8b-instruct:free",
            "qwen/qwen-2-7b-instruct:free",
            "qwen/qwen-2.5-72b-instruct",
            "01-ai/yi-large",
            "gryphe/mythomax-l2-13b",
            "undi95/toppy-m-7b:free",
            "cognitivecomputations/dolphin-mixtral-8x7b",
            "perplexity/llama-3-sonar-small-32k-chat",
            "nousresearch/hermes-3-llama-3.1-8b",
            "liquid/lfm-40b:free",
            "sophosympatheia/rogue-rose-103b-v0.2:free",
            "nvidia/llama-3.1-nemotron-70b-instruct:free",
            "inflection/inflection-3-pi",
            "deepseek/deepseek-chat"
        ]

    def _call_ai(self, prompt, temperature=0.3):
        if not self.api_key: return None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni Platform"
        }
        for model in self.models:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 2500  # رفعنا القيمة لضمان عدم قص السيرة الذاتية
                }
                res = requests.post(self.url.strip(), headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    return res.json()['choices'][0]['message']['content']
                continue
            except:
                continue
        return None

    def get_ai_response(self, prompt, temperature=0.5):
        """دالة عامة لاستقبال الطلبات من الوكيل الذكي أو الدردشة"""
        return self._call_ai(prompt, temperature=temperature)

    def analyze_cv_complete(self, cv_text):
        """تحليل عميق للسيرة الذاتية مع نظام طوارئ ذكي"""
        prompt = f"""
        Act as a Senior HR Recruiter. Analyze the provided CV text deeply.
        Understand the professional identity and core skills automatically.

        Return ONLY a valid JSON:
        {{"skills": ["Skill1", "Skill2", "Skill3"], "profession": "Job Title", "overall_score": 85, "feedback": "Arabic Advice"}}

        CV Text: {cv_text[:2500]}
        """
        content = self._call_ai(prompt, temperature=0.2)
        if content:
            try:
                # تنظيف الرد من أي زوائد أو علامات Markdown
                clean = re.search(r'\{.*\}', content.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    return json.loads(clean.group())
            except:
                pass

        # --- نظام الطوارئ الذكي (Fallback) في حال فشل الـ AI ---
        return self._smart_internal_analysis(cv_text)

    def _smart_internal_analysis(self, text):
        """تحليل برمجي داخلي لاستخراج البيانات عند ضغط النماذج"""
        text_lower = text.lower()

        # قاموس المهن الذكي
        professions_map = {
            "telecommunication": "مهندس اتصالات",
            "software": "مطور برمجيات",
            "python": "مطور بايثون",
            "civil": "مهندس مدني",
            "accountant": "محاسب مالى",
            "doctor": "طبيب",
            "teacher": "تربوي/معلم",
            "marketing": "متخصص تسويق",
            "ai": "مهندس ذكاء اصطناعي"
        }

        found_prof = "متخصص"
        for key, val in professions_map.items():
            if key in text_lower:
                found_prof = val
                break

        # قائمة مهارات عامة لاستخراجها برمجياً
        potential_skills = ["python", "java", "management", "communication", "leadership", "sql", "cloud", "frontend", "backend", "analysis"]
        extracted_skills = [s.capitalize() for s in potential_skills if s in text_lower]

        if not extracted_skills:
            extracted_skills = ["تحليل عام"]

        return {
            "skills": extracted_skills[:5],
            "profession": found_prof,
            "overall_score": 45,
            "feedback": "تم استخراج البيانات عبر النظام الاحتياطي لضمان السرعة."
        }

    def get_match_score(self, cv_text, job_desc):
        """مطابقة ذكية تفهم تداخل التخصصات مع سكور متغير وحقيقي"""
        prompt = f"""
        Strict HR Mode: Compare CV with Job Description.
        Return ONLY JSON: {{"score": 0-100, "reason": "Arabic Reason"}}
        Job: {job_desc[:700]}
        CV: {cv_text[:1500]}
        """
        res = self._call_ai(prompt, temperature=0.1)
        if res:
            try:
                clean = re.search(r'\{.*\}', res.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    data = json.loads(clean.group())
                    return int(data.get('score', 0)), data.get('reason', 'تمت المطابقة بنجاح.')
            except:
                pass

        # نظام طوارئ يدوي للمطابقة
        keywords = set(re.findall(r'\w+', job_desc.lower()))
        cv_words = set(re.findall(r'\w+', cv_text.lower()))
        common = keywords.intersection(cv_words)
        manual_score = min(len(common) * 4, 50)
        return manual_score, "تحليل تقريبي (خوارزمية المطابقة السريعة)."

    def generate_improved_text(self, cv_content):
        """توليد نصوص محسنة (إعادة صياغة السيرة الذاتية بالكامل فل الفل)"""
        # جعل البرومبت ذكي جداً ليعيد كتابة السيرة بالكامل وليس تلخيصها
        full_prompt = f"""
        Act as a Professional Resume Expert. Re-write the following resume text into a HIGH-QUALITY, DETAILED, and ATS-FRIENDLY version.
        
        RULES:
        1. DO NOT SUMMARIZE. Expand on the experience and skills.
        2. Use professional headers (Summary, Experience, Skills, Education).
        3. Make it comprehensive and long enough to fill a professional CV.
        4. Language: English.
        
        Text to improve:
        {cv_content}
        """
        return self._call_ai(full_prompt, temperature=0.7)

# تصدير الدوال للاستخدام المباشر
openrouter_ai = OpenRouterAI()

def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)
