/*
 * Settings: one save model. With JS the per-section Save buttons hide; any
 * change shows one sticky bar, and Save posts every changed section, then
 * shows a "Saved" toast. A section with errors falls back to a normal submit,
 * so the server's error page explains it. Without JS each section keeps its
 * own Save button.
 */
import { showToast } from "./toast.mjs";

export function bindSettingsSave(doc, win = window) {
  const forms = [...doc.querySelectorAll("form[data-settings-section][id]")];
  if (!forms.length) return;
  const dirty = new Set();
  const bar = doc.createElement("div");
  bar.className = "save-bar";
  bar.hidden = true;
  bar.setAttribute("role", "region");
  bar.setAttribute("aria-label", "Unsaved changes");
  bar.innerHTML = '<span class="save-bar-text">You have unsaved changes</span><span class="save-bar-actions"><button type="button" class="save-bar-btn" data-save-bar-reset>Discard</button><button type="button" class="save-bar-btn is-primary" data-save-bar-save>Save changes</button></span>';
  doc.body.append(bar);
  const save = bar.querySelector("[data-save-bar-save]");
  forms.forEach((form) => {
    form.querySelectorAll("[data-section-save]").forEach((b) => { b.hidden = true; });
    const mark = () => { dirty.add(form); bar.hidden = false; };
    form.addEventListener("input", mark);
    form.addEventListener("change", mark);
  });
  bar.querySelector("[data-save-bar-reset]").addEventListener("click", () => win.location.reload());
  save.addEventListener("click", async () => {
    save.disabled = true;
    for (const form of [...dirty]) {
      try {
        const response = await win.fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin" });
        const back = new URL(response.url, win.location.href).pathname === win.location.pathname;
        if (!response.ok || !back) throw new Error("not saved");
        dirty.delete(form);
      } catch (error) {
        console.error(error);
        form.submit();
        return;
      }
    }
    save.disabled = false;
    bar.hidden = true;
    showToast(doc, "Saved", { win });
  });
}
