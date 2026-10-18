/*
 * Settings: one save model, autosave. Every settings section saves as it changes and says "Saved"
 * next to its heading (appearance and the side menu do the same in settings.mjs and
 * side-menu.mjs). Text fields save when you leave them or press Enter. A herd section the server
 * rejects falls back to a normal submit, so its error page explains why. The bottom bar shows the
 * server's reason instead (for example a tab picked twice) and saves once the picks are valid,
 * then refreshes the bar on the page. Without JS each section keeps its own Save button.
 */
export const SAVED = "Saved";

export function bindSettingsSave(doc, win = window) {
  const forms = [...doc.querySelectorAll("form[data-settings-section][id], form[data-autosave]")];
  forms.forEach((form) => {
    form.querySelectorAll("[data-section-save]").forEach((el) => { el.hidden = true; });
    const say = (text) => { const status = form.querySelector("[data-autosave-status]"); if (status) status.textContent = text; };
    const tabs = form.getAttribute("data-autosave") === "tabs";
    let timer = 0;
    async function save(submitter) {
      const body = new win.FormData(form, submitter || undefined);
      try {
        const response = await win.fetch(form.action, {
          method: "POST", body, credentials: "same-origin",
          headers: tabs ? { "X-Requested-With": "fetch" } : {},
        });
        if (tabs) {
          const data = await response.json().catch(() => ({}));
          if (!response.ok || !data.ok) { say("Pick 3 to 5 different tabs."); return; }
          await refreshTabs(doc, win, submitter ? form : null);
        } else if (!response.ok || new URL(response.url, win.location.href).pathname !== win.location.pathname) {
          form.submit();
          return;
        }
        say(SAVED);
      } catch (error) {
        win.console?.error?.(error);
        form.submit();
      }
    }
    form.addEventListener("change", () => {
      say("");
      win.clearTimeout(timer);
      timer = win.setTimeout(() => save(), 250);
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      win.clearTimeout(timer);
      save(event.submitter && event.submitter.name ? event.submitter : null);
    });
  });
}

/** Swap in the saved bottom bar (and, after Reset, the form's picks) without reloading. */
async function refreshTabs(doc, win, form) {
  const bar = doc.querySelector("[data-app-tabs]");
  if (!bar && !form) return;
  const response = await win.fetch(win.location.pathname, { credentials: "same-origin" });
  const page = new win.DOMParser().parseFromString(await response.text(), "text/html");
  const fresh = page.querySelector("[data-app-tabs]");
  if (bar && fresh) bar.innerHTML = fresh.innerHTML;
  const freshForm = form && page.querySelector(`form#${form.id}`);
  if (freshForm) {
    form.innerHTML = freshForm.innerHTML;
    form.querySelectorAll("[data-section-save]").forEach((el) => { el.hidden = true; });
  }
}
