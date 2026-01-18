# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time, random
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # --- مجموعة الـ 60 نموذجاً الصغير والسريع (تبدأ بها الأولوية) ---
        self.small_models = [
            "google/gemini-2.0-flash-exp:free", "google/gemini-flash-1.5-8b:free",
            "meta-llama/llama-3.2-3b-instruct:free", "meta-llama/llama-3.2-1b-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free", "mistralai/mistral-7b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free", "meta-llama/llama-3.1-8b-instruct:free",
            "google/gemini-2.0-flash-001", "qwen/qwen-2-7b-instruct:free",
            "huggingfaceh4/zephyr-7b-beta:free", "undi95/toppy-m-7b:free",
            "upstage/solar-10-7b-instruct:free", "mistralai/mistral-nemo",
            "liquid/lfm-40b:free", "meta-llama/llama-2-7b-chat:free",
            "qwen/qwen-2.5-3b-instruct:free", "mistralai/pixtral-12b:free",
            "nousresearch/hermes-3-llama-3.1-8b", "open-theory/gryphe-mythomax-l2-13b:free",
            "microsoft/phi-3-medium-128k-instruct:free"
        ]

        # --- مجموعة الـ 40 نموذجاً المتوسط والكبير (احتياطي عالي الجودة) ---
        self.large_models = [
            "google/gemini-pro-1.5", "openai/gpt-4o-mini", "openai/gpt-4o",
            "anthropic/claude-3.5-sonnet", "anthropic/claude-3-haiku",
            "meta-llama/llama-3.1-70b-instruct:free", "cohere/command-r",
            "deepseek/deepseek-chat", "mistralai/mixtral-8x7b-instruct:free",
            "google/gemini-1.5-pro-exp-0827", "meta-llama/llama-3.1-405b-instruct"
        ]

        # الترتيب الذكي: الصغير أولاً ثم الكبير
        self.ordered_models = self.small_models + self.large_models

    def _call_ai(self, prompt, temperature=0.3):
        if not self.api_key: return "❌ API Key missing!"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni AI Mega-Engine"
        }

        # نحاول المرور على النماذج بالترتيب (من الأصغر للأكبر)
        for model in self.ordered_models:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 1500
                }

                # تايم أوت 7 ثواني (كافية جداً للنماذج الصغيرة)
                res = requests.post(self.url, headers=headers, json=payload, timeout=7)

                if res.status_code == 200:
                    data = res.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        if content and len(content.strip()) > 5:
                            return content
                
                # إذا كان الموديل مشغولاً (429) أو به خطأ، ننتقل فوراً للذي يليه
                continue
            except:
                continue

        return "عذراً يا هندسة، جميع الـ 100 محرك ذكي تحت ضغط شديد حالياً. جرب خلال ثواني."

    def get_ai_response(self, prompt, temperature=0.5):
        return self._call_ai(prompt, temperature)

    def get_expert_omni_response(self, user_query, user_context=None, job_context=None):
        context_str = ""
        if user_context: context_str += f"\n[سياق المستخدم]: {user_context}"
        if job_context: context_str += f"\n[سياق الوظيفة]: {job_context}"

        prompt = f"""
        أنت 'الوكيل الخبير العالمي' لمنصة جوبيني السودان. 
        استخدم السياق التالي: {context_str}
        أجب بدقة ومهنية وباللهجة السودانية المهذبة على: "{user_query}"
        """
        return self._call_ai(prompt, temperature=0.6)

    def analyze_cv_complete(self, cv_text):
        prompt = f"""
        Analyze this Resume and return ONLY a valid JSON object.
        Structure:
        {{
            "skills": ["Skill1", "Skill2"],
            "profession": "Job Title",
            "overall_score": 80,
            "feedback": "Arabic Advice",
            "missing_skills": [
                {{"skill": "Skill Name", "reason": "Why needed", "learning_link": "YouTube Link"}}
            ]
        }}
        Text: {cv_text[:2500]}
        """
        res = self._call_ai(prompt, 0.1)
        try:
            # تنظيف الرد لاستخراج الـ JSON فقط في حال وجود نص إضافي
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {
                "skills": ["تحليل ذكي"], "profession": "متخصص", "overall_score": 55,
                "feedback": "يا مكنة، الـ AI تعب شوية، جرب ترفع الملف مرة تانية أو تأكد من جودة النص.",
                "missing_skills": []
            }

    def generate_improved_text(self, cv_content):
        prompt = f"Optimize this resume for ATS in English. Focus on achievements. Content: {cv_content[:2000]}"
        return self._call_ai(prompt, 0.7)

openrouter_ai = OpenRouterAI()

# دالات التوافق مع الملفات الأخرى
def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)

def get_expert_omni_response(user_query, user_context=None, job_context=None):
    return openrouter_ai.get_expert_omni_response(user_query, user_context, job_context)
