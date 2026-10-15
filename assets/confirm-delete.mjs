/*
 * Shared delete confirm. Every [data-confirm-delete] link goes to its delete
 * URL, which shows the confirm page without script. With script it opens one
 * shared <dialog> instead: the title, one line, Cancel and a red Delete, and
 * Delete posts to that same URL (the server still checks the owner).
 */
export function bindConfirmDelete(doc, win = window) {
  let dialog;
  const build = () => {
    dialog = doc.createElement("dialog");
    dialog.className = "app-confirm";
    dialog.setAttribute("aria-labelledby", "app-confirm-title");
    dialog.innerHTML = '<div class="confirm-del"><h2 class="confirm-del-title" id="app-confirm-title"></h2><p class="confirm-del-text"></p><form method="post" class="confirm-del-actions"><input type="hidden" name="csrfmiddlewaretoken"><button type="button" class="confirm-del-btn" data-confirm-cancel>Cancel</button><button type="submit" class="confirm-del-btn is-danger" data-confirm-submit></button></form></div>';
    dialog.querySelector("[data-confirm-cancel]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    doc.body.append(dialog);
  };
  doc.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[data-confirm-delete]");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey) return;
    if (typeof win.HTMLDialogElement !== "function") return;
    event.preventDefault();
    if (!dialog) build();
    link.closest("details[open]")?.removeAttribute("open");
    dialog.querySelector(".confirm-del-title").textContent = link.dataset.title || "Delete this?";
    dialog.querySelector(".confirm-del-text").textContent = link.dataset.text || "";
    dialog.querySelector("[data-confirm-submit]").textContent = link.dataset.label || "Delete";
    dialog.querySelector("form").action = link.href;
    dialog.querySelector("input[name=csrfmiddlewaretoken]").value = link.dataset.csrf || doc.querySelector("input[name=csrfmiddlewaretoken]")?.value || "";
    dialog.showModal();
    dialog.querySelector("[data-confirm-cancel]").focus();
  });
}
