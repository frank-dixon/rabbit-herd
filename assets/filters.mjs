/*
 * Rabbit list filters: with JS, a change in the filter panel submits at
 * once and the Apply button steps aside. The panel stays open and its
 * primary button reads "Show N rabbits" with the new count; tapping it closes
 * the panel and focus goes back to the Filter button, which shows the
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
    const count = root.querySelector("[data-result-count]")?.dataset.resultCount;
    if (done && count !== undefined) done.textContent = `Show ${count} rabbit${count === "1" ? "" : "s"}`;
    const reset = panel.querySelector("[data-filter-reset]");
    if (reset) {
      const on = Boolean(root.querySelector(".filter-count"));
      reset.classList.toggle("is-off", !on);
      if (on) { reset.removeAttribute("aria-disabled"); reset.removeAttribute("tabindex"); } else { reset.setAttribute("aria-disabled", "true"); reset.tabIndex = -1; }
    }
    if (fromFilters && panel.open) return;
    close(false);
    if (fromFilters && document.activeElement === document.body) panel.querySelector("summary")?.focus();
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
