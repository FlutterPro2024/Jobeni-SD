self.addEventListener('install', (e) => {
  console.log('Jobeni Service Worker Installed');
});
self.addEventListener('fetch', (e) => {
  e.respondWith(fetch(e.request));
});
