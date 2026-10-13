/*
 * One-tap done on Today: the round check posts in the background, then the
 * row fades and collapses and the counts update. Without JS the form posts
 * and the page reloads.
 */
import { leave } from "./motion.mjs";

export function bindQuickDone(doc, win = window) {
  doc.addEventListener("submit", async (event) => {
    const form = event.target.closest?.("[data-quick-done]");
    if (!form) return;
    event.preventDefault();
    const row = form.closest("li");
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    row?.classList.add("is-done");
    try {
      const response = await win.fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin", redirect: "follow" });
      if (!response.ok) throw new Error(String(response.status));
    } catch {
      if (button) button.disabled = false;
      row?.classList.remove("is-done");
      return;
    }
    const list = row?.parentElement;
    if (row) await leave(row);
    const left = list ? list.querySelectorAll("[data-today-item]").length : 0;
    const count = doc.querySelector("[data-due-count]");
    if (count) count.textContent = String(left);
    if (list && !left) { list.hidden = true; count?.remove(); doc.querySelector("[data-due-empty]")?.removeAttribute("hidden"); }
    doc.querySelectorAll('[data-tab="tasks"] .num').forEach((badge) => {
      const n = Math.max(0, parseInt(badge.textContent, 10) - 1);
      if (n) badge.firstChild.textContent = String(n); else badge.remove();
    });
    doc.dispatchEvent(new CustomEvent("bb:done", { detail: { form } }));
  });
}
