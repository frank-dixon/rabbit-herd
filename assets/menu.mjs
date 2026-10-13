/*
 * Menu panel. The button is a link to /menu/ so it works without JS; with JS
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
  panel.querySelector("[data-menu-close]")?.addEventListener("click", () => close());
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
    if (event.target.closest("a[href]")) close({ restoreFocus: false });
  });
  return { open, close, isOpen };
}
