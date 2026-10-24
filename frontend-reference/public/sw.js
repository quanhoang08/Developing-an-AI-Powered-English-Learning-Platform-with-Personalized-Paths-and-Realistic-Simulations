// Offline mode (tài liệu tính năng mục I.6): lưu bản app và kho từ chủ đề để các mini-game từ vựng
// (Memory, Word Rain, Bubble Pop, Word Search, Dictation Racer) chơi được khi mất mạng.
// Chỉ cache GET: app shell + /api/vocab/topics + /api/users/me (để app biết đang đăng nhập khi mất mạng; xóa lúc đăng xuất). Mọi API khác (chấm bài, XP, ví) luôn đi mạng.
const CACHE = "lumina-offline-v1";
const OFFLINE_API = ["/api/vocab/topics", "/api/users/me"];

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  const isShell = url.origin === self.location.origin && !url.pathname.startsWith("/api/");
  const isOfflineApi = OFFLINE_API.includes(url.pathname);
  if (!isShell && !isOfflineApi) return;
  // Network-first: luôn lấy bản mới khi có mạng, lùi về bản đã lưu khi mất mạng.
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request).then((hit) => hit || (request.mode === "navigate" ? caches.match("/") : Response.error()))),
  );
});
