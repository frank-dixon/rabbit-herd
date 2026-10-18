/*
 * Settings sub-nav scrollspy. The active link is the last section whose top has passed a
 * fixed activation line (sticky header offset + 25% of the viewport), recomputed once per
 * frame while scrolling. At the bottom of the page the last section wins. A click marks its
 * link at once and holds it until the smooth scroll ends, so the sections scrolled past
 * don't flicker. Links are plain anchors, so without JS they still jump to each section.
 */

/** Pick the active index. tops: section tops relative to the viewport, in page order. */
export function pickActive(tops, { line, atBottom = false }) {
  if (!tops.length) return -1;
  if (atBottom) return tops.length - 1;
  let active = 0;
  tops.forEach((top, i) => { if (top <= line) active = i; });
  return active;
}

export function activationLine(headerOffset, viewportHeight) {
  return headerOffset + viewportHeight * 0.25;
}

export function bindScrollSpy(root, win = window) {
  const nav = root.querySelector("[data-settings-nav]");
  if (!nav) return null;
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const pairs = links.map((link) => [link, root.getElementById(link.hash.slice(1))]).filter(([, el]) => el);
  if (!pairs.length) return null;
  // Page order, whatever order the links are in.
  const ordered = () => pairs.map(([link, el]) => [link, el.getBoundingClientRect().top]).sort((a, b) => a[1] - b[1]);
  let current = null;
  let lockedTo = null;
  let lockTimer = 0;
  // The link last clicked (or named by the hash). Near the bottom, sections too short to
  // reach the line stay chosen until the reader scrolls by hand.
  let chosen = null;
  const mark = (link) => {
    if (link === current) return;
    current?.removeAttribute("aria-current");
    link?.setAttribute("aria-current", "location");
    current = link;
  };
  const headerOffset = () => {
    const top = parseFloat(win.getComputedStyle?.(nav)?.top);
    return Number.isFinite(top) ? top : 80;
  };
  const update = () => {
    if (lockedTo) return;
    const rows = ordered();
    const doc = root.documentElement;
    const atBottom = !!doc && win.innerHeight + win.scrollY >= doc.scrollHeight - 2;
    const line = activationLine(headerOffset(), win.innerHeight);
    let i = pickActive(rows.map((r) => r[1]), { line, atBottom });
    const c = chosen && rows.findIndex((r) => r[0] === chosen);
    if (chosen && c >= 0 && c >= pickActive(rows.map((r) => r[1]), { line }) && rows[c][1] < win.innerHeight) i = c;
    if (i >= 0) mark(rows[i][0]);
  };
  const unlock = () => { lockedTo = null; win.clearTimeout(lockTimer); update(); };
  // scrollend where supported; otherwise end the lock once scrolling has been quiet a moment.
  const hold = (link, ms = 1200) => {
    lockedTo = link;
    chosen = link;
    mark(link);
    win.clearTimeout(lockTimer);
    lockTimer = win.setTimeout(unlock, ms);
  };
  let queued = false;
  const onScroll = () => {
    if (lockedTo) { win.clearTimeout(lockTimer); lockTimer = win.setTimeout(unlock, 160); return; }
    if (queued) return;
    queued = true;
    win.requestAnimationFrame(() => { queued = false; update(); });
  };
  for (const [link, el] of pairs) {
    link.addEventListener("click", (event) => {
      if (event && (event.metaKey || event.ctrlKey || event.shiftKey || event.button > 0)) return;
      // Settings shows one section at a time by its #anchor (:target), so let the link change the
      // hash: replaceState wouldn't update :target. Back then returns to the list on a phone.
      hold(link);
    });
  }
  win.addEventListener("scroll", onScroll, { passive: true });
  win.addEventListener("scrollend", () => { if (lockedTo) unlock(); }, { passive: true });
  win.addEventListener("resize", onScroll, { passive: true });
  for (const type of ["wheel", "touchmove", "keydown"]) win.addEventListener(type, () => { chosen = null; }, { passive: true });
  win.addEventListener("hashchange", () => {
    const link = links.find((l) => l.hash === win.location.hash);
    if (link) hold(link, 400);
  });
  const initial = win.location?.hash && links.find((l) => l.hash === win.location.hash);
  if (initial) hold(initial, 400); else update();
  return { update };
}
