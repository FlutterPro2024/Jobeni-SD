# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time, random
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        # استجلاب المفتاح من متغيرات البيئة
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # --- ترسانة المحركات المحدثة 2026 (لضمان الـ Uptime) ---
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

        # الدمج الهرمي لضمان استمرارية الخدمة
        self.ordered_models = self.free_models + self.mid_models + self.elite_models

    def _call_ai(self, prompt, temperature=0.3):
        if not self.api_key:
            return "❌ خطأ: مفتاح API (OPENROUTER_API_KEY) غير موجود."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni Professional AI Engine"
        }

        # محاولة ذكية للمرور عبر المحركات (Failover Logic)
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

    # --- محرك البحث عن المنح الدراسية (Scholarship AI Agent) ---
    def find_scholarships(self, query, context_text):
        """رادار المنح الدراسية المبرمج لجلب أفضل الفرص العالمية 2026"""
        prompt = f"""
        أنت "Scholarship AI Agent" مبرمج لجلب أفضل المنح الدراسية عالمياً.
        المهام:
        1. ابحث عن منح تناسب: {query}
        2. حلل مطابقتها لخلفية المستخدم الأكاديمية: {context_text[:1500]}
        3. التنسيق: JSON Array فقط.
        """
        res = self._call_ai(prompt, temperature=0.2)
        try:
            clean = re.search(r'\[.*\]', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return []

    def analyze_cv_complete(self, cv_text, is_academic=False):
        """تحليل سيرة ذاتية صارم بمعايير التوظيف العالمية أو المنح"""
        role_type = "Admission Officer" if is_academic else "HR Manager"
        prompt = f"""
        Act as a {role_type}. Analyze this text and return ONLY JSON.
        {{
            "skills": [], "profession": "", "overall_score": 0, "feedback": "", "missing_skills": []
        }}
        Text: {cv_text[:4000]}
        """
        res = self._call_ai(prompt, 0.1)
        try:
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {"skills": [], "profession": "متخصص", "overall_score": 50, "feedback": "خطأ في التحليل", "missing_skills": []}

    def generate_skills_radar_data(self, cv_text):
        """توليد مصفوفة المهارات للرادار الرقمي"""
        prompt = f"""
        Analyze CV and provide numerical scores (0-100) for 5 categories.
        Return ONLY JSON: {{"labels": ["Technical", "Soft Skills", "Experience", "Education", "Projects"], "scores": [0,0,0,0,0]}}
        CV: {cv_text[:2500]}
        """
        res = self._call_ai(prompt, temperature=0.1)
        try:
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {"labels": ["تقني", "تواصل", "خبرة", "تعليم", "مشاريع"], "scores": [50, 50, 50, 50, 50]}

    def suggest_courses_for_gaps(self, radar_data):
        """توصيات أكاديمية لسد الفجوات المهنية"""
        gaps = [label for label, score in zip(radar_data['labels'], radar_data['scores']) if score < 80]
        if not gaps: return "🚀 ملفك المهني مثالي!"
        prompt = f"اقترح مسارات تعليمية لسد فجوات: {gaps}. التنسيق: HTML <ul>."
        return self._call_ai(prompt, temperature=0.6)

    def build_global_cv(self, cv_text, mode='job'):
        """تطوير السيرة الذاتية (ATS or Academic Optimized)"""
        if mode == 'scholarship':
            prompt = f"Rewrite this CV as a world-class ACADEMIC CV for scholarship applications. Focus on research and GPA: {cv_text[:4000]}"
        else:
            prompt = f"Rewrite this CV to be world-class and ATS-optimized: {cv_text[:4000]}"
        return self._call_ai(prompt, temperature=0.3)

    def generate_interview_simulation(self, job_title, cv_text):
        """توليد أسئلة مقابلة ذكية"""
        prompt = f"Generate 3 tough interview questions for {job_title} based on CV: {cv_text[:1000]}"
        return self._call_ai(prompt, temperature=0.7)

# تصدير نسخة موحدة
openrouter_ai = OpenRouterAI()

# دالات التوافق
def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)

def get_expert_omni_response(user_query, user_context=None, job_context=None):
    context_str = f"User Context: {user_context} | Job Context: {job_context}"
    prompt = f"Context: {context_str}\nأجب كخبير مهني أو أكاديمي بلهجة عربية احترافية: {user_query}"
    return openrouter_ai.get_ai_response(prompt, temperature=0.6)
