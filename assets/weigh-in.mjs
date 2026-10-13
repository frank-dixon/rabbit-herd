/*
 * Quick weigh-in keypad: large keys type into the weight field without
 * raising the phone keyboard. Without JS the field takes typing as normal.
 */
export function bindWeighIn(doc, win = window) {
  const root = doc.querySelector("[data-weigh-in]");
  if (!root) return;
  const input = root.querySelector("#id_value");
  const pad = root.querySelector("[data-keypad]");
  if (!input || !pad) return;
  const coarse = win.matchMedia?.("(pointer: coarse)").matches;
  pad.hidden = false;
  if (coarse) { input.setAttribute("inputmode", "none"); input.blur(); }
  pad.addEventListener("click", (event) => {
    const key = event.target.closest("[data-key]")?.dataset.key;
    if (!key) return;
    let v = input.value;
    if (key === "back") v = v.slice(0, -1);
    else if (key === ".") { if (!v.includes(".")) v = (v || "0") + "."; }
    else if (v.replace(".", "").length < 6) v = v === "0" ? key : v + key;
    input.value = v;
    win.navigator.vibrate?.(4);
  });
  doc.addEventListener("keydown", (event) => {
    if (event.target === input || event.metaKey || event.ctrlKey) return;
    if (/^[0-9.]$/.test(event.key)) { pad.querySelector(`[data-key="${event.key}"]`)?.click(); event.preventDefault(); }
    else if (event.key === "Backspace") { pad.querySelector('[data-key="back"]').click(); event.preventDefault(); }
  });
}
