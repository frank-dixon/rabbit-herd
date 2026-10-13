/*
 * Rabbit list filters: with JS, a change in the filter panel submits at
 * once and the Apply button steps aside. Esc or a tap outside closes it.
 */
export function bindFilters(root) {
  const form = root.querySelector("[data-filter-form]");
  if (!form) return;
  const panel = form.querySelector("[data-filter-panel]");
  const apply = form.querySelector("[data-filter-apply]");
  if (apply) apply.classList.add("sr-only");
  form.querySelectorAll("[data-filter-panel] select").forEach((select) => {
    select.addEventListener("change", () => form.requestSubmit());
  });
  if (!panel) return;
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.open) { panel.open = false; panel.querySelector("summary").focus(); }
  });
  root.addEventListener("pointerdown", (event) => {
    if (panel.open && !panel.contains(event.target)) panel.open = false;
  });
}
