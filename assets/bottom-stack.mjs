/*
 * Phone bottom stack: measures the tab bar, the guest/demo rail and the page's action (pinned
 * main button or a form's action bar) and writes their real heights into CSS variables on <body>,
 * so layout.css can stack them with no overlap and pad the page by exactly the stack's height.
 */
const fixedHeight = (win, el) => {
  if (!el) return 0;
  const cs = win.getComputedStyle(el);
  if (cs.display === "none" || cs.position !== "fixed") return 0;
  return el.getBoundingClientRect().height;
};

export function measureStack(doc, win = window) {
  const body = doc.body;
  if (!body) return null;
  const tabs = fixedHeight(win, doc.querySelector("[data-app-tabs]"));
  const rail = fixedHeight(win, doc.querySelector(".temp-rail"));
  const action = Math.max(fixedHeight(win, doc.querySelector(".pin-main")), fixedHeight(win, doc.querySelector("[data-action-bar]")));
  const px = (n) => `${Math.round(n)}px`;
  body.style.setProperty("--tabbar-h", px(tabs));
  body.style.setProperty("--rail-h", px(rail));
  body.style.setProperty("--action-h", px(action));
  body.style.setProperty("--stack-h", px(tabs + rail + action));
  return { tabs, rail, action, total: tabs + rail + action };
}

export function bindBottomStack(doc, win = window) {
  let frame = 0;
  const update = () => {
    win.cancelAnimationFrame(frame);
    frame = win.requestAnimationFrame(() => {
      // Measure with the CSS defaults, so a stale value never feeds back into the result.
      ["--tabbar-h", "--rail-h", "--action-h", "--stack-h"].forEach((name) => doc.body.style.removeProperty(name));
      measureStack(doc, win);
    });
  };
  update();
  win.addEventListener("resize", update);
  if ("ResizeObserver" in win) {
    const observer = new win.ResizeObserver(update);
    doc.querySelectorAll("[data-app-tabs], .temp-rail, .pin-main, [data-action-bar]").forEach((el) => observer.observe(el));
  }
}
