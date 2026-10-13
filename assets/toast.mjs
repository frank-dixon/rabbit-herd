/*
 * Toasts. Server messages arrive in [data-toasts]; showToast() adds new ones
 * from script. Each fades out after a few seconds (longer with an Undo),
 * pausing while hovered or focused. Undo either posts its form or runs a
 * callback.
 */
const LIFE_MS = 4000;
const UNDO_MS = 6000;

function region(doc) {
  let el = doc.querySelector("[data-toasts]");
  if (!el) {
    el = doc.createElement("div");
    el.className = "toasts";
    el.setAttribute("data-toasts", "");
    el.setAttribute("aria-live", "polite");
    doc.body.append(el);
  }
  return el;
}

function dismiss(toast) {
  if (toast.classList.contains("is-leaving")) return;
  toast.classList.add("is-leaving");
  const ms = parseFloat(getComputedStyle(toast).animationDuration) * 1000 || 0;
  setTimeout(() => toast.remove(), ms + 30);
}

function arm(toast, win) {
  const close = toast.querySelector("[data-toast-close]");
  if (close) { close.hidden = false; close.addEventListener("click", () => dismiss(toast)); }
  let left = toast.querySelector("[data-toast-undo], [data-undo]") ? UNDO_MS : LIFE_MS;
  let started = Date.now();
  let timer = win.setTimeout(() => dismiss(toast), left);
  const pause = () => { win.clearTimeout(timer); left -= Date.now() - started; };
  const resume = () => { started = Date.now(); timer = win.setTimeout(() => dismiss(toast), Math.max(left, 1200)); };
  toast.addEventListener("pointerenter", pause);
  toast.addEventListener("pointerleave", resume);
  toast.addEventListener("focusin", pause);
  toast.addEventListener("focusout", resume);
}

export function showToast(doc, text, { undo, win = window } = {}) {
  const toast = doc.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "status");
  toast.setAttribute("data-toast", "");
  const label = doc.createElement("span");
  label.className = "min-w-0 flex-1";
  label.textContent = text;
  toast.append(label);
  if (undo) {
    const button = doc.createElement("button");
    button.type = "button";
    button.className = "toast-action";
    button.textContent = "Undo";
    button.setAttribute("data-undo", "");
    button.addEventListener("click", () => { dismiss(toast); undo(); });
    toast.append(button);
  }
  const close = doc.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("data-toast-close", "");
  close.innerHTML = '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg><span class="sr-only">Dismiss</span>';
  toast.append(close);
  const box = region(doc);
  box.querySelectorAll("[data-toast]").forEach((old) => dismiss(old));
  box.append(toast);
  arm(toast, win);
  return toast;
}

export function bindToasts(doc, win = window) {
  doc.querySelectorAll("[data-toasts] [data-toast]").forEach((toast) => arm(toast, win));
}
