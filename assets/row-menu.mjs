/*
 * Rows with a "…" row menu (components/row_actions.html) are one big tap target: a tap anywhere
 * on the row that isn't already a control opens its Edit (in the shared modal) or, when there's
 * nothing to edit, the menu itself. Picking an item closes the menu.
 */
const CONTROL = "a, button, summary, input, select, textarea, label, details[data-row-menu], [data-no-row-tap]";

export function rowTarget(row) {
  return row.querySelector("[data-row-open]") || row.querySelector("details[data-row-menu] > summary");
}

export function bindRowMenus(doc) {
  doc.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    const target = event.target;
    if (!target.closest || target.closest(CONTROL)) return;
    if (doc.getSelection && String(doc.getSelection()).length) return; // selecting text, not tapping
    const row = target.closest("[data-row-tap]");
    if (!row) return;
    const open = rowTarget(row);
    if (open) open.click();
  });
  doc.addEventListener("submit", (event) => {
    const menu = event.target.closest?.("details[data-row-menu]");
    if (menu) menu.open = false;
  }, true);
  doc.addEventListener("click", (event) => {
    const item = event.target.closest?.("details[data-row-menu] a[role=menuitem]");
    if (item) item.closest("details").open = false;
  });
}
