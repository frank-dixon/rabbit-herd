/*
 * Remove with undo instead of a confirm prompt. A form marked
 * data-undo-remove hides its row at once and shows a toast; the delete is
 * only sent when the toast times out (or the page is left). Undo puts the
 * row back and nothing is sent. Without JS the form simply posts.
 */
import { showToast } from "./toast.mjs";

export function bindUndoRemove(doc, win = window) {
  const pending = new Set();
  const send = (form) => {
    pending.delete(form);
    win.fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin", keepalive: true }).catch(() => {});
  };
  doc.addEventListener("submit", (event) => {
    const form = event.target.closest?.("form[data-undo-remove]");
    if (!form) return;
    event.preventDefault();
    const row = form.closest("[data-row], li, tr") || form;
    const height = row.getBoundingClientRect().height;
    row.style.overflow = "hidden";
    const anim = row.animate?.([{ opacity: 1, height: `${height}px` }, { opacity: 0, height: "0px", paddingTop: 0, paddingBottom: 0, marginTop: 0, marginBottom: 0 }],
      { duration: 220, easing: "cubic-bezier(0.4, 0, 0.2, 1)", fill: "forwards" });
    pending.add(form);
    let timer;
    const toast = showToast(doc, form.dataset.undoRemove || "Removed.", {
      win,
      undo: () => {
        win.clearTimeout(timer);
        pending.delete(form);
        anim?.reverse();
        anim?.finished.then(() => { anim.cancel(); row.style.overflow = ""; }).catch(() => {});
      },
    });
    timer = win.setTimeout(() => { if (pending.has(form)) send(form); }, 6000);
    toast.addEventListener("animationend", () => { if (!toast.isConnected && pending.has(form)) send(form); });
  });
  win.addEventListener("pagehide", () => { [...pending].forEach(send); });
}
