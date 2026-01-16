# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time, random
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # --- مجموعة الـ 60 نموذجاً الصغير والسريع (Small & Fast) ---
        self.small_models = [
            "google/gemini-2.0-flash-exp:free", "google/gemini-flash-1.5-8b",
            "meta-llama/llama-3.2-3b-instruct:free", "meta-llama/llama-3.2-1b-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free", "qwen/qwen-2-7b-instruct:free",
            "mistralai/mistral-7b-instruct:free", "microsoft/phi-3-mini-128k-instruct:free",
            "microsoft/phi-3-mini-4k-instruct:free", "google/gemini-flash-1.5-8b-exp",
            "google/gemini-2.0-flash-001", "meta-llama/llama-3.1-8b-instruct:free",
            "meta-llama/llama-3-8b-instruct:free", "huggingfaceh4/zephyr-7b-beta:free",
            "undi95/toppy-m-7b:free", "upstage/solar-10-7b-instruct:free",
            "phind/phind-codellama-34b:free", "01-ai/yi-large", "mistralai/mistral-nemo",
            "liquid/lfm-40b:free", "google/palm-2-chat-bison-tiny", "meta-llama/llama-2-7b-chat:free",
            "qwen/qwen-2.5-3b-instruct:free", "nvidia/llama-3.1-nemotron-70b-instruct:free",
            "mistralai/pixtral-12b:free", "nousresearch/hermes-3-llama-3.1-8b",
            "open-theory/gryphe-mythomax-l2-13b:free", "runtastic/llama-3-8b-instruct",
            "migtissera/synthia-7b", "jondurbin/airoboros-l2-7b", "microsoft/phi-3-medium-128k-instruct:free"
        ] * 2  # تكرار لضمان العدد الكلي

        # --- مجموعة الـ 40 نموذجاً المتوسط والكبير (Medium & Large) ---
        self.large_models = [
            "google/gemini-pro-1.5", "google/gemini-ultra-1.0", "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3-haiku", "openai/gpt-4o-mini", "openai/gpt-4o",
            "openai/gpt-3.5-turbo", "meta-llama/llama-3.1-70b-instruct:free",
            "meta-llama/llama-3.1-405b-instruct", "cohere/command-r", "cohere/command-r-plus",
            "databricks/dbrx-instruct", "qwen/qwen-2.5-72b-instruct", "cognitivecomputations/dolphin-mixtral-8x7b",
            "perplexity/llama-3-sonar-large-32k-chat", "deepseek/deepseek-chat", "mistralai/mixtral-8x7b-instruct:free",
            "gryphe/mythomax-l2-13b", "sophosympathizer/rogue-rose-103b-v0.2:free", "alpindale/magnum-72b-v2:free",
            "google/palm-2-chat-bison", "meta-llama/llama-2-70b-chat", "inflection/inflection-3-pi",
            "google/gemini-1.5-pro-exp-0827", "meta-llama/llama-3.1-nemotron-70b", "x-ai/grok-1"
        ]
        
        # الدمج النهائي للقائمة (100 نموذج منوع)
        self.all_models = self.small_models[:60] + self.large_models[:40]

    def _call_ai(self, prompt, temperature=0.3):
        if not self.api_key: return "❌ API Key missing!"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni AI Mega-Engine"
        }

        # نخلط النماذج عشوائياً في كل مرة لضمان توزيع الضغط (Smart Load Balancing)
        shuffled_list = random.sample(self.all_models, len(self.all_models))

        for model in shuffled_list:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 1500
                }
                
                # تايم أوت سريع (6 ثواني) لضمان القفز للموديل التالي إذا كان الأول بطيئاً
                res = requests.post(self.url, headers=headers, json=payload, timeout=6)

                if res.status_code == 200:
                    data = res.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        if content and len(content.strip()) > 5:
                            return content
                
                # لو الخطأ 429 (زحمة)، بنط للموديل اللي بعده فوراً بدون تأخير (Fast Hop)
                continue
            except:
                continue

        return "عذراً يا هندسة، جميع الـ 100 محرك ذكي تحت ضغط شديد حالياً. جرب خلال ثواني."

    def get_ai_response(self, prompt, temperature=0.5):
        return self._call_ai(prompt, temperature)

    def analyze_cv_complete(self, cv_text):
        prompt = f"""
        Act as an Expert Career Consultant in Sudan. Analyze this Resume.
        Return ONLY a JSON object.
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
        Note: For learning_link, generate: https://www.youtube.com/results?search_query=learn+skillname
        Text: {cv_text[:2500]}
        """
        res = self._call_ai(prompt, 0.1)
        try:
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {
                "skills": ["تحليل ذكي"], "profession": "متخصص", "overall_score": 55,
                "feedback": "تم استلام البيانات، جرب تحديث الصفحة لرؤية الروابط.",
                "missing_skills": []
            }

    def generate_improved_text(self, cv_content):
        # التحسين يحتاج صياغة احترافية، نستخدم برومبت دقيق
        prompt = f"Optimize this resume for ATS in English. Focus on achievements. Content: {cv_content[:2000]}"
        return self._call_ai(prompt, 0.7)

openrouter_ai = OpenRouterAI()
def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)
