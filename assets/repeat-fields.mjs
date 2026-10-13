/*
 * Task repeat: the "Every n days/weeks/months" fields show only while Custom
 * is picked. Without JS they stay visible and the server ignores them.
 */
export function bindRepeatFields(doc) {
  const sync = (select) => {
    const custom = select.form?.querySelector("[data-repeat-custom]");
    if (!custom) return;
    const show = select.value === "custom";
    custom.hidden = !show;
    if (show) custom.classList.add("enter");
  };
  doc.querySelectorAll('select[data-role="repeat"]').forEach(sync);
  doc.addEventListener("change", (event) => {
    if (event.target.matches?.('select[data-role="repeat"]')) sync(event.target);
  });
}
