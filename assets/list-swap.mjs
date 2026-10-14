/*
 * No-reload list pages. Inside [data-swap-root], links that only change the query string
 * (status tabs, Grid/List, Roomy/Compact, filter chips, sorts) and GET filter forms fetch
 * the page and swap only the parts marked [data-swap="key"]; the URL follows with
 * history.pushState and Back/Forward swap again. The server saves the view preference
 * on that same GET, so a fetched Grid/List click persists it. Without JS every control is
 * a plain link or form. Any fetch failure falls back to a normal navigation.
 */
import { bindSegmented, place } from "./segmented.mjs";
import { reducedMotion } from "./motion.mjs";

/** A link we handle: same origin and path, only the query differs, plain left click. */
export function swappable(href, here, event = {}, target = "") {
  if (event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || target) return false;
  let url;
  try { url = new URL(href, here); } catch { return false; }
  const cur = new URL(here);
  return url.origin === cur.origin && url.pathname === cur.pathname && url.search !== cur.search;
}

/** URL for a GET form submit, dropping empty fields so the address stays tidy. */
export function formUrl(action, entries) {
  const url = new URL(action);
  url.search = "";
  for (const [k, v] of entries) if (typeof v === "string" && v !== "") url.searchParams.append(k, v);
  return url;
}

function syncGroup(group, fresh) {
  const mine = group.querySelectorAll("[data-seg-option]");
  const theirs = fresh.querySelectorAll("[data-seg-option]");
  if (mine.length !== theirs.length) return;
  mine.forEach((el, i) => {
    const src = theirs[i];
    if (src.hasAttribute("href")) el.setAttribute("href", src.getAttribute("href"));
    el.toggleAttribute("data-selected", src.hasAttribute("data-selected"));
    const cur = src.getAttribute("aria-current");
    if (cur) el.setAttribute("aria-current", cur); else el.removeAttribute("aria-current");
    el.className = src.className;
    el.innerHTML = src.innerHTML; // counts
  });
  place(group);
}

export function bindListSwap(doc, win) {
  const root = doc.querySelector("[data-swap-root]");
  if (!root || !win?.fetch || !win.history?.pushState || !win.DOMParser) return;
  let pending = null;

  const apply = (fresh) => {
    const next = fresh.querySelector("[data-swap-root]");
    if (!next) return false;
    root.querySelectorAll(":scope [data-swap]").forEach((part) => {
      const repl = next.querySelector(`[data-swap="${part.dataset.swap}"]`);
      if (repl) { part.replaceWith(repl); bindSegmented(repl, win); }
    });
    const keep = [...root.querySelectorAll("[data-swap-sync]")];
    const theirs = [...next.querySelectorAll("[data-swap-sync]")];
    keep.forEach((g, i) => theirs[i] && syncGroup(g, theirs[i]));
    doc.title = fresh.title || doc.title;
    return true;
  };

  async function go(url, push, source = null) {
    pending?.abort();
    const ctl = new AbortController();
    pending = ctl;
    const results = root.querySelector('[data-swap="results"]');
    results?.setAttribute("aria-busy", "true");
    try {
      const res = await win.fetch(url, { signal: ctl.signal, headers: { Accept: "text/html" }, credentials: "same-origin" });
      if (!res.ok || res.redirected) throw new Error(String(res.status));
      const fresh = new win.DOMParser().parseFromString(await res.text(), "text/html");
      if (ctl.signal.aborted) return;
      const run = () => { if (!apply(fresh)) throw new Error("no region"); };
      if (push) win.history.pushState({ listSwap: true }, "", url);
      if (doc.startViewTransition && !reducedMotion(win)) await doc.startViewTransition(run).updateCallbackDone;
      else run();
      root.dispatchEvent(new win.CustomEvent("list-swap:done", { bubbles: true, detail: { source } }));
    } catch (error) {
      if (error?.name === "AbortError") return;
      win.location.assign(url);
    } finally {
      if (pending === ctl) pending = null;
      root.querySelector('[data-swap="results"]')?.removeAttribute("aria-busy");
    }
  }

  root.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href]");
    if (!link || event.defaultPrevented || link.hasAttribute("download")) return;
    if (!swappable(link.href, win.location.href, event, link.target)) return;
    event.preventDefault();
    go(link.href, true, link);
  });
  root.addEventListener("submit", (event) => {
    const form = event.target;
    if ((form.method || "get").toLowerCase() !== "get" || event.defaultPrevented) return;
    event.preventDefault();
    go(formUrl(form.action || win.location.href, new FormData(form, event.submitter)).href, true, form);
  });
  win.history.replaceState({ listSwap: true }, "");
  win.addEventListener("popstate", (event) => { if (event.state?.listSwap) go(win.location.href, false); });
}
