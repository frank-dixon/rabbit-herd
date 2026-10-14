{% autoescape off %}/* Bramble Burrow service worker. Version {{ version }}.
 * Shell assets: cache first. Pages: network first, the last copy kept for
 * offline use. Photos: cache first, refreshed in the background.
 * Sign-in pages, admin and anything that is not a GET are never cached. */
const VERSION = "{{ version }}";
const SHELL = "bb-shell-" + VERSION;
const PAGES = "bb-pages";
const PHOTOS = "bb-photos";
const OFFLINE_URL = "/offline/";
const SHELL_URLS = [OFFLINE_URL, "/manifest.webmanifest"{% for asset in assets %}, "{{ asset|escapejs }}"{% endfor %}];
const MAX_PAGES = 60;
const MAX_PHOTOS = 120;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("bb-shell-") && key !== SHELL).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "clear-private") {
    event.waitUntil(Promise.all([caches.delete(PAGES), caches.delete(PHOTOS)]));
  }
});

async function trim(name, max) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(keys.length - max, 0)).map((key) => cache.delete(key)));
}

function cacheable(url) {
  return !/^\/(accounts|admin)\//.test(url.pathname) && url.pathname !== "/sw.js";
}

async function page(request) {
  try {
    const response = await fetch(request);
    if (response.ok && !response.redirected && (response.headers.get("content-type") || "").includes("text/html")) {
      const cache = await caches.open(PAGES);
      await cache.delete(request);
      await cache.put(request, response.clone());
      trim(PAGES, MAX_PAGES);
    }
    return response;
  } catch (error) {
    const saved = await caches.match(request, { cacheName: PAGES });
    return saved || (await caches.match(OFFLINE_URL));
  }
}

async function photo(request) {
  const cache = await caches.open(PHOTOS);
  const saved = await cache.match(request);
  const fresh = fetch(request).then((response) => {
    if (response.ok && !response.redirected) {
      cache.put(request, response.clone()).then(() => trim(PHOTOS, MAX_PHOTOS));
    }
    return response;
  });
  if (saved) {
    fresh.catch(() => null);
    return saved;
  }
  return fresh;
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || !cacheable(url)) {
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(page(request));
  } else if (/^\/rabbits\/(photos\/\d+|outside\/\d+\/photo)\/$/.test(url.pathname)) {
    event.respondWith(photo(request));
  } else if (url.pathname.startsWith("/static/") || url.pathname === "/manifest.webmanifest") {
    event.respondWith(caches.match(request).then((saved) => saved || fetch(request)));
  }
});
{% endautoescape %}
