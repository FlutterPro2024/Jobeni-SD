import requests
from bs4 import BeautifulSoup
from .models import Job, db
from .openrouter_ai import openrouter_ai
import time
import random

class ScholarshipScraper:
    def __init__(self):
        self.targets = [
            "https://www.scholarships.com", "https://www.fastweb.com",
            "https://www.chegg.com/scholarships", "https://www.internationalscholarships.com",
            "https://www.scholarshipportal.com", "https://www.daad.de/en/",
            "https://foreign.fulbrightonline.org/", "https://www.chevening.org/",
            "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en",
            "https://www.studyinjapan.go.jp/en/", "https://www.csc.edu.cn/",
            "https://cscuk.fcdo.gov.uk/", "https://www.gatescambridge.org/",
            "https://www.rhodeshouse.ox.ac.uk/", "https://www.sbfi.admin.ch/sbfi/en/home/education/scholarships-and-grants.html",
            "https://www.studyinnl.org/finances/scholarships", "https://www.studyportals.com/",
            "https://bigfuture.collegeboard.org/scholarship-search", "https://scholarshipsads.com",
            "https://www.scholarshipdb.net", "https://globalscholarships.com",
            "https://scholarshipglobe.com", "https://www.cappex.com/",
            "https://www.niche.com/colleges/scholarships/", "https://scholarshipamerica.org/students/browse-scholarships/",
            "https://bold.org/scholarships", "http://www.scholarshipmonkey.com/",
            "https://www.petersons.com/college-search/scholarship-search.aspx",
            "https://www.careeronestop.org/Toolkit/Training/find-scholarships.aspx"
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def run_radar(self):
        """تشغيل الرادار على جميع المواقع"""
        report = []
        # نختار موقعين عشوائيين في كل دورة عشان ما نثقل على السيرفر
        selected_targets = random.sample(self.targets, k=3) 
        
        for url in selected_targets:
            try:
                print(f"📡 جاري فحص: {url}")
                response = requests.get(url, headers=self.headers, timeout=20)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'lxml')
                    
                    # استخراج الروابط والنصوص التي تحتوي على كلمة Scholarship
                    links = soup.find_all('a', href=True)
                    potential_scholarships = []
                    
                    for link in links:
                        text = link.text.strip().lower()
                        href = link['href']
                        if "scholarship" in text or "grant" in text or "funding" in text:
                            if href.startswith('/'): href = url + href
                            potential_scholarships.append({"title": link.text.strip(), "url": href})

                    # حفظ أول 5 نتائج جديدة من كل موقع
                    count = 0
                    for item in potential_scholarships[:5]:
                        exists = Job.query.filter_by(source_link=item['url']).first()
                        if not exists:
                            # استخدام AI لتنظيف العنوان
                            clean_title = openrouter_ai.get_ai_response(f"Clean this scholarship title: {item['title']}")
                            
                            new_entry = Job(
                                title=clean_title or item['title'],
                                company="Global Provider",
                                source_link=item['url'],
                                category="Scholarship",
                                is_active=True
                            )
                            db.session.add(new_entry)
                            count += 1
                    
                    db.session.commit()
                    report.append(f"✅ {url}: وجدنا {count} منحة جديدة.")
                else:
                    report.append(f"⚠️ {url}: استجابة غير صالحة ({response.status_code})")
            except Exception as e:
                report.append(f"❌ {url}: خطأ - {str(e)}")
        
        return "\n".join(report)

scholarship_scraper = ScholarshipScraper()
