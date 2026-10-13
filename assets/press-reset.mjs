/*
 * iOS can leave a card looking pressed after a long-press preview or a
 * cancelled touch. Clear the pressed state whenever a touch ends or is cut off.
 */
export function bindPressReset(doc, win = window) {
  const root = doc.documentElement;
  const reset = () => {
    root.classList.add("press-reset");
    const el = doc.activeElement;
    if (el && el !== doc.body && el.matches?.("a, button") && !el.matches(":focus-visible")) el.blur();
  };
  const clear = () => root.classList.remove("press-reset");
  for (const type of ["touchcancel", "pointercancel", "contextmenu"]) doc.addEventListener(type, reset, true);
  doc.addEventListener("touchend", () => win.requestAnimationFrame(() => { if (doc.querySelector(":active")) reset(); }), true);
  doc.addEventListener("visibilitychange", reset);
  win.addEventListener("pageshow", reset);
  win.addEventListener("blur", reset);
  doc.addEventListener("pointerdown", clear, true);
  doc.addEventListener("dragstart", (event) => { if (event.target?.tagName === "IMG") event.preventDefault(); }, true);
}
