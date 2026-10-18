/*
 * Small page actions that used to be inline handlers (kept out of the HTML so
 * the Content-Security-Policy can forbid inline script). Delegated, so pages
 * swapped in without a reload work too.
 */
export function bindPageActions(doc, win) {
  doc.addEventListener("click", (event) => {
    const target = event.target instanceof win.Element ? event.target : null;
    if (!target) return;
    if (target.closest("[data-print-button]")) {
      win.print();
      return;
    }
    const back = target.closest("[data-error-back]");
    if (back && win.history.length > 1 && doc.referrer) {
      try {
        if (new URL(doc.referrer).origin !== win.location.origin) return;
      } catch (e) {
        return;
      }
      event.preventDefault();
      win.history.back();
    }
  });
}
