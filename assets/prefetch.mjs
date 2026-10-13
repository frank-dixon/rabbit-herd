/*
 * Prefetch a page when the pointer rests on its link or a finger lands on
 * it, so the tap opens instantly. Uses speculation rules where supported and
 * <link rel=prefetch> elsewhere. Sends Sec-Purpose: prefetch, which the
 * server uses to leave one-time messages unread.
 */
const SKIP = /^\/(accounts|admin|sw\.js|manifest|offline|export)|\/photos\/\d+\/$|logout|undo|start-over|restart|\.(csv|pdf|zip)$|\/delete\/?$/;
const HOVER_MS = 65;

export function prefetchable(a, loc) {
  if (!a || !a.href || a.target || a.hasAttribute("download") || a.closest("[data-no-prefetch]")) return null;
  let url;
  try { url = new URL(a.href, loc.href); } catch { return null; }
  if (url.origin !== loc.origin || !/^https?:$/.test(url.protocol)) return null;
  if (url.pathname === loc.pathname && url.search === loc.search) return null;
  if (SKIP.test(url.pathname)) return null;
  url.hash = "";
  return url.href;
}

export function bindPrefetch(doc, win = window) {
  const conn = win.navigator.connection;
  if (conn && (conn.saveData || /(^|-)2g$/.test(conn.effectiveType || ""))) return;
  const done = new Set();
  const spec = win.HTMLScriptElement?.supports?.("speculationrules");
  const go = (href) => {
    if (!href || done.has(href) || done.size > 40) return;
    done.add(href);
    if (spec) {
      const s = doc.createElement("script");
      s.type = "speculationrules";
      s.textContent = JSON.stringify({ prefetch: [{ source: "list", urls: [href] }] });
      doc.head.append(s);
    } else {
      const l = doc.createElement("link");
      l.rel = "prefetch"; l.href = href; l.as = "document";
      doc.head.append(l);
    }
  };
  let timer = 0;
  doc.addEventListener("pointerover", (e) => {
    if (e.pointerType !== "mouse") return;
    const href = prefetchable(e.target.closest?.("a"), win.location);
    if (!href) return;
    clearTimeout(timer);
    timer = setTimeout(() => go(href), HOVER_MS);
  });
  doc.addEventListener("pointerout", () => clearTimeout(timer));
  doc.addEventListener("touchstart", (e) => go(prefetchable(e.target.closest?.("a"), win.location)), { passive: true });
  doc.addEventListener("focusin", (e) => go(prefetchable(e.target.closest?.("a"), win.location)));
}
