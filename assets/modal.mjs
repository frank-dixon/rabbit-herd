/*
 * The shared modal. A link marked data-modal opens its page inside the <dialog>
 * instead of navigating; links inside that point at edit pages stay inside.
 * Forms post with fetch (redirects followed). When the answer is the page
 * underneath, the change is saved: the [data-refresh] regions are swapped in
 * place, the server's message shows as a toast, and the modal closes. Any other
 * answer (the next card, or the same card with server-side errors) renders in
 * the modal. Without JavaScript the links simply open the pages.
 */
import { reducedMotion } from "./motion.mjs";
import { showToast } from "./toast.mjs";
import { bindRabbitFlow } from "./rabbit-flow.mjs";

const EDIT_PATH = /^\/rabbits\/\d+\/(edit|change|genes|status)\b|^\/relatives\/\d+\/add-to-herd\/|^\/costs\/(new|\d+\/edit)\//;

export function staysInModal(url, base) {
  const target = new URL(url, base);
  return target.origin === new URL(base).origin && EDIT_PATH.test(target.pathname);
}

/** The part of a fetched page to show: [data-modal-content] if marked, else <main> without its header. */
export function modalContent(page) {
  const main = page.querySelector("[data-modal-content]") || page.querySelector("main");
  if (!main) return { title: "", nodes: [] };
  const heading = main.querySelector("h1") || (main.hasAttribute("data-modal-content") ? main.querySelector("h2") : null);
  const title = (heading?.textContent || page.title || "").trim();
  if (heading && heading.tagName === "H2") heading.remove(); // the modal header shows it
  main.querySelectorAll("[data-page-header], [data-toasts], [data-connection-status], dialog").forEach((el) => el.remove());
  return { title, nodes: Array.from(main.childNodes) };
}

/** Prefix ids (and the for/aria refs that point at them) so a form copied from the page underneath doesn't clash with it. */
export function prefixIds(root, prefix = "m-") {
  const ids = new Set(Array.from(root.querySelectorAll("[id]"), (el) => el.id));
  if (!ids.size) return;
  root.querySelectorAll("[id]").forEach((el) => { el.id = prefix + el.id; });
  root.querySelectorAll("[for], [aria-describedby], [aria-labelledby], [aria-controls]").forEach((el) => {
    for (const attr of ["for", "aria-describedby", "aria-labelledby", "aria-controls"]) {
      const value = el.getAttribute(attr);
      if (value) el.setAttribute(attr, value.split(/\s+/).map((id) => (ids.has(id) ? prefix + id : id)).join(" "));
    }
  });
}

export function bindModal(doc, win = window) {
  const dialog = doc.querySelector("dialog[data-modal]");
  if (!dialog || typeof dialog.showModal !== "function") return;
  const body = dialog.querySelector("[data-modal-body]");
  const title = dialog.querySelector("[data-modal-title]");
  let opener = null;
  let busy = false;
  const parser = new win.DOMParser();

  function close() {
    if (!dialog.open) return;
    const done = () => { dialog.removeAttribute("data-closing"); dialog.close(); body.replaceChildren(); if (opener) opener.focus({ preventScroll: true }); };
    if (reducedMotion(win)) { done(); return; }
    dialog.setAttribute("data-closing", "");
    win.setTimeout(done, 150);
  }

  function refresh(page) {
    doc.querySelectorAll("[data-refresh]").forEach((region) => {
      const fresh = page.querySelector(`[data-refresh="${region.getAttribute("data-refresh")}"]`);
      if (fresh) region.innerHTML = fresh.innerHTML;
    });
  }

  async function load(url, init) {
    if (busy) return;
    busy = true;
    dialog.setAttribute("aria-busy", "true");
    try {
      const response = await win.fetch(url, { credentials: "same-origin", headers: { "X-Modal": "1" }, ...init });
      const page = parser.parseFromString(await response.text(), "text/html");
      const landed = new URL(response.url || url, win.location.href);
      if (landed.pathname === win.location.pathname && init && init.method === "POST" && response.ok && response.redirected !== false) {
        refresh(page);
        const message = page.querySelector("[data-toasts] [data-toast] span, [data-toasts] [data-toast]")?.textContent?.trim();
        close();
        showToast(doc, message || "Saved.", { win });
        return;
      }
      if (!staysInModal(landed.href, win.location.href) && landed.pathname !== new URL(url, win.location.href).pathname) {
        win.location.assign(landed.href);
        return;
      }
      const { title: heading, nodes } = modalContent(page);
      title.textContent = heading;
      body.replaceChildren(...nodes.map((node) => doc.importNode(node, true)));
      if (body.querySelector("[data-add-sheet-body]")) prefixIds(body);
      body.dataset.url = landed.href;
      bindRabbitFlow(body);
      if (!dialog.open) dialog.showModal();
      const target = body.querySelector("[aria-invalid=true], .border-red-800 input, input:not([type=hidden]), select, textarea, button");
      if (target) target.focus({ preventScroll: true });
      body.scrollTop = 0;
    } catch (error) {
      win.location.assign(url);
    } finally {
      busy = false;
      dialog.removeAttribute("aria-busy");
    }
  }

  doc.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest && event.target.closest("a[href]");
    if (!link) return;
    const inside = dialog.contains(link);
    if (!inside && !link.hasAttribute("data-modal")) return;
    if (inside && new URL(link.href, win.location.href).pathname === win.location.pathname && !new URL(link.href, win.location.href).hash) {
      event.preventDefault(); // Cancel / back to the page underneath: just close
      close();
      return;
    }
    if (inside && !staysInModal(link.href, win.location.href)) return;
    event.preventDefault();
    if (!inside) opener = link;
    load(link.href);
  });
  body.addEventListener("submit", (event) => {
    const form = event.target;
    if ((form.method || "get").toLowerCase() !== "post") return;
    event.preventDefault();
    const data = new win.FormData(form, event.submitter || undefined);
    load(form.getAttribute("action") ? form.action : body.dataset.url, { method: "POST", body: data });
  });
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); close(); });
  dialog.addEventListener("click", (event) => { if (event.target === dialog) close(); });
  dialog.querySelector("[data-modal-close]").addEventListener("click", close);
}
