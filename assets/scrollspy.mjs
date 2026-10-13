/*
 * Settings sub-nav: as the page scrolls, the link for the section in view gets
 * aria-current="location" (styled as an accent bar). The links are plain anchors,
 * so without JS they still jump to each section; CSS makes the jump smooth.
 */
export function bindScrollSpy(root, win = window) {
  const nav = root.querySelector("[data-settings-nav]");
  if (!nav) return null;
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const pairs = links.map((link) => [link, root.getElementById(link.hash.slice(1))]).filter(([, el]) => el);
  if (!pairs.length) return null;
  let current = null;
  const mark = (link) => {
    if (link === current) return;
    current?.removeAttribute("aria-current");
    link?.setAttribute("aria-current", "location");
    current = link;
  };
  const update = () => {
    const line = 120;
    // Sections can sit in a different order from the links, so go by position.
    const tops = pairs.map(([link, el]) => [link, el.getBoundingClientRect().top]);
    const doc = root.documentElement;
    const atBottom = doc && win.innerHeight + win.scrollY >= doc.scrollHeight - 4;
    const passed = atBottom ? tops : tops.filter(([, top]) => top - line <= 0);
    const pool = passed.length ? passed : tops.slice().sort((x, y) => x[1] - y[1]).slice(0, 1);
    mark(pool.reduce((best, row) => (row[1] > best[1] ? row : best))[0]);
  };
  let queued = false;
  const onScroll = () => {
    if (queued) return;
    queued = true;
    win.requestAnimationFrame(() => { queued = false; update(); });
  };
  links.forEach((link) => link.addEventListener("click", () => mark(link)));
  win.addEventListener("scroll", onScroll, { passive: true });
  win.addEventListener("resize", onScroll, { passive: true });
  update();
  return { update };
}
