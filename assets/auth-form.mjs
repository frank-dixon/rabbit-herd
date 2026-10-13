/*
 * Signed-out forms (templates/accounts/_auth_*.html). Without JS they are plain forms
 * (server errors show inline). With JS: the password Show/Hide toggle appears, and submitting
 * shows a loading state (spinner, "Signing in…", aria-busy). The button stays enabled until
 * submit; a second submit while busy is ignored. Back/forward restores the idle state.
 */
export function bindAuthForms(root, win = typeof window === "undefined" ? null : window) {
  const forms = [...root.querySelectorAll("[data-auth-form]")];
  forms.forEach((form) => {
    form.querySelectorAll("[data-password-toggle]").forEach((button) => {
      const input = root.getElementById(button.getAttribute("aria-controls"));
      if (!input) return;
      button.hidden = false;
      button.addEventListener("click", () => {
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        button.setAttribute("aria-pressed", String(show));
        button.firstChild.nodeValue = show ? "Hide" : "Show";
      });
    });
    form.addEventListener("submit", (event) => {
      if (form.getAttribute("aria-busy") === "true") { event.preventDefault(); return; }
      setBusy(form, true);
    });
  });
  win?.addEventListener("pageshow", () => forms.forEach((form) => setBusy(form, false)));
}

export function setBusy(form, busy) {
  form.setAttribute("aria-busy", String(busy));
  const button = form.querySelector("[data-busy-label]");
  if (!button) return;
  const label = button.querySelector("[data-submit-label]");
  if (busy) {
    button.dataset.idleLabel = button.dataset.idleLabel || label.textContent;
    label.textContent = button.dataset.busyLabel;
    button.setAttribute("aria-disabled", "true");
    form.querySelectorAll("[data-password]").forEach((input) => { input.type = "password"; });
  } else if (button.dataset.idleLabel) {
    label.textContent = button.dataset.idleLabel;
    button.removeAttribute("aria-disabled");
  }
  const spinner = button.querySelector(".auth-spinner");
  if (spinner) spinner.hidden = !busy;
}
