"""
صفحة اختبار APIs والنماذج
"""
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
import os
import requests
import json
from datetime import datetime

test_bp = Blueprint('test', __name__)

@test_bp.route('/test/apis')
@login_required
def test_apis_dashboard():
    """لوحة تحكم لاختبار جميع APIs"""
    return render_template('test_apis.html')

@test_bp.route('/api/test/serper')
def test_serper_api():
    """اختبار Serper API"""
    api_key = os.environ.get('SERPER_API_KEY')
    
    if not api_key:
        return jsonify({
            'status': 'error',
            'message': '❌ مفتاح Serper API غير موجود',
            'details': 'قم بتعيين متغير البيئة SERPER_API_KEY'
        })
    
    # اختبار بسيط
    test_query = "مطور ويب وظيفة"
    
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "q": test_query,
        "gl": "sa",
        "hl": "ar",
        "num": 3
    }
    
    try:
        start_time = datetime.now()
        response = requests.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=payload,
            timeout=10
        )
        end_time = datetime.now()
        
        response_time = (end_time - start_time).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            organic_count = len(data.get('organic', []))
            
            return jsonify({
                'status': 'success',
                'message': f'✅ Serper API يعمل بشكل صحيح',
                'details': {
                    'status_code': response.status_code,
                    'response_time': f'{response_time:.2f} ثانية',
                    'results_found': organic_count,
                    'api_key_first_chars': api_key[:10] + '...',
                    'api_key_valid': True
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'❌ خطأ في Serper API',
                'details': {
                    'status_code': response.status_code,
                    'response_text': response.text[:200],
                    'api_key_first_chars': api_key[:10] + '...'
                }
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'❌ فشل الاتصال بـ Serper API',
            'details': {
                'error': str(e),
                'api_key_first_chars': api_key[:10] + '...'
            }
        })

@test_bp.route('/api/test/openrouter')
def test_openrouter_api():
    """اختبار OpenRouter API"""
    api_key = os.environ.get('OPENROUTER_API_KEY')
    
    if not api_key:
        return jsonify({
            'status': 'error',
            'message': '❌ مفتاح OpenRouter API غير موجود',
            'details': 'قم بتعيين متغير البيئة OPENROUTER_API_KEY'
        })
    
    # اختبار بسيط
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Jobeni-SD Test"
    }
    
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [
            {"role": "user", "content": "قل مرحبا فقط"}
        ],
        "temperature": 0.1,
        "max_tokens": 10
    }
    
    try:
        start_time = datetime.now()
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        end_time = datetime.now()
        
        response_time = (end_time - start_time).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            reply = data['choices'][0]['message']['content']
            
            return jsonify({
                'status': 'success',
                'message': f'✅ OpenRouter API يعمل بشكل صحيح',
                'details': {
                    'status_code': response.status_code,
                    'response_time': f'{response_time:.2f} ثانية',
                    'model_used': payload['model'],
                    'ai_reply': reply,
                    'api_key_first_chars': api_key[:10] + '...',
                    'api_key_valid': True
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'❌ خطأ في OpenRouter API',
                'details': {
                    'status_code': response.status_code,
                    'response_text': response.text[:200],
                    'api_key_first_chars': api_key[:10] + '...'
                }
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'❌ فشل الاتصال بـ OpenRouter API',
            'details': {
                'error': str(e),
                'api_key_first_chars': api_key[:10] + '...'
            }
        })

@test_bp.route('/api/test/openrouter_full')
def test_openrouter_full_analysis():
    """اختبار تحليل كامل باستخدام OpenRouter"""
    api_key = os.environ.get('OPENROUTER_API_KEY')
    
    if not api_key:
        return jsonify({
            'status': 'error',
            'message': '❌ مفتاح OpenRouter API غير موجود'
        })
    
    cv_text = """
    أحمد محمد
    مطور ويب بخبرة 3 سنوات
    مهارات: Python, Flask, HTML, CSS, JavaScript
    خبرة: شركة التقنية (2022-2024)
    تعليم: بكالوريوس علوم حاسوب
    """
    
    from app.openrouter_ai import openrouter_ai
    
    try:
        start_time = datetime.now()
        analysis = openrouter_ai.analyze_cv_with_ai(cv_text)
        end_time = datetime.now()
        
        response_time = (end_time - start_time).total_seconds()
        
        return jsonify({
            'status': 'success',
            'message': '✅ تحليل OpenRouter يعمل بشكل صحيح',
            'details': {
                'response_time': f'{response_time:.2f} ثانية',
                'analysis_keys': list(analysis.keys()),
                'sample_data': {
                    'skills_count': len(analysis.get('skills', {}).get('technical', [])),
                    'overall_score': analysis.get('overall_score', 0),
                    'has_recommendations': len(analysis.get('job_recommendations', [])) > 0
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'❌ فشل تحليل OpenRouter',
            'details': {
                'error': str(e)
            }
        })

@test_bp.route('/api/test/serper_search')
def test_serper_search():
    """اختبار بحث حقيقي باستخدام Serper"""
    api_key = os.environ.get('SERPER_API_KEY')
    
    if not api_key:
        return jsonify({
            'status': 'error',
            'message': '❌ مفتاح Serper API غير موجود'
        })
    
    from app.serper_search import serper_searcher
    
    try:
        start_time = datetime.now()
        result = serper_searcher.search_jobs("مطور ويب", "السعودية", 5)
        end_time = datetime.now()
        
        response_time = (end_time - start_time).total_seconds()
        
        return jsonify({
            'status': 'success' if result.get('success') else 'error',
            'message': '✅ بحث Serper يعمل بشكل صحيح' if result.get('success') else '❌ فشل بحث Serper',
            'details': {
                'response_time': f'{response_time:.2f} ثانية',
                'total_jobs': result.get('total_results', 0),
                'jobs_found': len(result.get('jobs', [])),
                'sample_titles': [job.get('title', '')[:50] for job in result.get('jobs', [])[:3]]
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'❌ فشل بحث Serper',
            'details': {
                'error': str(e)
            }
        })

@test_bp.route('/api/test/all')
def test_all_apis():
    """اختبار جميع APIs في وقت واحد"""
    import threading
    import queue
    
    results = {}
    q = queue.Queue()
    
    def test_and_put(name, func):
        try:
            result = func()
            q.put((name, result))
        except Exception as e:
            q.put((name, {'status': 'error', 'error': str(e)}))
    
    # اختبار جميع APIs
    tests = [
        ('serper_basic', lambda: requests.get('http://localhost:5000/api/test/serper').json()),
        ('openrouter_basic', lambda: requests.get('http://localhost:5000/api/test/openrouter').json()),
        ('serper_search', lambda: requests.get('http://localhost:5000/api/test/serper_search').json()),
        ('openrouter_analysis', lambda: requests.get('http://localhost:5000/api/test/openrouter_full').json())
    ]
    
    threads = []
    for name, func in tests:
        t = threading.Thread(target=test_and_put, args=(name, func))
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    while not q.empty():
        name, result = q.get()
        results[name] = result
    
    # حساب الإحصائيات
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r.get('status') == 'success')
    
    return jsonify({
        'summary': {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'success_rate': f'{(passed_tests/total_tests)*100:.1f}%' if total_tests > 0 else '0%'
        },
        'detailed_results': results
    })
