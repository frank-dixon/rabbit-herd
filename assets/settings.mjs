/*
 * Settings: choosing a theme or density previews it at once and saves it in
 * the background. Guests keep the choice in localStorage (and still POST so
 * the guest row matches while the session is live). Without JS the form's
 * Save button posts the same fields.
 */
const THEME_KEY = "bb-ui-theme";
const DENSITY_KEY = "bb-ui-density";

function isGuest(html) {
  return html?.getAttribute("data-guest") === "1";
}

function storeGuest(html, name, value) {
  if (!isGuest(html)) return;
  try {
    if (name === "ui_theme") localStorage.setItem(THEME_KEY, value);
    if (name === "ui_density") localStorage.setItem(DENSITY_KEY, value);
  } catch (_) { /* private mode */ }
}

export function bindSettings(root, win = window) {
  const form = root.querySelector("[data-appearance-form]");
  if (!form) return;
  const html = root.documentElement || root.ownerDocument?.documentElement;
  const status = form.querySelector("[data-appearance-status]");
  const save = form.querySelector("[data-appearance-save]");
  if (save) save.hidden = true;
  form.addEventListener("change", async (event) => {
    const input = event.target;
    if (input.name === "ui_theme") {
      html.dataset.theme = input.value;
      storeGuest(html, "ui_theme", input.value);
      const meta = root.querySelector('meta[name="theme-color"]');
      const swatch = input.closest("label")?.querySelector("[data-theme-canvas]");
      if (meta && swatch) meta.setAttribute("content", swatch.getAttribute("data-theme-canvas") || meta.getAttribute("content"));
    }
    if (input.name === "ui_density") {
      html.dataset.density = input.value;
      storeGuest(html, "ui_density", input.value);
    }
    if (input.name === "ui_mark") {
      const pick = input.closest("label")?.querySelector(".app-mark");
      if (pick) for (const m of root.querySelectorAll(".app-mark")) if (!form.contains(m)) { m.setAttribute("viewBox", pick.getAttribute("viewBox")); m.innerHTML = pick.innerHTML; }
    }
    try {
      const response = await win.fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(String(response.status));
      if (status) status.textContent = "Saved";
    } catch {
      if (save) save.hidden = false;
      if (status) status.textContent = "Not saved. Use Save to try again.";
    }
  });
}
