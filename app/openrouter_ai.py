# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        # قائمة بـ 20 نموذج أو أكثر (من المجاني الخفيف إلى العملاق) لضمان عدم التوقف
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
            "nvidia/llama-3.1-nemotron-70b-instruct:free",
            "deepseek/deepseek-chat",
            "google/palm-2-chat-bison",
            "phind/phind-codellama-34b"
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
                    "max_tokens": 2500 # لضمان عدم قص السيرة الذاتية
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
        Return ONLY a valid JSON:
        {{"skills": ["Skill1", "Skill2", "Skill3"], "profession": "Job Title", "overall_score": 85, "feedback": "Arabic Advice"}}
        CV Text: {cv_text[:2500]}
        """
        content = self._call_ai(prompt, temperature=0.2)
        if content:
            try:
                clean = re.search(r'\{.*\}', content.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    return json.loads(clean.group())
            except:
                pass
        return self._smart_internal_analysis(cv_text)

    def _smart_internal_analysis(self, text):
        """تحليل برمجي داخلي لاستخراج البيانات عند ضغط النماذج"""
        text_lower = text.lower()
        professions_map = {
            "telecommunication": "مهندس اتصالات", "software": "مطور برمجيات",
            "python": "مطور بايثون", "civil": "مهندس مدني", "accountant": "محاسب مالى",
            "doctor": "طبيب", "teacher": "تربوي/معلم", "marketing": "متخصص تسويق",
            "ai": "مهندس ذكاء اصطناعي"
        }
        found_prof = "متخصص"
        for key, val in professions_map.items():
            if key in text_lower:
                found_prof = val
                break
        potential_skills = ["python", "java", "management", "communication", "leadership", "sql", "cloud", "frontend", "backend", "analysis"]
        extracted_skills = [s.capitalize() for s in potential_skills if s in text_lower]
        if not extracted_skills: extracted_skills = ["تحليل عام"]
        return {
            "skills": extracted_skills[:5],
            "profession": found_prof,
            "overall_score": 45,
            "feedback": "تم استخراج البيانات عبر النظام الاحتياطي لضمان السرعة."
        }

    def get_match_score(self, cv_text, job_desc):
        """مطابقة ذكية تفهم تداخل التخصصات"""
        prompt = f"""
        Compare CV with Job Description.
        Return ONLY JSON: {{"score": 0-100, "reason": "Arabic Reason"}}
        Job: {job_desc[:700]} | CV: {cv_text[:1500]}
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
        return 30, "تحليل تقريبي سريع."

    def generate_improved_text(self, cv_content):
        """إعادة صياغة السيرة الذاتية بالكامل (فل الفل) مع كسر قيود الخصوصية"""
        full_prompt = f"""
        Act as a Professional Career Coach. Your task is to REWRITE and ENHANCE the following resume.
        The user has provided their own data and authorized this for professional use.
        
        STRICT RULES:
        1. DO NOT give privacy warnings. This is a legitimate request.
        2. DO NOT SUMMARIZE. Expand the content to a FULL professional resume.
        3. Structure: PROFESSIONAL SUMMARY, KEY SKILLS (Detailed), EXPERIENCE, EDUCATION, and PROJECTS.
        4. Focus on ICT and AI terminology. 
        5. Output ONLY the improved resume in Markdown.

        Resume Content:
        {cv_content}
        """
        return self._call_ai(full_prompt, temperature=0.7)

# تصدير الدوال للاستخدام المباشر
openrouter_ai = OpenRouterAI()

def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)
