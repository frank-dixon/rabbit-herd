/*
 * Segmented controls (components/segmented.html), one module app-wide: link segments
 * (Grid/List, Roomy/Compact, sort), radio segments (Settings > Mode, weigh-in unit) and
 * underline tabs (Rabbits Active/Former/Archived). One indicator per group, absolutely
 * positioned behind the options, slides (transform + width, ~200ms ease-out in CSS) to the
 * chosen option. It is measured, so options can differ in width, and re-measured on resize
 * and when web fonts finish loading. Without JS the chosen option keeps its static style;
 * with reduced motion it jumps (motion.css).
 */

/** Indicator geometry inside the group: x from the group's padding edge, and width. */
export function thumbPosition(groupRect, optionRect, clientLeft = 0) {
  if (!groupRect || !optionRect) return null;
  return { x: Math.round((optionRect.left - groupRect.left - clientLeft) * 100) / 100, w: Math.round(optionRect.width * 100) / 100 };
}

const OPTION = "[data-seg-option]";
const chosen = (group) => group.querySelector(`${OPTION}[data-selected], ${OPTION}:has(input:checked)`);

export function place(group) {
  const thumb = group.querySelector("[data-seg-thumb]");
  const option = chosen(group);
  if (!thumb || !option) { group.removeAttribute("data-seg-ready"); return null; }
  const pos = thumbPosition(group.getBoundingClientRect(), option.getBoundingClientRect(), group.clientLeft || 0);
  group.style.setProperty("--seg-x", `${pos.x}px`);
  group.style.setProperty("--seg-w", `${pos.w}px`);
  return pos;
}

function select(group, option) {
  group.querySelectorAll(OPTION).forEach((el) => {
    const on = el === option;
    el.toggleAttribute("data-selected", on);
    if (el.tagName === "A") { if (on) el.setAttribute("aria-current", el.dataset.current || "true"); else el.removeAttribute("aria-current"); }
  });
  place(group);
}

export function bindSegmented(root, win = typeof window === "undefined" ? null : window) {
  const groups = [...root.querySelectorAll("[data-segmented]")];
  const placeAll = () => groups.forEach(place);
  groups.forEach((group) => {
    place(group);
    // Turn the slide on after the first placement, so the page doesn't open with a slide.
    win?.requestAnimationFrame?.(() => group.setAttribute("data-seg-ready", ""));
    group.addEventListener("click", (event) => {
      const option = event.target.closest?.(OPTION);
      if (!option || option.tagName !== "A" || event.metaKey || event.ctrlKey || event.shiftKey) return;
      select(group, option); // the link still navigates; the indicator slides meanwhile
    });
    group.addEventListener("change", (event) => {
      const option = event.target.closest?.(OPTION);
      if (option) select(group, option);
    });
  });
  if (groups.length && win) {
    let queued = false;
    win.addEventListener("resize", () => {
      if (queued) return;
      queued = true;
      win.requestAnimationFrame(() => { queued = false; placeAll(); });
    }, { passive: true });
    root.fonts?.ready?.then(placeAll);
  }
  return { placeAll };
}
