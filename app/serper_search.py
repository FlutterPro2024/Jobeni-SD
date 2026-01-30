# ~/jobeni-sD/app/serper_search.py
import requests
import json
import os
import re
from dotenv import load_dotenv
from app.openrouter_ai import openrouter_ai # استدعاء المحرك للترجمة الذكية

load_dotenv()

class SerperSearcher:
    def __init__(self):
        self.api_key = os.getenv("SERPER_API_KEY")
        self.url = "https://google.serper.dev/search"

    def _smart_translate_query(self, query):
        """ترجمة وتحسين الكلمة البحثية لضمان أفضل نتائج عالمية"""
        prompt = f"Translate and optimize this job/scholarship search term to English for a global Google search: '{query}'. Output ONLY the optimized English term."
        try:
            optimized = openrouter_ai.get_ai_response(prompt, temperature=0.1)
            return optimized.strip().replace('"', '')
        except:
            return query # في حال فشل الذكاء الاصطناعي نستخدم النص الأصلي

    def search_jobs(self, query):
        """المحرك الذكي للبحث عن الوظائف والمنح الدراسية عالمياً 2026"""
        if not self.api_key:
            print("⚠️ SERPER_API_KEY is missing!")
            return {"jobs": []}

        # 1. الترجمة الذكية للاستعلام
        english_query = self._smart_translate_query(query)
        
        # 2. ذكاء اصطناعي بسيط لتحديد نوع البحث
        is_scholarship = any(word in query.lower() for word in ['scholarship', 'منحة', 'منح', 'study', 'phd', 'masters'])

        if is_scholarship:
            # تحسين الاستعلام للمنح
            refined_query = f"{english_query} fully funded scholarship 2026 for sudanese students official link"
        else:
            # تحسين الاستعلام للوظائف العالمية
            refined_query = f"{english_query} hiring career opportunities remote worldwide 2026"

        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        payload = json.dumps({
            "q": refined_query,
            "gl": "us",
            "hl": "en", # تغيير اللغة لـ en لضمان نتائج عالمية أدق
            "num": 25 
        })

        try:
            print(f"🔍 Searching for: {refined_query}") # لمراقبة الأداء في الـ Shell
            response = requests.post(self.url, headers=headers, data=payload, timeout=12)
            if response.status_code == 200:
                results = response.json()
                organic = results.get('organic', [])
                jobs = []
                for item in organic:
                    link = item.get('link', '')
                    if not link: continue

                    try:
                        domain_parts = link.split('/')[2].replace('www.', '').split('.')
                        source_name = domain_parts[0].capitalize() if len(domain_parts) > 1 else "Global Source"
                    except:
                        source_name = "Global Portal"

                    jobs.append({
                        'title': item.get('title', 'No Title'),
                        'link': link,
                        'company': source_name,
                        'location': 'Worldwide / Remote',
                        'snippet': item.get('snippet', '')
                    })
                return {"jobs": jobs}
            else:
                print(f"Serper API Status Error: {response.status_code}")
        except Exception as e:
            print(f"Serper Search Connection Error: {e}")

        return {"jobs": []}

serper_searcher = SerperSearcher()
