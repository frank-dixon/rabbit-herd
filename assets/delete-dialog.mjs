/*
 * Delete-a-rabbit dialog. The Delete link goes to a confirm page without
 * script; with script it opens a native <dialog> instead. showModal() makes
 * the rest of the page inert (a real focus trap) and Esc closes it.
 * With a typed phrase (removing for good), the confirm button stays disabled
 * until the text matches; the server checks it again. Without one (moving to
 * Recently deleted) it is a plain confirm and Cancel takes focus.
 */

export function tidy(text) {
  return String(text || "").trim().split(/\s+/).filter(Boolean).join(" ").toLowerCase();
}

export function phraseMatches(typed, phrase) {
  return tidy(typed) === tidy(phrase);
}

export function bindDeleteDialog(root) {
  root.querySelectorAll("[data-delete-open]").forEach((opener) => {
    const dialog = root.getElementById ? root.getElementById(opener.dataset.deleteOpen) : document.getElementById(opener.dataset.deleteOpen);
    if (!dialog || typeof dialog.showModal !== "function") {
      return; // No <dialog> support: the link's confirm page still works.
    }
    const form = dialog.querySelector("[data-delete-form]");
    const input = dialog.querySelector("[data-delete-input]");
    const submit = form.querySelector('button[type="submit"]');
    const update = () => {
      if (!input) return;
      const ok = phraseMatches(input.value, form.dataset.phrase);
      submit.disabled = !ok;
      submit.classList.toggle("opacity-50", !ok);
      submit.classList.toggle("cursor-not-allowed", !ok);
    };
    input?.addEventListener("input", update);
    form.addEventListener("submit", (event) => {
      if ((input && !phraseMatches(input.value, form.dataset.phrase)) || form.dataset.sent) {
        event.preventDefault();
        return;
      }
      form.dataset.sent = "1"; // one submit only; the server is idempotent too
      submit.setAttribute("aria-disabled", "true");
    });
    dialog.querySelector("[data-delete-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
      if (input) input.value = "";
      update();
      opener.focus();
    });
    opener.addEventListener("click", (event) => {
      event.preventDefault();
      update();
      dialog.showModal();
      (input || dialog.querySelector("[data-delete-close]")).focus();
    });
  });
}
