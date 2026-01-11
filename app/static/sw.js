// ~/jobeni-sD/app/static/sw.js

const CACHE_NAME = 'jobeni-v3'; // رفعنا الإصدار لتنظيف الـ Cache القديم
const OFFLINE_URL = '/';

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll([
                '/',
                '/static/css/style.css', // تأكد من وجود المسارات الصحيحة لملفاتك
                '/static/icon.png'
            ]);
        })
    );
    // تفعيل الـ Service Worker الجديد فوراً
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Cleaning old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // استراتيجية: حاول الشبكة أولاً، وإذا فشلت عد للـ Cache
    // استثناء روابط الـ API والـ Admin من الكاش لضمان تحديث البيانات
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => {
                return caches.match(OFFLINE_URL);
            })
        );
    } else {
        event.respondWith(
            caches.match(event.request).then((response) => {
                return response || fetch(event.request);
            })
        );
    }
});
