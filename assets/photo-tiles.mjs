/*
 * Small upgrades for the Photos card on a rabbit's page. Without script the
 * Upload button posts the chosen file and each tile's panel opens with
 * :target. With script, choosing a file uploads it straight away (through
 * the same shrink step in photo-upload.mjs), and a tile's panel opens as a
 * modal <dialog>: focus stays inside and Esc closes it.
 */

export function bindPhotoTiles(root) {
  root.querySelectorAll("[data-photo-tile-upload]").forEach((form) => {
    form.querySelectorAll("[data-nojs-only]").forEach((el) => (el.hidden = true));
    const input = form.querySelector("[data-photo-autosubmit]");
    input.addEventListener("change", () => {
      if (input.files && input.files.length) {
        form.requestSubmit();
      }
    });
  });
  root.querySelectorAll("[data-photo-open]").forEach((opener) => {
    const dialog = document.getElementById(opener.dataset.photoOpen);
    if (!dialog || typeof dialog.showModal !== "function") {
      return;
    }
    opener.addEventListener("click", (event) => {
      event.preventDefault();
      dialog.showModal();
    });
    dialog.querySelector("[data-photo-close]").addEventListener("click", (event) => {
      event.preventDefault();
      dialog.close();
    });
    dialog.addEventListener("close", () => opener.focus());
  });
}
