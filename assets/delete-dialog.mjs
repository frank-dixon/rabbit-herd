/*
 * Shared confirm dialog (delete a rabbit, convert a litter). The opener link
 * goes to a confirm page without script; with script it opens a native
 * <dialog> instead. showModal() makes the rest of the page inert (a real
 * focus trap) and Esc closes it. Plain confirm: the action button is enabled
 * right away and Cancel takes focus.
 */

export function bindDeleteDialog(root) {
  root.querySelectorAll("[data-delete-open]").forEach((opener) => {
    const dialog = root.getElementById ? root.getElementById(opener.dataset.deleteOpen) : document.getElementById(opener.dataset.deleteOpen);
    if (!dialog || typeof dialog.showModal !== "function") {
      return; // No <dialog> support: the link's confirm page still works.
    }
    const form = dialog.querySelector("[data-delete-form]");
    const submit = form.querySelector('button[type="submit"]');
    form.addEventListener("submit", (event) => {
      if (form.dataset.sent) {
        event.preventDefault();
        return;
      }
      form.dataset.sent = "1"; // one submit only; the server is idempotent too
      submit.setAttribute("aria-disabled", "true");
    });
    dialog.querySelector("[data-delete-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => opener.focus());
    opener.addEventListener("click", (event) => {
      event.preventDefault();
      dialog.showModal();
      dialog.querySelector("[data-delete-close]").focus();
    });
  });
}
