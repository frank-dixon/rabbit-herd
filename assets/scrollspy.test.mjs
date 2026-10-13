import { test } from "node:test";
import assert from "node:assert/strict";
import { activationLine, bindScrollSpy, pickActive } from "./scrollspy.mjs";

test("pickActive: the last section whose top has passed the line", () => {
  assert.equal(pickActive([0, 600, 1400], { line: 280 }), 0);
  assert.equal(pickActive([-700, -100, 700], { line: 280 }), 1);
  assert.equal(pickActive([-700, 279, 700], { line: 280 }), 1);
  assert.equal(pickActive([-1400, -800, 280], { line: 280 }), 2);
});

test("pickActive: first section before any has passed, last at the bottom", () => {
  assert.equal(pickActive([400, 900], { line: 280 }), 0);
  assert.equal(pickActive([-900, -300, 500], { line: 280, atBottom: true }), 2);
  assert.equal(pickActive([], { line: 280 }), -1);
});

test("activationLine: header offset plus a quarter of the viewport", () => {
  assert.equal(activationLine(80, 800), 280);
});

function fakePage(tops, { hash = "" } = {}) {
  const listeners = {};
  const timers = [];
  const link = (name) => {
    const a = {};
    return { hash: `#${name}`, setAttribute: (k, v) => (a[k] = v), removeAttribute: (k) => delete a[k],
      get current() { return a["aria-current"]; }, addEventListener: (t, f) => (listeners[`${name}:${t}`] = f) };
  };
  const links = Object.keys(tops).map(link);
  const scrolled = [];
  const sections = Object.fromEntries(Object.keys(tops).map((id) => [id,
    { getBoundingClientRect: () => ({ top: tops[id] }), scrollIntoView: () => scrolled.push(id) }]));
  const nav = { querySelectorAll: () => links };
  const root = { querySelector: () => nav, getElementById: (id) => sections[id], documentElement: { scrollHeight: 5000 } };
  const history = [];
  const win = { innerHeight: 800, scrollY: 0, location: { hash }, requestAnimationFrame: (f) => f(),
    getComputedStyle: () => ({ top: "80px" }), matchMedia: () => ({ matches: false }),
    history: { replaceState: (_s, _t, h) => history.push(h) },
    setTimeout: (f) => timers.push(f), clearTimeout: () => {}, addEventListener: (t, f) => (listeners[t] = f) };
  const current = () => links.map((l) => l.current);
  return { links, root, win, tops, listeners, current, scrolled, history, timers };
}

test("marks the section past the line as the page scrolls", () => {
  const page = fakePage({ rabbitry: 0, units: 600, appearance: 1400 });
  bindScrollSpy(page.root, page.win);
  assert.deepEqual(page.current(), ["location", undefined, undefined]);
  Object.assign(page.tops, { rabbitry: -700, units: 200, appearance: 1000 });
  page.listeners.scroll();
  assert.deepEqual(page.current(), [undefined, "location", undefined]);
});

test("the last section wins at the bottom of the page", () => {
  const page = fakePage({ rabbitry: -900, units: -300, appearance: 400 });
  page.win.scrollY = 4200;
  bindScrollSpy(page.root, page.win);
  assert.equal(page.links[2].current, "location");
});

test("a click marks its link, updates the hash, and holds through the scroll", () => {
  const page = fakePage({ rabbitry: 0, units: 600, appearance: 1400 });
  bindScrollSpy(page.root, page.win);
  page.listeners["appearance:click"]({ preventDefault() {} });
  assert.equal(page.links[2].current, "location");
  assert.deepEqual(page.history, ["#appearance"]);
  assert.deepEqual(page.scrolled, ["appearance"]);
  Object.assign(page.tops, { rabbitry: -500, units: 100, appearance: 900 }); // mid-scroll
  page.listeners.scroll();
  assert.equal(page.links[2].current, "location");
  Object.assign(page.tops, { rabbitry: -1300, units: -700, appearance: 100 });
  page.listeners.scrollend();
  assert.equal(page.links[2].current, "location");
});

test("the lock also ends on the timeout fallback", () => {
  const page = fakePage({ rabbitry: 0, units: 600 });
  bindScrollSpy(page.root, page.win);
  page.listeners["units:click"]({ preventDefault() {} });
  Object.assign(page.tops, { rabbitry: 0, units: 600 }); // scroll never happened
  page.timers.at(-1)();
  page.listeners.wheel();
  page.listeners.scroll();
  assert.equal(page.links[0].current, "location");
});

test("goes by position when sections sit in another order than the links", () => {
  const page = fakePage({ rabbitry: 900, units: 1500, appearance: 0 });
  bindScrollSpy(page.root, page.win);
  assert.equal(page.links[2].current, "location");
});

test("a hash on load marks that link", () => {
  const page = fakePage({ rabbitry: -600, units: 0, appearance: 600 }, { hash: "#units" });
  bindScrollSpy(page.root, page.win);
  assert.equal(page.links[1].current, "location");
});

test("a clicked section near the bottom stays active even though it can't reach the line", () => {
  const page = fakePage({ rabbitry: -2000, units: -1200, export: 500, account: 650 });
  page.win.scrollY = 4200; // at the bottom
  bindScrollSpy(page.root, page.win);
  assert.equal(page.links[3].current, "location");
  page.listeners["export:click"]({ preventDefault() {} });
  page.listeners.scrollend();
  assert.equal(page.links[2].current, "location");
  page.listeners.wheel();
  page.listeners.scroll();
  assert.equal(page.links[3].current, "location");
});
