/*
 * Settings: choosing a mode, theme or density previews it at once and saves it in
 * the background. Without JS the form's Save button posts the same fields.
 */
export function bindSettings(root, win = window) {
  const form = root.querySelector("[data-appearance-form]");
  if (!form) return;
  const html = root.documentElement || root.ownerDocument?.documentElement;
  const status = form.querySelector("[data-appearance-status]");
  const save = form.querySelector("[data-appearance-save]");
  if (save) save.hidden = true;
  form.addEventListener("change", async (event) => {
    const input = event.target;
    if (input.name === "ui_theme") html.dataset.theme = input.value;
    if (input.name === "ui_density") html.dataset.density = input.value;
    if (input.name === "ui_mode") html.dataset.mode = input.value;
    if (input.name === "ui_density") html.dataset.density = input.value;
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
