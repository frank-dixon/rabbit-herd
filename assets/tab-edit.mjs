/*
 * Customizable bottom bar. Press and hold a tab (about 450 ms) or right-click
 * it to enter edit mode: the bar lifts, empty slots show, and the other pages
 * slide up beneath it. Drag a page or tab between tabs or to either end to
 * insert it there (an indicator marks the spot and the tabs reflow); once
 * the bar is full a drop swaps with the tab under it. Drag a tab down to
 * remove it. Tapping a page fills the next empty slot; with a full bar, tap
 * the page and then the tab it replaces. Arrow keys move a focused tab,
 * Delete removes it. 3 to 5 tabs. Done, Esc or a tap outside saves. Settings
 * has a plain form for the same thing. Rules live in tab-order.mjs.
 */
import { MAX, MIN, addNext, insertAt, insertionIndex, removeTab } from "./tab-order.mjs";

const HOLD_MS = 450;
const MOVE_SLOP = 8;

export function bindTabEdit(doc, win = window) {
  const nav = doc.querySelector("[data-app-tabs]");
  const data = doc.getElementById("tab-destinations");
  if (!nav || !data) return null;
  const bar = nav.querySelector("[data-tab-list]");
  const tray = nav.querySelector("[data-tab-tray]");
  const trayList = nav.querySelector("[data-tray-list]");
  const head = nav.querySelector("[data-tab-edit-head]");
  const hint = nav.querySelector("[data-tab-hint]");
  const places = Object.fromEntries(JSON.parse(data.textContent).map((d) => [d.key, d]));
  const badges = {};
  bar.querySelectorAll("[data-tab]").forEach((li) => {
    const badge = li.querySelector("[data-badge]");
    if (badge) badges[li.dataset.tab] = badge.outerHTML;
  });
  const reduce = win.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  let tabs = [...bar.querySelectorAll("[data-tab]")].map((li) => li.dataset.tab);
  let editing = false;
  let selected = null; // {from: "bar"|"tray", key}
  let drag = null;
  let saved = tabs.join(",");

  const icon = (d) => `<svg class="h-6 w-6 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;

  function barItem(key) {
    const p = places[key];
    const active = p.active;
    if (!editing) {
      return `<li data-tab="${key}"><a href="${p.url}" class="group flex min-h-[58px] flex-col items-center justify-center gap-0.5 px-1 pt-1.5 pb-1 text-[11px] font-medium focus:outline-none ${active ? "text-accent" : "text-muted"}"${active ? ' aria-current="page"' : ""}><span class="relative grid h-7 w-14 place-items-center rounded-full group-focus-visible:ring-2 group-focus-visible:ring-accent ${active ? "bg-accent-soft" : ""}">${icon(p.icon)}${badges[key] || ""}</span><span class="max-w-full overflow-hidden text-ellipsis whitespace-nowrap">${p.label}</span></a></li>`;
    }
    const sel = selected && selected.key === key;
    return `<li data-tab="${key}" data-slot><button type="button" class="tab-edit-item flex min-h-[58px] w-full flex-col items-center justify-center gap-0.5 px-1 pt-1.5 pb-1 text-[11px] font-medium text-ink" aria-pressed="${sel}" aria-label="${p.label}, tab ${tabs.indexOf(key) + 1} of ${tabs.length}"><span class="relative grid h-7 w-14 place-items-center rounded-full">${icon(p.icon)}</span><span class="max-w-full overflow-hidden text-ellipsis whitespace-nowrap">${p.label}</span></button></li>`;
  }

  function trayItem(key) {
    const p = places[key];
    const sel = selected && selected.key === key;
    return `<li data-place="${key}"><button type="button" class="tab-edit-item flex h-16 w-full flex-col items-center justify-center gap-1 rounded-md border border-line bg-canvas text-[11px] font-medium text-ink" aria-pressed="${sel}" aria-label="${p.label}, not in the bar">${icon(p.icon)}<span class="max-w-full overflow-hidden text-ellipsis whitespace-nowrap px-1">${p.label}</span></button></li>`;
  }

  const emptySlot = (i) => `<li data-empty aria-hidden="true"><span class="tab-empty flex min-h-[58px] items-center justify-center"><span class="h-7 w-10 rounded-full border border-dashed border-line"></span></span><span class="sr-only">Empty slot ${i + 1}</span></li>`;

  function render() {
    const slots = editing ? MAX : tabs.length;
    bar.style.gridTemplateColumns = `repeat(${slots}, minmax(0, 1fr))`;
    const before = reduce ? null : rects();
    bar.innerHTML = tabs.map(barItem).join("") + (editing ? Array.from({ length: MAX - tabs.length }, (_, i) => emptySlot(tabs.length + i)).join("") : "");
    if (before) reflow(before);
    if (editing) {
      const rest = Object.keys(places).filter((k) => !tabs.includes(k));
      trayList.innerHTML = rest.map(trayItem).join("");
    }
  }

  // Slide tabs from their old spot to the new one (FLIP), so a change reads as a move.
  function rects() {
    return Object.fromEntries([...bar.querySelectorAll("[data-tab]")].map((li) => [li.dataset.tab, li.getBoundingClientRect().left]));
  }
  function reflow(before) {
    bar.querySelectorAll("[data-tab]").forEach((li) => {
      const was = before[li.dataset.tab];
      if (was === undefined) return;
      const dx = was - li.getBoundingClientRect().left;
      if (Math.abs(dx) > 1) li.animate([{ transform: `translateX(${dx}px)` }, { transform: "none" }], { duration: 220, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
    });
  }

  let indicator = null;
  function showIndicator(index) {
    if (!indicator) {
      indicator = doc.createElement("span");
      indicator.className = "tab-insert";
      indicator.setAttribute("aria-hidden", "true");
      bar.style.position = "relative";
      bar.append(indicator);
    }
    const items = [...bar.querySelectorAll("[data-tab]")];
    const box = bar.getBoundingClientRect();
    const edge = index < items.length ? items[index].getBoundingClientRect().left : items.length ? items[items.length - 1].getBoundingClientRect().right : box.left;
    indicator.style.left = `${edge - box.left - 1}px`;
    indicator.hidden = false;
  }
  function hideIndicator() { if (indicator) { indicator.remove(); indicator = null; } }

  const instruction = nav.querySelector("[data-tab-instruction]");
  const cancel = nav.querySelector("[data-tab-cancel]");
  const RESTING = "Drag to reorder or add. Up to 5.";
  // Show the pending step in the header: what to tap next, the tabs it can
  // land on highlighted, and Cancel.
  function picking(text) {
    if (instruction) instruction.textContent = text || RESTING;
    if (cancel) cancel.hidden = !text;
    if (text) nav.dataset.picking = selected?.zone || "";
    else delete nav.dataset.picking;
  }
  function say(text) { if (hint) hint.textContent = text; }

  function enter() {
    if (editing) return;
    editing = true;
    selected = null;
    win.navigator.vibrate?.(12);
    const before = bar.getBoundingClientRect().top;
    nav.dataset.editing = "";
    head.hidden = false;
    tray.hidden = false;
    render();
    say("");
    if (!reduce) {
      const after = bar.getBoundingClientRect().top;
      bar.animate([{ transform: `translateY(${before - after}px)` }, { transform: "none" }], { duration: 260, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
      for (const el of [head, tray]) el.animate([{ opacity: 0, transform: "translateY(12px)" }, { opacity: 1, transform: "none" }], { duration: 240, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
    }
    nav.querySelector("[data-tab-done]")?.focus({ preventScroll: true });
  }

  async function exit() {
    if (!editing) return;
    const finish = () => {
      editing = false;
      selected = null;
      picking("");
      delete nav.dataset.editing;
      head.hidden = true;
      tray.hidden = true;
      render();
    };
    if (reduce) finish();
    else {
      const anims = [head, tray].map((el) => el.animate([{ opacity: 1 }, { opacity: 0, transform: "translateY(12px)" }], { duration: 160, easing: "cubic-bezier(0.4, 0, 1, 1)", fill: "forwards" }));
      await Promise.all(anims.map((a) => a.finished.catch(() => {})));
      const before = bar.getBoundingClientRect().top;
      finish();
      anims.forEach((a) => a.cancel());
      const after = bar.getBoundingClientRect().top;
      bar.animate([{ transform: `translateY(${before - after}px)` }, { transform: "none" }], { duration: 220, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
    }
    if (tabs.join(",") !== saved) save();
  }

  async function save() {
    const body = new FormData();
    tabs.forEach((k) => body.append("tab", k));
    const token = doc.querySelector('meta[name="csrf-token"]')?.content || "";
    try {
      const response = await win.fetch(nav.dataset.saveUrl, { method: "POST", body, credentials: "same-origin", headers: { "X-CSRFToken": token, "X-Requested-With": "fetch" } });
      if (response.ok) saved = tabs.join(",");
    } catch { /* kept locally until the next save */ }
  }

  // Apply a change: a new tab list, or a message when it isn't allowed.
  function apply(next, key, refusal) {
    if (!next) return refusal;
    tabs = next;
    render();
    flash(key);
    return "";
  }
  function move(from, to) {
    if (!to) return "";
    if (to.zone === "bar") return apply(insertAt(tabs, from.key, to.index ?? (to.key ? tabs.indexOf(to.key) : tabs.length)), from.key, "");
    if (from.zone === "bar" && to.zone === "tray") return apply(removeTab(tabs, from.key), from.key, `Keep at least ${MIN} tabs.`);
    return "";
  }

  function flash(key) {
    const el = bar.querySelector(`[data-tab="${key}"] .tab-edit-item`);
    if (el && !reduce) el.animate([{ transform: "scale(0.9)", opacity: 0.6 }, { transform: "none", opacity: 1 }], { duration: 200, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
  }

  function zoneAt(x, y) {
    const el = doc.elementFromPoint(x, y);
    if (!el) return null;
    if (bar.contains(el) || el === bar) {
      const items = [...bar.querySelectorAll("[data-tab]")].filter((li) => li !== drag?.source);
      const index = insertionIndex(x, items.map((li) => { const r = li.getBoundingClientRect(); return [r.left, r.right]; }));
      const slot = el.closest("[data-slot]");
      // A full bar swaps with the tab under the pointer; otherwise insert between.
      if (tabs.length >= MAX && drag?.from.zone === "tray" && slot) return { zone: "bar", key: slot.dataset.tab, index: tabs.indexOf(slot.dataset.tab), el: slot };
      const key = items[index]?.dataset.tab;
      return { zone: "bar", key: null, index: key ? tabs.indexOf(key) : tabs.length, insert: index, el: bar };
    }
    if (tray.contains(el)) return { zone: "tray", key: el.closest("[data-place]")?.dataset.place || null, el: tray };
    return null;
  }

  // Long-press to enter, and drag while editing.
  let hold = null;
  nav.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 && event.pointerType === "mouse") return;
    const li = event.target.closest("[data-tab], [data-place]");
    if (!li) return;
    if (!editing) {
      if (!event.target.closest("[data-tab]")) return;
      const start = { x: event.clientX, y: event.clientY };
      hold = { start, timer: win.setTimeout(() => { hold.fired = true; enter(); }, HOLD_MS), fired: false };
      return;
    }
    const from = li.dataset.tab ? { zone: "bar", key: li.dataset.tab } : { zone: "tray", key: li.dataset.place };
    drag = { from, start: { x: event.clientX, y: event.clientY }, ghost: null, over: null, id: event.pointerId, source: li };
  });

  nav.addEventListener("click", (event) => {
    if (hold?.fired) { event.preventDefault(); event.stopPropagation(); hold = null; return; }
  }, true);

  win.addEventListener("pointermove", (event) => {
    if (hold && !hold.fired) {
      if (Math.hypot(event.clientX - hold.start.x, event.clientY - hold.start.y) > MOVE_SLOP) { win.clearTimeout(hold.timer); hold = null; }
    }
    if (!drag || event.pointerId !== drag.id) return;
    if (!drag.ghost) {
      if (Math.hypot(event.clientX - drag.start.x, event.clientY - drag.start.y) < MOVE_SLOP) return;
      const r = drag.source.getBoundingClientRect();
      const ghost = drag.source.cloneNode(true);
      ghost.className = "tab-ghost";
      ghost.style.width = `${r.width}px`;
      ghost.style.height = `${r.height}px`;
      doc.body.append(ghost);
      drag.ghost = ghost;
      drag.offset = { x: drag.start.x - r.left, y: drag.start.y - r.top };
      drag.source.classList.add("tab-dragging");
      nav.setPointerCapture?.(event.pointerId);
    }
    event.preventDefault();
    drag.ghost.style.transform = `translate(${event.clientX - drag.offset.x}px, ${event.clientY - drag.offset.y}px) scale(1.06)`;
    const over = zoneAt(event.clientX, event.clientY);
    if (drag.over?.el !== over?.el) {
      drag.over?.el.classList.remove("tab-target");
      if (over && over.el !== bar) over.el.classList.add("tab-target");
    }
    if (over && over.insert !== undefined) showIndicator(over.insert);
    else hideIndicator();
    drag.over = over;
  }, { passive: false });

  function endDrag(event) {
    if (hold && !hold.fired) { win.clearTimeout(hold.timer); hold = null; }
    if (!drag || (event && event.pointerId !== drag.id)) return;
    const { ghost, over, from, source } = drag;
    drag = null;
    source.classList.remove("tab-dragging");
    over?.el.classList.remove("tab-target");
    hideIndicator();
    if (!ghost) return; // a tap; handled by click
    ghost.remove();
    say(move(from, over) || "");
    // Swallow only the click this same release produces.
    suppressClick = true;
    win.setTimeout(() => { suppressClick = false; }, 0);
  }
  let suppressClick = false;
  win.addEventListener("pointerup", endDrag);
  win.addEventListener("pointercancel", endDrag);

  // Tap-to-swap (and keyboard): select one item, then the place to put it.
  nav.addEventListener("click", (event) => {
    if (!editing) return;
    if (suppressClick) { suppressClick = false; return; }
    if (event.target.closest("[data-tab-done]")) { exit(); return; }
    if (event.target.closest("[data-tab-cancel]")) { selected = null; picking(""); render(); return; }
    const li = event.target.closest("[data-tab], [data-place]");
    if (!li) return;
    const here = li.dataset.tab ? { zone: "bar", key: li.dataset.tab } : { zone: "tray", key: li.dataset.place };
    if (!selected && here.zone === "tray" && tabs.length < MAX) {
      say(apply(addNext(tabs, here.key), here.key, ""));
      return;
    }
    if (!selected) {
      selected = here;
      render();
      picking(here.zone === "bar" ? `Tap where ${places[here.key].label} should go, or use the arrow keys.` : `Tap the tab ${places[here.key].label} replaces.`);
      focusItem(here);
      return;
    }
    const first = selected;
    selected = null;
    picking("");
    let message = "";
    if (first.zone === "tray" && here.zone === "bar") message = move(first, { zone: "bar", key: here.key, index: tabs.indexOf(here.key) });
    else if (first.zone === "bar" && here.zone === "tray") message = move({ zone: "tray", key: here.key }, { zone: "bar", key: first.key, index: tabs.indexOf(first.key) });
    else if (first.zone === "bar" && here.zone === "bar" && first.key !== here.key) {
      const a = tabs.indexOf(first.key), b = tabs.indexOf(here.key);
      message = apply(insertAt(tabs, first.key, a < b ? b + 1 : b), first.key, "");
    }
    render();
    say(message);
    focusItem(here.zone === "bar" ? here : { zone: "bar", key: first.key });
  });

  function focusItem(at) {
    const sel = at.zone === "bar" ? `[data-tab="${at.key}"] button` : `[data-place="${at.key}"] button`;
    nav.querySelector(sel)?.focus({ preventScroll: true });
  }

  // Keyboard: in edit mode, Delete removes the focused tab.
  nav.addEventListener("keydown", (event) => {
    if (!editing) return;
    const li = event.target.closest?.("[data-tab]");
    if (li && (event.key === "Delete" || event.key === "Backspace")) {
      event.preventDefault();
      say(move({ zone: "bar", key: li.dataset.tab }, { zone: "tray", key: null }));
    }
    if (li && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
      event.preventDefault();
      const i = tabs.indexOf(li.dataset.tab);
      const to = event.key === "ArrowLeft" ? Math.max(0, i - 1) : Math.min(tabs.length, i + 2);
      apply(insertAt(tabs, li.dataset.tab, to), li.dataset.tab, "");
      focusItem({ zone: "bar", key: li.dataset.tab });
    }
  });

  nav.addEventListener("contextmenu", (event) => {
    if (!event.target.closest("[data-tab], [data-place]")) return;
    event.preventDefault();
    if (hold) { win.clearTimeout(hold.timer); hold = null; }
    enter();
  });
  doc.addEventListener("keydown", (event) => { if (event.key === "Escape" && editing) exit(); });
  doc.addEventListener("pointerdown", (event) => { if (editing && !nav.contains(event.target)) exit(); });

  return { enter, exit, get tabs() { return [...tabs]; }, move };
}
