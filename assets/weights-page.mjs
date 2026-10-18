/*
 * Weights page: inline Log weight saves without a reload (then the table re-renders in
 * place), "select all" for Weigh a group, and one Log popover open at a time.
 * Without JS the Log form posts and the server redirects back to the page.
 */
import { showToast } from "./toast.mjs";

export async function refresh(doc, win) {
  const res = await win.fetch(win.location.href, { headers: { Accept: "text/html" }, credentials: "same-origin" });
  if (!res.ok) throw new Error(String(res.status));
  const fresh = new win.DOMParser().parseFromString(await res.text(), "text/html");
  doc.querySelectorAll("[data-weights-page] [data-swap]").forEach((part) => {
    const repl = fresh.querySelector(`[data-weights-page] [data-swap="${part.dataset.swap}"]`);
    if (repl && part.dataset.swap !== "hidden") part.replaceWith(repl);
  });
}

export function bindWeightsPage(doc, win = window) {
  const root = doc.querySelector("[data-weights-page]");
  if (!root) return;
  // Long weigh-in history: the newest 12 rows, then Show all (without JS every row shows).
  const collapse = () => root.querySelectorAll("[data-weight-history][data-long]").forEach((t) => {
    t.setAttribute("data-collapsed", "");
    const more = t.parentElement.querySelector("[data-history-more]");
    if (more) more.hidden = false;
  });
  root.addEventListener("click", (event) => {
    const more = event.target.closest("[data-history-more]");
    if (!more) return;
    more.parentElement.querySelector("[data-weight-history]")?.removeAttribute("data-collapsed");
    more.hidden = true;
  });
  const showSel = () => { root.querySelector(".wt-li.is-sel")?.scrollIntoView?.({ block: "nearest" }); collapse(); };
  showSel();
  root.addEventListener("list-swap:done", showSel);
  root.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-weight-log]");
    if (!form) return;
    event.preventDefault();
    const err = form.querySelector("[data-weight-log-error]");
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const res = await win.fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value } });
      const data = await res.json();
      if (!data.ok) { err.textContent = data.error; err.hidden = false; return; }
      await refresh(doc, win);
      showToast(doc, data.message, { win });
    } catch {
      form.submit();
    } finally {
      btn.disabled = false;
    }
  });
  // Phone Sort select: a new sort starts in its default direction; keep it in step with header clicks.
  root.addEventListener("change", (event) => {
    if (event.target.matches("[data-sort-select]")) root.querySelector('input[name="dir"]')?.remove();
  }, true);
  root.addEventListener("list-swap:done", () => {
    const select = root.querySelector("[data-sort-select]");
    if (select) select.value = new URL(win.location.href).searchParams.get("sort") || "last";
  });
  root.addEventListener("change", (event) => {
    if (!event.target.matches("[data-select-all]")) return;
    root.querySelectorAll('input[name="ids"]').forEach((box) => { box.checked = event.target.checked; });
  });
  root.addEventListener("toggle", (event) => {
    const panel = event.target;
    if (!panel.matches?.("[data-weight-log-panel]") || !panel.open) return;
    root.querySelectorAll("[data-weight-log-panel][open]").forEach((other) => { if (other !== panel) other.open = false; });
    const fallback = panel.querySelector("[data-weight-log-fallback]");
    const template = doc.querySelector("template[data-weight-log-template]");
    if (fallback && template) {
      const form = template.content.firstElementChild.cloneNode(true);
      form.action = panel.dataset.logAction;
      fallback.replaceWith(form);
    }
    panel.querySelector("input:not([type=hidden])")?.focus();
  }, true);
  doc.addEventListener("pointerdown", (event) => {
    root.querySelectorAll("[data-weight-log-panel][open]").forEach((p) => { if (!p.contains(event.target)) p.open = false; });
  });
}
