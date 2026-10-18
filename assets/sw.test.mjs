// Runs the service worker template in a fake worker scope.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function load() {
  let src = readFileSync(new URL("../templates/pwa/sw.js", import.meta.url), "utf8");
  src = src.replace(/\{%[^%]*%\}/g, "").replace(/\{\{[^}]*\}\}/g, "t");
  const listeners = {};
  const stores = new Map();
  const cacheFor = (name) => {
    if (!stores.has(name)) stores.set(name, new Map());
    const m = stores.get(name);
    return {
      match: async (r) => m.get(typeof r === "string" ? r : r.url),
      put: async (r, res) => { m.set(typeof r === "string" ? r : r.url, res); },
      delete: async (r) => m.delete(typeof r === "string" ? r : r.url),
      keys: async () => [...m.keys()].map((url) => ({ url })),
      addAll: async () => {},
    };
  };
  const caches = {
    open: async (n) => cacheFor(n),
    delete: async (n) => stores.delete(n),
    keys: async () => [...stores.keys()],
    match: async (r, opts = {}) => {
      const names = opts.cacheName ? [opts.cacheName] : [...stores.keys()];
      for (const n of names) { const hit = await cacheFor(n).match(r); if (hit) return hit; }
      return undefined;
    },
  };
  const scope = { location: { origin: "https://x.test" }, addEventListener: (t, f) => { listeners[t] = f; }, clients: { claim() {} }, skipWaiting() {} };
  const env = { self: scope, caches, fetch: null };
  new Function("self", "caches", "env", `const fetch = (...a) => env.fetch(...a);\n${src}`)(scope, caches, env);
  return { listeners, caches, stores, env };
}

function html(body, extra = {}) {
  return { ok: true, redirected: false, url: "https://x.test/", headers: { get: () => "text/html" }, body, clone() { return this; }, ...extra };
}

function navigate(sw, path) {
  let responded;
  sw.listeners.fetch({ request: { url: "https://x.test" + path, method: "GET", mode: "navigate" }, respondWith: (p) => { responded = p; } });
  return responded;
}

test("sign-in, signup and admin pages are never handled", () => {
  const sw = load();
  for (const path of ["/login/", "/signup/", "/logout/", "/admin/", "/accounts/guest/"]) {
    assert.equal(navigate(sw, path), undefined, path);
  }
});

test("a slow network falls back to the saved copy after the timeout", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const sw = load();
  sw.env.fetch = async () => html("fresh");
  assert.equal((await navigate(sw, "/rabbits/")).body, "fresh");
  await new Promise((r) => setImmediate(r));
  sw.env.fetch = () => new Promise(() => {});  // lie-fi: never answers
  const pending = navigate(sw, "/rabbits/");
  await new Promise((r) => setImmediate(r));
  t.mock.timers.tick(3000);
  assert.equal((await pending).body, "fresh");
});

test("being sent to sign-in clears saved private pages", async () => {
  const sw = load();
  sw.env.fetch = async () => html("herd");
  await navigate(sw, "/rabbits/");
  await new Promise((r) => setImmediate(r));
  assert.ok([...sw.stores.keys()].some((k) => k.startsWith("bb-pages-")));
  sw.env.fetch = async () => html("login", { redirected: true, url: "https://x.test/login/?next=/rabbits/" });
  await navigate(sw, "/rabbits/");
  await new Promise((r) => setImmediate(r));
  assert.ok(![...sw.stores.keys()].some((k) => k.startsWith("bb-pages-")));
});
