# ~/jobeni-sD/app/serper_search.py
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

class SerperSearcher:
    def __init__(self):
        # بياخد المفتاح من Environment Variables في فيرسيل أو المحلي
        self.api_key = os.getenv("SERPER_API_KEY")
        self.url = "https://google.serper.dev/search"      
    
    def search_jobs(self, query):
        if not self.api_key:
            print("⚠️ SERPER_API_KEY is missing!")
            return {"jobs": []}

        # تحسين الاستعلام لجلب نتائج توظيف حقيقية
        refined_query = f"{query} hiring career opportunities 2026"

        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }                                                  
        payload = json.dumps({
            "q": refined_query,
            "gl": "us", 
            "hl": "ar", 
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
                    if not link: continue
                    
                    # استخراج اسم الموقع بأمان لتجنب الـ Index Error
                    try:
                        domain_parts = link.split('/')[2].replace('www.', '').split('.')
                        company_name = domain_parts[0].capitalize() if len(domain_parts) > 1 else "Global Job"
                    except:
                        company_name = "Global Source"

                    jobs.append({
                        'title': item.get('title', 'No Title'),
                        'link': link,
                        'company': company_name,
                        'location': 'International / Remote',
                        'snippet': item.get('snippet', '')
                    })
                return {"jobs": jobs}
            else:
                print(f"Serper API Status Error: {response.status_code}")
        except Exception as e:
            print(f"Serper Search Connection Error: {e}")

        return {"jobs": []}

serper_searcher = SerperSearcher()
