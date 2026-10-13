/*
 * Swipe a row left to act on it (touch only): a task row marks it done, a
 * rabbit row opens its weights to log one. The row follows the finger, the
 * action shows underneath, and past ~35% of the width it commits; short of
 * that it springs back. Every row keeps a visible button for the same
 * action, so mouse, keyboard and no-JS users are covered.
 */
const COMMIT = 0.35;

export function bindSwipe(doc, win = window) {
  const reduce = win.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  doc.querySelectorAll("[data-swipe]").forEach((row) => prepare(row, doc));

  let s = null;
  doc.addEventListener("pointerdown", (event) => {
    if (event.pointerType !== "touch") return;
    const row = event.target.closest?.("[data-swipe]");
    if (!row || event.target.closest("button, input, select, textarea")) return;
    s = { row, x: event.clientX, y: event.clientY, dx: 0, mode: null, id: event.pointerId, w: row.getBoundingClientRect().width };
  });
  doc.addEventListener("pointermove", (event) => {
    if (!s || event.pointerId !== s.id) return;
    const dx = event.clientX - s.x, dy = event.clientY - s.y;
    if (!s.mode) {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      s.mode = Math.abs(dx) > Math.abs(dy) * 1.4 && dx < 0 ? "swipe" : "scroll";
      if (s.mode === "swipe") s.row.classList.add("is-swiping");
    }
    if (s.mode !== "swipe") return;
    s.dx = Math.min(0, dx);
    const content = s.row.querySelector(".swipe-content");
    content.style.transform = `translateX(${s.dx}px)`;
    s.row.classList.toggle("swipe-armed", -s.dx > s.w * COMMIT);
  });
  const end = (event) => {
    if (!s || event.pointerId !== s.id) return;
    const { row, dx, w, mode } = s;
    s = null;
    if (mode !== "swipe") return;
    const content = row.querySelector(".swipe-content");
    row.classList.remove("is-swiping");
    const commit = -dx > w * COMMIT;
    content.style.transition = reduce ? "none" : "transform var(--dur-2) var(--ease-out)";
    content.style.transform = commit ? `translateX(${-w}px)` : "";
    const done = () => { content.style.transition = ""; };
    setTimeout(done, 260);
    // A swipe should not also count as a tap on the row's link.
    row.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); }, { capture: true, once: true });
    if (commit) {
      win.navigator.vibrate?.(8);
      setTimeout(() => act(row, win), reduce ? 0 : 180);
    } else row.classList.remove("swipe-armed");
  };
  doc.addEventListener("pointerup", end);
  doc.addEventListener("pointercancel", end);
}

function prepare(row, doc) {
  if (row.querySelector(".swipe-content")) return;
  const content = doc.createElement("div");
  content.className = "swipe-content";
  content.append(...row.childNodes);
  for (const cls of [...row.classList]) if (!cls.startsWith("swipe")) { content.classList.add(cls); }
  row.className = "swipe-row";
  const bg = doc.createElement("div");
  bg.className = "swipe-bg";
  bg.setAttribute("aria-hidden", "true");
  bg.textContent = row.dataset.swipeLabel || "Done";
  row.append(bg, content);
}

function act(row, win) {
  const form = row.querySelector(row.dataset.swipe || "form");
  if (row.dataset.swipeHref) { win.location.assign(row.dataset.swipeHref); return; }
  if (form?.requestSubmit) form.requestSubmit();
  else form?.submit();
}
