/*
 * Motion helpers shared by every feature: ease an added element in, and fade
 * and collapse an element before removing it. CSS in motion.css does the
 * work; with reduced motion the durations are near zero.
 */
export function enter(el) {
  el.classList.remove("mo-enter");
  void el.offsetWidth;
  el.classList.add("mo-enter");
  return el;
}

export function leave(el, { remove = true } = {}) {
  return new Promise((resolve) => {
    const wrap = el.ownerDocument.createElement(el.tagName === "LI" ? "li" : "div");
    wrap.className = "mo-collapse";
    el.replaceWith(wrap);
    const inner = el.tagName === "LI" ? el.ownerDocument.createElement("div") : el;
    if (inner !== el) { inner.append(...el.childNodes); inner.className = el.className; }
    wrap.append(inner);
    const done = () => { if (remove) wrap.remove(); resolve(); };
    requestAnimationFrame(() => {
      wrap.classList.add("mo-gone");
      const ms = parseFloat(getComputedStyle(wrap).transitionDuration) * 1000 || 0;
      setTimeout(done, ms + 40);
    });
  });
}
