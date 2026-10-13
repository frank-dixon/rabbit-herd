/*
 * Segmented link controls: on click, move the choice to the clicked segment at
 * once so the thumb slides while the next page loads. The link still navigates.
 */
export function bindSegmented(root) {
  root.querySelectorAll("[data-segmented]").forEach((group) => {
    group.addEventListener("click", (event) => {
      const option = event.target.closest("[data-seg-option]");
      if (!option || event.metaKey || event.ctrlKey || event.shiftKey) return;
      group.querySelectorAll("[data-seg-option]").forEach((el) => {
        const on = el === option;
        el.toggleAttribute("data-selected", on);
        el.classList.toggle("text-on-accent", on);
        el.classList.toggle("text-muted", !on);
        if (on) el.setAttribute("aria-current", "true"); else el.removeAttribute("aria-current");
      });
    });
  });
}
