# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        # حصر القائمة في الموديلات المجانية لضمان العمل بدون رصيد
        self.models = [
            "mistralai/mistral-7b-instruct:free",
            "google/gemini-2.0-flash-001",
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
                res = requests.post(self.url.strip(), headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    print(f"✅ Success with FREE model: {model}")
                    return res.json()['choices'][0]['message']['content']
                print(f"⚠️ Model {model} returned status {res.status_code}")
                continue
            except: continue
        return None

    def analyze_cv_complete(self, cv_text):
        """تحليل شامل لجميع المجالات"""
        prompt = f'Analyze Resume. Return ONLY JSON. Fields: "skills", "profession", "overall_score", "feedback". Text: {cv_text[:2000]}'
        content = self._call_ai(prompt, temperature=0.1)
        if content:
            try:
                clean = re.search(r'\{.*\}', content.replace("```json", "").replace("```", ""), re.DOTALL)
                if clean: return json.loads(clean.group())
            except: pass
        
        lines = [l.strip() for l in cv_text.split('\n') if len(l.strip()) > 3]
        return {
            "skills": ["تحليل تقني", "مهارات أساسية"],
            "profession": lines[1] if len(lines) > 1 else "متخصص",
            "overall_score": 50,
            "feedback": "الخدمة المجانية محدودة، يرجى مراجعة التنسيق يدوياً."
        }

    def get_match_score(self, cv_text, job_desc):
        # تم إصلاح التداخل هنا باستخدام علامات أحادية وإلغاء أقواس الـ JSON المزدوجة
        prompt = f"Compare Resume and Job. Return ONLY JSON: {{'score': 0-100, 'reason': 'Arabic explanation'}}\nJob: {job_desc[:500]}\nCV: {cv_text[:1000]}"
        res = self._call_ai(prompt, temperature=0.1)
        try:
            clean = re.search(r'\{.*\}', res.replace("```json", "").replace("```", ""), re.DOTALL)
            data = json.loads(clean.group())
            return int(data.get('score', 0)), data.get('reason', 'تم التقييم.')
        except: return 0, "فشل الاتصال بالمحرك المجاني."

    def generate_improved_text(self, prompt):
        return self._call_ai(prompt, temperature=0.7)

openrouter_ai = OpenRouterAI()
