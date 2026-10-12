/*
 * Status card: show the date and cause of death only while Deceased is
 * chosen, and let a quick-pick chip fill the cause. Without script the
 * fields stay visible with a hint, and the server ignores them for any
 * other status.
 */
export function bindDeathFields(root) {
  root.querySelectorAll("[data-death-fields]").forEach((fieldset) => {
    const form = fieldset.closest("form");
    fieldset.querySelectorAll("[data-nojs-only]").forEach((el) => (el.hidden = true));
    const picks = fieldset.querySelector("[data-cause-picks]");
    const cause = fieldset.querySelector('input[name="death_cause"]');
    if (picks) {
      picks.hidden = false;
      picks.querySelectorAll("[data-cause]").forEach((chip) =>
        chip.addEventListener("click", () => {
          cause.value = chip.dataset.cause;
          cause.focus();
        }),
      );
    }
    const update = () => {
      const chosen = form.querySelector('input[name="status"]:checked');
      fieldset.hidden = !(chosen && chosen.value === "deceased");
    };
    form.querySelectorAll('input[name="status"]').forEach((radio) => radio.addEventListener("change", update));
    update();
  });
}
