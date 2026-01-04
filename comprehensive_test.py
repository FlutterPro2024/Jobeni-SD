import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

def run_comprehensive_test():
    api_key = os.getenv("OPENROUTER_API_KEY")
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # قائمة النماذج المجانية مرتبة من الأقوى (الأكثر ذكاءً) إلى الأخف
    models = [
        # --- DeepSeek (الأقوى حالياً في البرمجة والتحليل) ---
        "deepseek/deepseek-r1:free",
        "deepseek/deepseek-chat:free",
        
        # --- Google (الأفضل في السرعة ودقة النصوص) ---
        "google/gemini-2.0-pro-exp-02-05:free",
        "google/gemini-2.0-flash-lite-preview-02-05:free",
        
        # --- Meta & Grok (الأقوى في اللغة الإنجليزية والمنطق العام) ---
        "meta-llama/llama-3.3-70b-instruct:free",
        "x-ai/grok-2-1212:free", # إذا كان متاحاً في منطقتك
        
        # --- Mistral & Claude-style (استقرار عالي) ---
        "mistralai/mistral-7b-instruct:free",
        "anthropic/claude-3-haiku:free", # بعض الحسابات توفر نسخة مجانية محدودة
        
        # --- Qwen & Microsoft (ممتازين جداً في الـ JSON) ---
        "qwen/qwen-2.5-72b-instruct:free",
        "microsoft/phi-3-medium-128k-instruct:free"
    ]
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "Jobeni SD Ultimate Tester"
    }

    print(f"🚀 بدء الاختبار الشامل لـ {len(models)} نموذج مجاني...")
    print(f"🔑 المفتاح المستخدم: {api_key[:8]}****")
    print("-" * 50)

    results = []

    for model in models:
        print(f"🔄 جاري فحص: {model} ...")
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Return the word 'READY' if you can read this."}],
            "max_tokens": 10
        }

        try:
            start_time = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            end_time = time.time()
            
            if response.status_code == 200:
                print(f"✅ نجاااح! الرد: {response.json()['choices'][0]['message']['content'].strip()}")
                print(f"⏱️ زمن الاستجابة: {end_time - start_time:.2f} ثانية")
                results.append((model, "Success"))
            else:
                print(f"❌ فشل (حالة {response.status_code}).")
                print(f"⚠️ السبب: {response.text[:100]}")
                results.append((model, f"Failed ({response.status_code})"))
                
                # الانتظار 5 ثواني في حال الفشل قبل تجربة الموديل الأقل قوة
                print(f"⏳ انتظار 5 ثواني قبل تجربة الموديل التالي...")
                time.sleep(5)
                
        except Exception as e:
            print(f"💥 خطأ في الاتصال: {str(e)}")
            results.append((model, "Connection Error"))
            time.sleep(5)

    print("\n" + "="*50)
    print("📊 ملخص الاختبار النهائي:")
    print("="*50)
    for model, status in results:
        icon = "✅" if status == "Success" else "❌"
        print(f"{icon} {model.ljust(45)} : {status}")

if __name__ == "__main__":
    run_comprehensive_test()
