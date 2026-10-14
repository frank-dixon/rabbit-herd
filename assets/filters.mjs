/*
 * Rabbit list filters: with JS, a change in the filter panel submits at
 * once and the Apply button steps aside. Once the list has swapped in, the
 * panel closes and focus goes back to the Filter button, which now shows the
 * active-filter count. Esc, a tap outside, or a tab or layout change closes it too.
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
  const done = panel.querySelector("[data-filter-done]");
  const close = (focus) => {
    if (!panel.open) return;
    panel.open = false;
    if (focus) panel.querySelector("summary")?.focus();
  };
  if (done) { done.hidden = false; done.addEventListener("click", () => close(true)); }
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.open) close(true);
  });
  root.addEventListener("pointerdown", (event) => {
    if (panel.open && !panel.contains(event.target)) close(false);
  });
  // A tab, layout or chip link chosen by keyboard: no pointerdown, so close here.
  root.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href]");
    if (link && !panel.contains(link)) close(false);
  });
  // A header click sorts the list; keep the panel's Sort select in step with the URL.
  root.addEventListener("list-swap:done", () => syncSort(form, form.ownerDocument?.defaultView?.location?.href));
  root.addEventListener("list-swap:done", (event) => {
    const fromFilters = event.detail?.source === form;
    close(fromFilters && panel.contains(document.activeElement));
    if (fromFilters && !panel.open && document.activeElement === document.body) panel.querySelector("summary")?.focus();
  });
}

/** Set a [data-sort-select] to the URL's ?sort=, adding an option if a header chose one it lacks. */
export function syncSort(form, href) {
  const select = form?.querySelector("[data-sort-select]");
  if (!select || !href) return;
  const value = new URL(href).searchParams.get("sort") || select.options[0]?.value || "";
  if (![...select.options].some((o) => o.value === value)) {
    const option = select.ownerDocument.createElement("option");
    option.value = value;
    option.textContent = value.replace(/^-/, "") + (value.startsWith("-") ? " ↓" : " ↑");
    select.append(option);
  }
  select.value = value;
}
