{% autoescape off %}/* Bramble Burrow service worker. Version {{ version }}.
 * Shell assets: cache first. Pages: network first with a 3 second timeout,
 * then the last saved copy. Photos: cache first, refreshed in the background.
 * Sign-in pages (/login/, /signup/, /logout/, /accounts/), admin and anything
 * that is not a GET are never cached. */
const VERSION = "{{ version }}";
// Bump CACHE_SCHEMA when the shape of saved pages or photos changes; older
// caches are deleted on activate.
const CACHE_SCHEMA = "v2";
const SHELL = "bb-shell-" + VERSION;
const PAGES = "bb-pages-" + CACHE_SCHEMA;
const PHOTOS = "bb-photos-" + CACHE_SCHEMA;
const KEEP = [SHELL, PAGES, PHOTOS];
const NETWORK_TIMEOUT_MS = 3000;
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
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("bb-") && !KEEP.includes(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "clear-private") {
    event.waitUntil(clearPrivate());
  }
});

async function trim(name, max) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(keys.length - max, 0)).map((key) => cache.delete(key)));
}

const PRIVATE_PATHS = /^\/(accounts|admin|login|signup|logout|demo)(\/|$)/;

function cacheable(url) {
  return !PRIVATE_PATHS.test(url.pathname) && url.pathname !== "/sw.js";
}

function clearPrivate() {
  return Promise.all([caches.delete(PAGES), caches.delete(PHOTOS)]);
}

async function savePage(request, response) {
  if (response.redirected) {
    // Sent to sign-in: the session ended, so drop this device's private copies.
    if (PRIVATE_PATHS.test(new URL(response.url).pathname)) await clearPrivate();
    return;
  }
  if (!response.ok || !(response.headers.get("content-type") || "").includes("text/html")) return;
  const cache = await caches.open(PAGES);
  await cache.put(request, response);
  trim(PAGES, MAX_PAGES);
}

async function page(request) {
  const network = fetch(request);
  const stored = network.then((response) => savePage(request, response.clone())).catch(() => null);
  const timeout = new Promise((resolve) => setTimeout(resolve, NETWORK_TIMEOUT_MS, "timeout"));
  try {
    const first = await Promise.race([network, timeout]);
    if (first !== "timeout") {
      stored.catch(() => null);
      return first;
    }
    // Weak signal: show the saved copy now; the network answer still refreshes it.
    const saved = await caches.match(request, { cacheName: PAGES });
    if (saved) return saved;
    return await network;
  } catch (error) {
    const saved = await caches.match(request, { cacheName: PAGES });
    return saved || (await caches.match(OFFLINE_URL));
  }
}

async function photo(request) {
  const cache = await caches.open(PHOTOS);
  const saved = await cache.match(request);
  // The app URL is the stable key. With S3 it redirects to a short-lived signed
  // link; the image that comes back (opaque, cross-origin) is kept under the
  // app URL, so the photo still shows offline after the link expires.
  const fresh = fetch(request).then((response) => {
    if (response.ok || response.type === "opaque") {
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
  } else if (/^\/(rabbits\/(photos\/\d+|outside\/\d+\/photo)|litters\/\d+(\/kits\/\d+)?\/photo)\/$/.test(url.pathname)) {
    event.respondWith(photo(request));
  } else if (url.pathname.startsWith("/static/") || url.pathname === "/manifest.webmanifest") {
    event.respondWith(caches.match(request).then((saved) => saved || fetch(request)));
  }
});
{% endautoescape %}
