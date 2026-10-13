/*
 * Pull to refresh on Today and the list pages, for touch screens only.
 * Pull down from the top of the page past the threshold and let go to reload.
 * Offline, letting go says so instead of reloading into an error.
 */
import { showToast } from "./toast.mjs";

export const THRESHOLD = 72;
export const MAX_PULL = 120;

/** Finger travel to indicator travel: 1:1 at first, then resisting. */
export function pullDistance(dy) {
  if (dy <= 0) return 0;
  const eased = dy < THRESHOLD ? dy * 0.6 : THRESHOLD * 0.6 + (dy - THRESHOLD) * 0.25;
  return Math.min(MAX_PULL, Math.round(eased));
}

export function bindPullRefresh(doc, win = window) {
  if (!doc.querySelector("[data-refreshable]")) return;
  if (!win.matchMedia?.("(pointer: coarse)").matches) return;
  const ind = doc.createElement("div");
  ind.className = "ptr";
  ind.setAttribute("aria-hidden", "true");
  ind.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v4h-4"/></svg>';
  doc.body.append(ind);
  let startY = null, startX = 0, dy = 0, locked = false;
  const set = (d) => {
    ind.style.setProperty("--pull", `${d}px`);
    ind.classList.toggle("is-armed", dy >= THRESHOLD);
  };
  doc.addEventListener("touchstart", (e) => {
    if (win.scrollY > 0 || e.touches.length > 1 || doc.documentElement.classList.contains("panel-open") || e.target.closest("dialog, input, textarea, select, [data-keypad]")) { startY = null; return; }
    startY = e.touches[0].clientY; startX = e.touches[0].clientX; dy = 0; locked = false;
    ind.classList.add("is-pulling");
  }, { passive: true });
  doc.addEventListener("touchmove", (e) => {
    if (startY === null) return;
    dy = e.touches[0].clientY - startY;
    const dx = Math.abs(e.touches[0].clientX - startX);
    if (!locked && (dx > 8 || Math.abs(dy) > 8)) {
      locked = true;
      if (dx > Math.abs(dy)) { startY = null; ind.classList.remove("is-pulling"); set(0); return; }
    }
    if (dy <= 0 || win.scrollY > 0) { set(0); return; }
    set(pullDistance(dy));
  }, { passive: true });
  const end = () => {
    if (startY === null) return;
    startY = null;
    ind.classList.remove("is-pulling");
    if (dy >= THRESHOLD) {
      if (!win.navigator.onLine) { set(0); showToast(doc, "You're offline. Pull again once you're back online.", { win }); return; }
      ind.classList.add("is-loading");
      set(THRESHOLD * 0.6);
      win.location.reload();
    } else set(0);
    dy = 0;
  };
  doc.addEventListener("touchend", end);
  doc.addEventListener("touchcancel", end);
}
