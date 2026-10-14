/*
 * Menu panel. The button links to #app-menu, which opens it with :target without JS; with JS
 * it opens the slide-in panel instead. The page behind is made inert while
 * it is open (which also keeps focus inside the panel); Esc, the close
 * button or a tap on the scrim closes it and focus returns to the button.
 */
export function bindMenu(doc, win = window) {
  const button = doc.querySelector("[data-menu-button]");
  const panel = doc.querySelector("[data-menu-panel]");
  const shell = doc.querySelector("[data-shell]");
  const scrim = doc.querySelector("[data-menu-scrim]");
  if (!button || !panel || !shell) return null;
  const html = doc.documentElement;
  panel.inert = true;

  function isOpen() { return html.hasAttribute("data-menu-open"); }

  function open() {
    if (isOpen()) return;
    html.setAttribute("data-menu-open", "");
    panel.inert = false;
    shell.inert = true;
    button.setAttribute("aria-expanded", "true");
    const first = panel.querySelector("[aria-current] , a, button");
    win.requestAnimationFrame(() => (first || panel).focus({ preventScroll: true }));
  }

  function close({ restoreFocus = true } = {}) {
    if (!isOpen()) return;
    html.removeAttribute("data-menu-open");
    panel.inert = true;
    shell.inert = false;
    button.setAttribute("aria-expanded", "false");
    if (restoreFocus) button.focus({ preventScroll: true });
  }

  button.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    isOpen() ? close() : open();
  });
  panel.querySelector("[data-menu-close]")?.addEventListener("click", (event) => { event.preventDefault(); close(); });
  scrim?.addEventListener("click", () => close());
  doc.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) { event.preventDefault(); close(); }
  });
  // Keep Tab inside the panel even where inert is not supported.
  panel.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const items = [...panel.querySelectorAll("a[href], button:not([disabled])")];
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && doc.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && doc.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  panel.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link || event.target.closest("[data-account-button], [data-menu-close]")) return;
    // With cross-document view transitions the menu stays open until the next
    // page is ready, then slides out as part of the page change (motion.css).
    if (slidesOutWithPage(win, link, event)) return;
    close({ restoreFocus: false });
  });
  // Back/Forward from the cache can bring the page back with the menu open.
  win.addEventListener("pageshow", (event) => { if (event.persisted) close({ restoreFocus: false }); });
  return { open, close, isOpen };
}

/** True when this click becomes a cross-document navigation with a view transition. */
export function slidesOutWithPage(win, link, event = {}) {
  if (!("onpagereveal" in win) || win.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return false;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target || link.hasAttribute("download")) return false;
  let url;
  try { url = new URL(link.href, win.location.href); } catch { return false; }
  const here = new URL(win.location.href);
  if (url.origin !== here.origin) return false;
  // A same-page hash jump doesn't load a new page, so close it now.
  return !(url.pathname === here.pathname && url.search === here.search);
}
