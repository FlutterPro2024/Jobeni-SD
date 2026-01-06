# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.models = [
            "google/gemini-2.0-flash-001",
            "mistralai/mistral-7b-instruct:free",
            "open-theory/gryphe-mythomax-l2-13b:free",
            "huggingfaceh4/zephyr-7b-beta:free",
            "microsoft/phi-3-mini-128k-instruct:free"
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
                    "temperature": temperature
                }
                res = requests.post(self.url.strip(), headers=headers, json=payload, timeout=25)
                if res.status_code == 200:
                    return res.json()['choices'][0]['message']['content']
                continue
            except: continue
        return None

    # --- الدالة الجديدة للربط مع الوكيل الذكي والدردشة ---
    def get_ai_response(self, prompt, temperature=0.5):
        """دالة عامة لاستقبال الطلبات من الوكيل الذكي أو الدردشة"""
        return self._call_ai(prompt, temperature=temperature)

    def analyze_cv_complete(self, cv_text):
        """تحليل عميق للسيرة الذاتية لجميع التخصصات"""
        prompt = f"""
        As a Senior HR Specialist, analyze this CV text.
        Extract skills, identify the exact profession, and give a general profile score.
        Return ONLY valid JSON format like this:
        {{"skills": ["skill1", "skill2"], "profession": "Job Title", "overall_score": 85, "feedback": "Arabic Text"}}
        CV Text: {cv_text[:2000]}
        """
        content = self._call_ai(prompt, temperature=0.2)
        if content:
            try:
                # تنظيف الرد من أي زيادات قبل وبعد الـ JSON
                clean = re.search(r'\{.*\}', content.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    return json.loads(clean.group())
            except: pass

        return {
            "skills": ["تحليل عام"],
            "profession": "متخصص",
            "overall_score": 50,
            "feedback": "فشل التحليل الذكي، تم استخدام الوضع الافتراضي."
        }

    def get_match_score(self, cv_text, job_desc):
        """مطابقة ذكية تفهم تداخل التخصصات (مثل Telecom و IT)"""
        prompt = f"""
        Act as an Expert Recruiter. Compare the Candidate CV with the Job Description.
        Consider transferable skills and related fields.
        Return ONLY a JSON object:
        {{"score": 85, "reason": "Arabic explanation of why this score was given"}}

        Job: {job_desc[:700]}
        CV: {cv_text[:1500]}
        """
        res = self._call_ai(prompt, temperature=0.1)
        if res:
            try:
                clean = re.search(r'\{.*\}', res.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean:
                    data = json.loads(clean.group())
                    score = int(data.get('score', 0))
                    return score, data.get('reason', 'تمت المطابقة بنجاح.')
            except Exception as e:
                print(f"JSON Parsing Error: {e}")

        # نظام الطوارئ: لو الـ AI فشل، نبحث عن كلمات مفتاحية يدوياً عشان ما ندي صفر
        keywords = set(job_desc.lower().split())
        cv_words = set(cv_text.lower().split())
        common = keywords.intersection(cv_words)
        manual_score = min(len(common) * 5, 40) # حد أقصى 40% لو التحليل اليدوي

        return manual_score, "تحليل تقريبي (المحرك الذكي مشغول حالياً)."

    def generate_improved_text(self, prompt):
        return self._call_ai(prompt, temperature=0.7)

# تصدير الدوال للاستخدام المباشر في الملفات الأخرى
openrouter_ai = OpenRouterAI()

def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)
