# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time, random
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        # استجلاب المفتاح من متغيرات البيئة
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # --- ترسانة المحركات المحدثة 2026 (التركيز على الدقة والسرعة) ---
        self.free_models = [
            "google/gemini-2.0-flash-exp:free",
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "google/gemini-flash-1.5-8b:free",
            "mistralai/mistral-7b-instruct:free"
        ]

        self.mid_models = [
            "openai/gpt-4o-mini",
            "anthropic/claude-3-5-haiku",
            "google/gemini-flash-1.5",
            "deepseek/deepseek-chat"
        ]

        self.elite_models = [
            "openai/gpt-4o",
            "anthropic/claude-3-5-sonnet",
            "google/gemini-1.5-pro"
        ]

        # الدمج الهرمي (الفري أولاً ثم المدفوع كخطة بديلة)
        self.ordered_models = self.free_models + self.mid_models + self.elite_models

    def _call_ai(self, prompt, temperature=0.0):
        """المحرك الداخلي: تم ضبط الحرارة الافتراضية عند 0.0 لضمان الصرامة"""
        if not self.api_key:
            return "❌ خطأ: مفتاح API مفقود."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni Professional AI Engine"
        }

        for model in self.ordered_models:
            try:
                print(f"🤖 جاري التحليل الصارم عبر: {model}...")
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 2500,
                    "top_p": 0.9
                }

                # مهلة زمنية ذكية: أطول للموديلات الضخمة
                timeout_val = 20 if ":free" in model else 40
                res = requests.post(self.url, headers=headers, json=payload, timeout=timeout_val)

                if res.status_code == 200:
                    data = res.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        if content and len(content.strip()) > 5:
                            return content
                continue
            except Exception as e:
                print(f"🔄 تبديل المحرك بسبب: {str(e)}")
                continue
        
        return "النظام يواجه ضغطاً. يرجى المحاولة لاحقاً."

    def get_ai_response(self, prompt, temperature=0.0):
        return self._call_ai(prompt, temperature)

    def analyze_cv_complete(self, cv_text, is_academic=False):
        """تحليل السيرة الذاتية: "نظام الجلاد" لفلترة الحقيقة"""
        role = "Global Admission Auditor" if is_academic else "Strict Technical Recruiter"
        
        prompt = f"""
        Act as a {role}. Be extremely critical and cynical.
        Analyze this CV text and identify hard facts only.
        
        [STRICT INSTRUCTIONS]:
        1. If no GPA is mentioned, assume it's low or missing.
        2. If skills are generic (e.g., 'Teamwork', 'Communication'), ignore them unless proven by projects.
        3. Score (0-100) must be HARSH. 80+ is only for elite world-class candidates.
        
        CV TEXT:
        {cv_text[:4000]}

        RETURN ONLY VALID JSON:
        {{
            "skills": ["hard skills only"],
            "profession": "most accurate title",
            "overall_score": 0-100,
            "feedback": "brutally honest 1-sentence critique",
            "missing_skills": ["critical tools/certs they lack"],
            "academic_level": "BSc/MSc/PhD/None",
            "gpa_status": "High/Mid/Low/Unknown"
        }}
        """
        res = self._call_ai(prompt, 0.0)
        try:
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {"skills": [], "profession": "متخصص", "overall_score": 40, "feedback": "بيانات غير مكتملة أو نص غير مفهوم"}

    def generate_skills_radar_data(self, cv_text):
        """توليد بيانات الرادار الرقمي بمعايير 2026"""
        prompt = f"""
        Provide strictly numerical scores (0-100) based on CV evidence.
        Categories: Technical, Soft Skills, Experience, Education, Projects.
        JSON ONLY: {{"labels": ["Technical", "Soft Skills", "Experience", "Education", "Projects"], "scores": [0,0,0,0,0]}}
        CV: {cv_text[:2500]}
        """
        res = self._call_ai(prompt, 0.0)
        try:
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {"labels": ["تقني", "تواصل", "خبرة", "تعليم", "مشاريع"], "scores": [30, 30, 30, 30, 30]}

    def build_global_cv(self, cv_text, mode='job'):
        """إعادة بناء السيرة الذاتية بمعايير عالمية (ATS أو أكاديمية)"""
        instruction = (
            "Optimize for top-tier Global Scholarships (Focus on Research, Publications, and Academic Excellence)"
            if mode == 'scholarship' else
            "Optimize for Fortune 500 ATS systems (Focus on Keywords, Measurable Impact, and Action Verbs)"
        )
        prompt = f"{instruction}. Rewrite the following CV text professionally while maintaining 100% honesty: {cv_text[:4000]}"
        return self._call_ai(prompt, temperature=0.2)

    def find_scholarships_strictly(self, query, context_text):
        """البحث عن المنح: منطق الفرز الصارم للمستحقين فقط"""
        prompt = f"""
        Act as a Global Scholarship Hunter. Find 2026 opportunities for: {query}
        Candidate Context: {context_text[:1500]}
        Return JSON Array of objects with: title, university, country, link, and match_score (0-100).
        """
        res = self._call_ai(prompt, 0.1)
        try:
            clean = re.search(r'\[.*\]', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return []

# تصدير نسخة موحدة للاستخدام في كل التطبيق
openrouter_ai = OpenRouterAI()

def get_ai_response(prompt, temperature=0.0):
    return openrouter_ai.get_ai_response(prompt, temperature)

def get_expert_omni_response(user_query, user_context=None, job_context=None):
    """رد الخبير: مخصص للهجة السودانية والاحترافية العالمية"""
    context = f"Context: {user_context} | {job_context}"
    prompt = f"{context}\nAnswer the following query as a high-level career consultant in Sudan: {user_query}"
    return openrouter_ai.get_ai_response(prompt, temperature=0.3)
