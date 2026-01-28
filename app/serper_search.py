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
        """المحرك الذكي للبحث عن الوظائف والمنح الدراسية عالمياً 2026"""
        if not self.api_key:
            print("⚠️ SERPER_API_KEY is missing!")
            return {"jobs": []}

        # ذكاء اصطناعي بسيط لتحديد نوع البحث وتخصيص الاستعلام
        is_scholarship = any(word in query.lower() for word in ['scholarship', 'منحة', 'منح', 'study', 'phd', 'masters'])
        
        if is_scholarship:
            # تحسين الاستعلام لجلب منح حقيقية وممولة بالكامل للسودانيين 2026
            refined_query = f"{query} fully funded scholarship 2026 for sudanese students official link"
        else:
            # تحسين الاستعلام لجلب نتائج توظيف عالمية 2026
            refined_query = f"{query} hiring career opportunities remote worldwide 2026"

        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        payload = json.dumps({
            "q": refined_query,
            "gl": "us", # البحث العالمي يبدأ من النطاق الأمريكي للأرشفة الأسرع
            "hl": "ar",
            "num": 25 # زيادة عدد النتائج لضمان جودة الفلترة لاحقاً
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

                    # استخراج اسم الموقع/المصدر بأمان
                    try:
                        domain_parts = link.split('/')[2].replace('www.', '').split('.')
                        # إذا كان الموقع مشهوراً نأخذ اسمه، وإلا نعتبره "مصدر عالمي"
                        source_name = domain_parts[0].capitalize() if len(domain_parts) > 1 else "Global Source"
                    except:
                        source_name = "Global Portal"

                    jobs.append({
                        'title': item.get('title', 'No Title'),
                        'link': link,
                        'company': source_name, # يمثل الشركة في الوظائف والجامعة/المنظمة في المنح
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
