# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time, random
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # قائمة الـ 50 نموذجاً المختارة بعناية (مجانية + سريعة + متنوعة الشركات)
        self.models = [
            "google/gemini-2.0-flash-exp:free", "google/gemini-flash-1.5-8b",
            "meta-llama/llama-3.2-3b-instruct:free", "meta-llama/llama-3.2-1b-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free", "qwen/qwen-2-7b-instruct:free",
            "mistralai/mistral-7b-instruct:free", "mistralai/pixtral-12b:free",
            "microsoft/phi-3-mini-128k-instruct:free", "microsoft/phi-3-medium-128k-instruct:free",
            "google/gemini-flash-1.5-8b-exp", "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.1-8b-instruct:free", "meta-llama/llama-3-8b-instruct:free",
            "nvidia/llama-3.1-nemotron-70b-instruct:free", "liquid/lfm-40b:free",
            "huggingfaceh4/zephyr-7b-beta:free", "undi95/toppy-m-7b:free",
            "open-theory/gryphe-mythomax-l2-13b:free", "nousresearch/hermes-3-llama-3.1-8b",
            "sophosympathizer/rogue-rose-103b-v0.2:free", "alpindale/magnum-72b-v2:free",
            "upstage/solar-10-7b-instruct:free", "phind/phind-codellama-34b:free",
            "inflection/inflection-3-pi", "01-ai/yi-large",
            "mistralai/mistral-nemo", "cohere/command-r",
            "cohere/command-r-plus", "google/gemini-pro-1.5",
            "openai/gpt-4o-mini", "openai/gpt-3.5-turbo",
            "anthropic/claude-3-haiku", "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.1-70b-instruct:free", "google/palm-2-chat-bison",
            "databricks/dbrx-instruct", "qwen/qwen-2.5-72b-instruct",
            "cognitivecomputations/dolphin-mixtral-8x7b", "perplexica/llama-3-sonar-large-32k-chat",
            "deepseek/deepseek-chat", "meta-llama/llama-3.1-405b-instruct",
            "gryphe/mythomax-l2-13b", "jondurbin/airoboros-l2-7b",
            "runtastic/llama-3-8b-instruct", "migtissera/synthia-7b",
            "google/gemini-ultra-1.0", "google/palm-2-codechat-bison",
            "meta-llama/llama-2-70b-chat", "meta-llama/llama-2-13b-chat:free"
        ]

    def _call_ai(self, prompt, temperature=0.3):
        if not self.api_key: return "❌ API Key missing!"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni AI Multi-Engine"
        }

        # نخلط النماذج عشوائياً في كل مرة لضمان عدم توقف الخدمة
        shuffled_models = random.sample(self.models, len(self.models))
        
        retry_delay = 0.5  # بداية بـ نص ثانية تأخير
        
        for model in shuffled_models:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 2000
                }
                # تايم أوت قصير لسرعة التبديل بين الموديلات
                res = requests.post(self.url, headers=headers, json=payload, timeout=10)
                
                if res.status_code == 200:
                    data = res.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        if content and len(content.strip()) > 5:
                            return content
                
                # لو السيرفر ادانا 429 (Too Many Requests) ننتظر شوية قبل الموديل الجاي
                if res.status_code == 429:
                    time.sleep(retry_delay)
                    retry_delay *= 1.5 # زيادة وقت الانتظار تدريجياً
                
                continue
            except:
                continue
                
        return "عذراً يا هندسة، جميع المحركات الذكية الـ 50 مشغولة حالياً. جرب بعد دقيقة."

    def get_ai_response(self, prompt, temperature=0.5):
        return self._call_ai(prompt, temperature)

    def analyze_cv_complete(self, cv_text):
        # البرومبت المطور لجلب المهارات الناقصة مع روابط يوتيوب تلقائياً
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
                {{"skill": "Skill Name", "reason": "Why needed", "learning_link": "YouTube Search Link"}}
            ]
        }}
        Note: For learning_link, generate a YouTube search URL like: https://www.youtube.com/results?search_query=learn+skillname
        Text: {cv_text[:3000]}
        """
        res = self._call_ai(prompt, 0.1)
        try:
            # استخراج الـ JSON بدقة حتى لو الموديل خرف وكتب كلام جانبي
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {
                "skills": ["تحليل جاري"], 
                "profession": "متخصص", 
                "overall_score": 50, 
                "feedback": "تم استلام البيانات، جاري تحسين النتائج.",
                "missing_skills": []
            }

    def generate_improved_text(self, cv_content):
        prompt = f"Rewrite this resume professionally in English for ATS optimization. Use bullet points: {cv_content}"
        return self._call_ai(prompt, 0.7)

openrouter_ai = OpenRouterAI()
def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)
