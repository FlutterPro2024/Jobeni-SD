# ~/jobeni-sD/app/serper_search.py
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

class SerperSearcher:
    def __init__(self):
        # استخدام المفتاح من البيئة أو المفتاح الافتراضي
        self.api_key = os.getenv("SERPER_API_KEY") or "fbe0d3c43b26afed1d11adce1718bdd568d8d331"
        self.url = "https://google.serper.dev/search"

    def search_jobs(self, query):
        if not self.api_key:
            return {"jobs": []}

        # تحسين الاستعلام ليشمل كلمات دلالية تجلب روابط التقديم المباشر
        # مثل: hiring, career, apply now
        refined_query = f"{query} hiring career opportunities"
        
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        payload = json.dumps({
            "q": refined_query,
            "gl": "us", # البحث عالمياً
            "hl": "ar", # دعم النتائج العربية والإنجليزية معاً
            "num": 12
        })

        try:
            response = requests.post(self.url, headers=headers, data=payload, timeout=12)
            if response.status_code == 200:
                results = response.json()
                organic = results.get('organic', [])

                jobs = []
                for item in organic:
                    link = item.get('link', '')
                    # استخراج اسم الموقع الذكي (مثل LinkedIn أو Indeed)
                    domain_parts = link.split('/')[2].replace('www.', '').split('.')
                    company_name = domain_parts[0].capitalize() if len(domain_parts) > 1 else "Global Job"

                    jobs.append({
                        'title': item.get('title'),
                        'link': link,
                        'company': company_name,
                        'location': 'International / Remote',
                        'snippet': item.get('snippet', '')
                    })
                return {"jobs": jobs}
        except Exception as e:
            print(f"Serper Search Error: {e}")

        return {"jobs": []}

serper_searcher = SerperSearcher()
