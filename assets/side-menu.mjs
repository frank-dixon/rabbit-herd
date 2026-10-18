/*
 * Settings > Side menu. Up/Down move the row in place (focus stays on the
 * button), save the whole order with fetch, and reorder the live side menu.
 * Without JS each button posts and the page comes back reordered.
 */
import { startQuiet } from "./view-transitions.mjs";
import { reducedMotion } from "./motion.mjs";

export function moveKey(order, key, way) {
  const next = order.slice();
  const i = next.indexOf(key);
  const j = way === "up" ? i - 1 : i + 1;
  if (i < 0 || j < 0 || j >= next.length) return next;
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

function syncButtons(list) {
  const rows = [...list.children];
  rows.forEach((row, i) => {
    row.querySelector('[data-way="up"]').disabled = i === 0;
    row.querySelector('[data-way="down"]').disabled = i === rows.length - 1;
  });
}

function syncRail(doc, keys) {
  doc.querySelectorAll("[data-app-rail] nav").forEach((nav) => {
    const links = new Map([...nav.querySelectorAll("a[data-rail-key]")].map((a) => [a.dataset.railKey, a]));
    keys.forEach((key) => {
      const link = links.get(key);
      if (!link) return;
      // Links stay within their own group: append after the last sibling of the same group.
      const group = link.dataset.railGroup;
      const last = [...nav.querySelectorAll(`a[data-rail-group="${group}"]`)].pop();
      if (last && last !== link) last.after(link);
    });
  });
}

export function bindSideMenu(doc, win) {
  const form = doc.querySelector("[data-side-menu]");
  if (!form || !win.fetch) return;
  const status = form.querySelector("[data-side-menu-status]");
  form.addEventListener("click", async (event) => {
    const button = event.target.closest?.("button[data-way]");
    if (!button || button.disabled) return;
    event.preventDefault();
    const row = button.closest("[data-side-key]");
    const list = row.parentElement;
    const sibling = button.dataset.way === "up" ? row.previousElementSibling : row.nextElementSibling;
    if (!sibling) return;
    const swap = () => { if (button.dataset.way === "up") sibling.before(row); else sibling.after(row); syncButtons(list); };
    if (doc.startViewTransition && !reducedMotion(win)) await startQuiet(doc, swap).updateCallbackDone; else swap();
    (button.disabled ? row.querySelector("button:not([disabled])") : button)?.focus();
    const keys = [...form.querySelectorAll("[data-side-key]")].map((li) => li.dataset.sideKey);
    syncRail(doc, keys);
    const body = new FormData();
    body.append("csrfmiddlewaretoken", form.querySelector("[name=csrfmiddlewaretoken]").value);
    keys.forEach((key) => body.append("order", key));
    try {
      const res = await win.fetch(form.action, { method: "POST", body, headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
      if (status) status.textContent = res.ok ? "Saved" : "Couldn't save. Try again.";
    } catch {
      if (status) status.textContent = "Couldn't save. Try again.";
    }
  });
}
