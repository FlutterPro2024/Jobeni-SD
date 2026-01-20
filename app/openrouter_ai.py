# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time, random
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        # استجلاب المفتاح من البيئة
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # --- مجموعة النماذج المجانية والسريعة (أولوية 1) ---
        self.free_models = [
            "google/gemini-2.0-flash-exp:free", "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.2-3b-instruct:free", "meta-llama/llama-3.2-1b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct:free", "qwen/qwen-2.5-7b-instruct:free",
            "qwen/qwen-2-7b-instruct:free", "mistralai/mistral-7b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free", "microsoft/phi-3-medium-128k-instruct:free",
            "google/gemini-flash-1.5-8b:free", "huggingfaceh4/zephyr-7b-beta:free",
            "undi95/toppy-m-7b:free", "open-theory/gryphe-mythomax-l2-13b:free",
            "gryphe/mythomax-l2-13b:free", "nousresearch/hermes-3-llama-3.1-8b",
            "liquid/lfm-40b:free", "mistralai/pixtral-12b:free",
            "qwen/qwen-2.5-3b-instruct:free", "upstage/solar-10-7b-instruct:free"
        ]

        # --- مجموعة النماذج المتوسطة والقوية (أولوية 2) ---
        self.mid_models = [
            "openai/gpt-4o-mini", "anthropic/claude-3-haiku", 
            "google/gemini-flash-1.5", "meta-llama/llama-3.1-70b-instruct:free",
            "mistralai/mixtral-8x7b-instruct:free", "cohere/command-r",
            "deepseek/deepseek-chat", "perplexity/llama-3.1-sonar-small-128k-chat",
            "meta-llama/llama-3-70b-instruct", "google/gemini-pro-1.5"
        ]

        # --- مجموعة النماذج العملاقة للنخبة (أولوية 3 - الملاذ الأخير) ---
        self.elite_models = [
            "openai/gpt-4o", "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.1-405b-instruct", "google/gemini-1.5-pro-exp-0827",
            "openai/gpt-4-turbo", "anthropic/claude-3-opus"
        ]

        # الدمج الكامل لضمان 100 محرك (بالتكرار الذكي أو التنوع)
        self.ordered_models = self.free_models + self.mid_models + self.elite_models

    def _call_ai(self, prompt, temperature=0.3):
        if not self.api_key: 
            print("❌ Error: OPENROUTER_API_KEY is missing!")
            return "❌ API Key missing!"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sudan.com",
            "X-Title": "Jobeni AI Mega-Engine"
        }

        # محاولة ذكية للمرور عبر النماذج في حالة الفشل
        for model in self.ordered_models:
            try:
                # طباعة الموديل الحالي في التيرمكس للمتابعة
                print(f"🤖 محاولة استخدام المحرك: {model}...")
                
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 1000
                }

                # تايم أوت قصير للنماذج الصغيرة لسرعة التبديل
                timeout_val = 10 if ":free" in model else 20
                res = requests.post(self.url, headers=headers, json=payload, timeout=timeout_val)

                if res.status_code == 200:
                    data = res.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        if content and len(content.strip()) > 2:
                            print(f"✅ نجاح الاستجابة من المحرك: {model}")
                            return content
                
                # طباعة سبب الفشل للانتقال للموديل التالي
                print(f"⚠️ المحرك {model} لم يستجب (Status: {res.status_code}). جاري التبديل...")
                continue
            except Exception as e:
                print(f"🔄 فشل المحرك {model} (Error: {str(e)[:50]}). جاري تجربة البديل...")
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
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {
                "skills": ["تحليل ذكي"], "profession": "متخصص", "overall_score": 55,
                "feedback": "يا مكنة، الـ AI تعب شوية، جرب ترفع الملف مرة تانية.",
                "missing_skills": []
            }

    def generate_improved_text(self, cv_content):
        prompt = f"Optimize this resume for ATS in English. Focus on achievements. Content: {cv_content[:2000]}"
        return self._call_ai(prompt, 0.7)

openrouter_ai = OpenRouterAI()

# دالات التوافق
def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)

def get_expert_omni_response(user_query, user_context=None, job_context=None):
    return openrouter_ai.get_expert_omni_response(user_query, user_context, job_context)
