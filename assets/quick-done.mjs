/*
 * One-tap done on Today: the round check posts in the background, then the
 * row fades and collapses and the counts update. Without JS the form posts
 * and the page reloads.
 */
import { leave } from "./motion.mjs";
import { showToast } from "./toast.mjs";
import { newOpId, queueEntry, savedText } from "./offline.mjs";

const meta = (doc, name) => doc.querySelector(`meta[name="${name}"]`)?.content || "";

export function bindQuickDone(doc, win = window) {
  doc.addEventListener("submit", async (event) => {
    const form = event.target.closest?.("[data-quick-done]");
    if (!form) return;
    event.preventDefault();
    const row = form.closest("li");
    const title = row?.querySelector("[data-task-title], p")?.textContent.trim() || "Task";
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    row?.classList.add("is-done");
    // Offline, the tap is kept on the device and sent once back online (offline.mjs).
    const keep = () => {
      const fields = Array.from(new FormData(form).entries()).filter(([, v]) => typeof v === "string");
      fields.push(["op_id", newOpId(win.crypto)]);
      queueEntry(win.localStorage, form.action, fields, "Task", meta(doc, "bb-user"));
      doc.dispatchEvent(new CustomEvent("bb:queued"));
    };
    let kept = false;
    if (win.navigator && win.navigator.onLine === false) {
      keep();
      kept = true;
    } else {
      try {
        const response = await win.fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin", redirect: "follow" });
        if (!response.ok) throw new Error(String(response.status));
      } catch (error) {
        if (error instanceof TypeError) {
          keep(); // the network dropped mid-tap
          kept = true;
        } else {
          if (button) button.disabled = false;
          row?.classList.remove("is-done");
          return;
        }
      }
    }
    const list = row?.parentElement;
    const next = row?.nextElementSibling || null;
    const copy = row?.cloneNode(true);
    if (row) await leave(row);
    const left = list ? list.querySelectorAll("[data-today-item]").length : 0;
    const count = doc.querySelector("[data-due-count]");
    if (count) count.textContent = String(left);
    if (list && !left) { list.hidden = true; count?.remove(); doc.querySelector("[data-due-empty]")?.removeAttribute("hidden"); }
    doc.querySelectorAll('[data-tab="tasks"] .num').forEach((badge) => {
      const n = Math.max(0, parseInt(badge.textContent, 10) - 1);
      if (n) badge.firstChild.textContent = String(n); else badge.remove();
    });
    if (kept) {
      showToast(doc, savedText("Task"), { win });
      doc.dispatchEvent(new CustomEvent("bb:done", { detail: { form } }));
      return;
    }
    showToast(doc, `Done: ${title}`, {
      win,
      undo: async () => {
        const body = new FormData(form);
        if (body.has("done")) body.set("done", "0");
        await win.fetch(form.action, { method: "POST", body, credentials: "same-origin" }).catch(() => {});
        // Put the row back where it was, without reloading the page.
        if (copy && list) {
          copy.classList.remove("is-done");
          copy.querySelector("button")?.removeAttribute("disabled");
          list.insertBefore(copy, next && next.parentElement === list ? next : null);
          list.hidden = false;
          doc.querySelector("[data-due-empty]")?.setAttribute("hidden", "");
        }
      },
    });
    doc.dispatchEvent(new CustomEvent("bb:done", { detail: { form } }));
  });
}
