/*
 * Delete-a-rabbit dialog. The Delete link goes to a confirm page without
 * script; with script it opens a native <dialog> instead. showModal() makes
 * the rest of the page inert (a real focus trap) and Esc closes it.
 * The confirm button stays disabled until the typed text matches; the
 * server checks the text again either way.
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
      const ok = phraseMatches(input.value, form.dataset.phrase);
      submit.disabled = !ok;
      submit.classList.toggle("opacity-50", !ok);
      submit.classList.toggle("cursor-not-allowed", !ok);
    };
    input.addEventListener("input", update);
    form.addEventListener("submit", (event) => {
      if (!phraseMatches(input.value, form.dataset.phrase)) {
        event.preventDefault();
      }
    });
    dialog.querySelector("[data-delete-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
      input.value = "";
      update();
      opener.focus();
    });
    opener.addEventListener("click", (event) => {
      event.preventDefault();
      update();
      dialog.showModal();
      input.focus();
    });
  });
}
