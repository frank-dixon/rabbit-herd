/*
 * Add sheets: a page's "New …" header button opens the add form in place
 * instead of reloading with ?new=1. The form sits in a <details data-add-sheet>
 * that the server opens on ?new=1, on errors and when editing, so it all works
 * without JavaScript. Cancel closes it again. Motion uses enter(), which
 * reduced motion makes instant.
 */
import { enter, focusSmooth } from "./motion.mjs";

export function sheetFor(doc, href) {
  const hash = (href || "").split("#")[1];
  if (!hash || (href || "").indexOf("new=1") === -1) return null;
  const el = doc.getElementById(hash);
  return el && el.hasAttribute("data-add-sheet") ? el : null;
}

export function bindAddSheets(doc) {
  doc.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey) return;
    const link = event.target.closest && event.target.closest("a[href]");
    if (!link || link.hasAttribute("data-modal") || link.closest("dialog[data-modal]")) return; // the shared modal handles these
    if (link.hasAttribute("data-sheet-close")) {
      const sheet = link.closest("[data-add-sheet]");
      if (sheet && !sheet.querySelector("[aria-invalid=true]") && link.getAttribute("href") === doc.location.pathname) {
        event.preventDefault();
        sheet.open = false;
        const opener = doc.querySelector(`a[href$="#${sheet.id}"]`);
        if (opener) opener.focus();
      }
      return;
    }
    const sheet = sheetFor(doc, link.getAttribute("href"));
    if (!sheet) return;
    event.preventDefault();
    if (sheet.open) {
      sheet.open = false;
      return;
    }
    sheet.open = true;
    enter(sheet.querySelector("section") || sheet);
    const field = sheet.querySelector("input:not([type=hidden]), select, textarea");
    if (field) focusSmooth(field);
  });
}

/** "…" menus (<details data-more-menu>): close on outside click and on Esc. */
export function bindMoreMenus(doc) {
  doc.addEventListener("click", (event) => {
    doc.querySelectorAll("details[data-more-menu][open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  doc.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    doc.querySelectorAll("details[data-more-menu][open]").forEach((menu) => {
      menu.open = false;
      const summary = menu.querySelector("summary");
      if (summary) summary.focus();
    });
  });
}
