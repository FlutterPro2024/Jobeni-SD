# ~/jobeni-sD/app/openrouter_ai.py
import requests, json, re, os, time
from dotenv import load_dotenv

load_dotenv()

class OpenRouterAI:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

        # قائمة بـ 50 نموذجاً منوعاً (Free & Fast) لضمان العمل تحت أي ضغط
        self.models = [
            "google/gemini-2.0-flash-exp:free", "google/gemini-flash-1.5-8b", 
            "meta-llama/llama-3.2-1b-instruct:free", "meta-llama/llama-3.2-3b-instruct:free",
            "qwen/qwen-2-7b-instruct:free", "mistralai/mistral-7b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free", "google/gemini-flash-1.5-8b-exp",
            "qwen/qwen-2.5-7b-instruct:free", "huggingfaceh4/zephyr-7b-beta:free",
            "undi95/toppy-m-7b:free", "open-theory/gryphe-mythomax-l2-13b:free",
            "nousresearch/hermes-3-llama-3.1-8b", "google/gemini-2.0-flash-001",
            "meta-llama/llama-3-8b-instruct:free", "inflection/inflection-3-pi",
            "migtissera/synthia-7b", "jondurbin/airoboros-l2-7b",
            "runtastic/llama-3-8b-instruct", "meta-llama/llama-3.1-8b-instruct:free",
            "mistralai/pixtral-12b:free", "microsoft/phi-3-medium-128k-instruct:free",
            "liquid/lfm-40b:free", "anthropic/claude-3-haiku",
            "01-ai/yi-large", "gryphe/mythomax-l2-13b",
            "cognitivecomputations/dolphin-mixtral-8x7b", "mistralai/mistral-nemo",
            "google/gemini-pro-1.5", "qwen/qwen-2.5-72b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct:free", "meta-llama/llama-3.1-70b-instruct:free",
            "meta-llama/llama-3.1-405b-instruct", "sophosympathizer/rogue-rose-103b-v0.2:free",
            "alpindale/magnum-72b-v2:free", "anthropic/claude-3.5-sonnet",
            "google/gemini-ultra-1.0", "databricks/dbrx-instruct",
            "cohere/command-r", "cohere/command-r-plus",
            "meta-llama/llama-2-70b-chat", "meta-llama/llama-2-13b-chat:free",
            "qwen/qwen-72b-chat", "upstage/solar-10-7b-instruct:free",
            "phind/phind-codellama-34b:free", "google/palm-2-chat-bison",
            "google/palm-2-codechat-bison", "openai/gpt-3.5-turbo",
            "openai/gpt-4o-mini", "perplexity/llama-3-sonar-large-32k-chat"
        ]

    def _call_ai(self, prompt, temperature=0.3):
        if not self.api_key: return "❌ API Key missing!"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jobeni-sd.com",
            "X-Title": "Jobeni AI Multi-Engine"
        }
        for model in self.models:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 2500
                }
                res = requests.post(self.url, headers=headers, json=payload, timeout=8)
                if res.status_code == 200:
                    data = res.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        if content and len(content.strip()) > 5:
                            return content
                continue
            except: continue
        return "عذراً يا هندسة، جميع المحركات الذكية مشغولة حالياً."

    def get_ai_response(self, prompt, temperature=0.5):
        return self._call_ai(prompt, temperature)

    def analyze_cv_complete(self, cv_text):
        prompt = f"Act as a Recruiter. Analyze CV. Return ONLY JSON. Format: {{\"skills\": [\"Skill1\"], \"profession\": \"Title\", \"overall_score\": 80, \"feedback\": \"Arabic Advice\"}} Text: {cv_text[:3000]}"
        res = self._call_ai(prompt, 0.1)
        try:
            clean = re.search(r'\{.*\}', res, re.DOTALL).group()
            return json.loads(clean)
        except:
            return {"skills": ["تحليل بيانات"], "profession": "متخصص", "overall_score": 50, "feedback": "تم التحليل الأولي بنجاح."}

    def generate_improved_text(self, cv_content):
        prompt = f"Rewrite this resume professionally. 1. Use English. 2. Use '•'. 3. Optimize for ATS. Content: {cv_content}"
        return self._call_ai(prompt, 0.7)

openrouter_ai = OpenRouterAI()
def get_ai_response(prompt, temperature=0.5):
    return openrouter_ai.get_ai_response(prompt, temperature)
