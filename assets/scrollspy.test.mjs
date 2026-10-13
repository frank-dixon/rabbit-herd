import { test } from "node:test";
import assert from "node:assert/strict";
import { bindScrollSpy } from "./scrollspy.mjs";

function fakePage(tops) {
  const listeners = {};
  const attrs = (name) => {
    const a = {};
    return { hash: `#${name}`, setAttribute: (k, v) => (a[k] = v), removeAttribute: (k) => delete a[k],
      get current() { return a["aria-current"]; }, addEventListener: (t, f) => (listeners[`${name}:${t}`] = f) };
  };
  const links = Object.keys(tops).map(attrs);
  const sections = Object.fromEntries(Object.keys(tops).map((id) => [id, { getBoundingClientRect: () => ({ top: tops[id] }) }]));
  const nav = { querySelectorAll: () => links };
  const root = { querySelector: () => nav, getElementById: (id) => sections[id], documentElement: { scrollHeight: 5000 } };
  const win = { innerHeight: 800, scrollY: 0, requestAnimationFrame: (f) => f(),
    addEventListener: (t, f) => (listeners[t] = f) };
  return { links, root, win, tops, listeners };
}

test("marks the section whose heading has passed the top line", () => {
  const page = fakePage({ rabbitry: 0, units: 600, appearance: 1400 });
  bindScrollSpy(page.root, page.win);
  assert.deepEqual(page.links.map((l) => l.current), ["location", undefined, undefined]);
  Object.assign(page.tops, { rabbitry: -700, units: -100, appearance: 700 });
  page.listeners.scroll();
  assert.deepEqual(page.links.map((l) => l.current), [undefined, "location", undefined]);
});

test("the last section wins at the bottom of the page", () => {
  const page = fakePage({ rabbitry: -900, units: -300, appearance: 400 });
  page.win.scrollY = 4200;
  bindScrollSpy(page.root, page.win);
  assert.equal(page.links[2].current, "location");
});

test("a click marks its link at once", () => {
  const page = fakePage({ rabbitry: 0, units: 600 });
  bindScrollSpy(page.root, page.win);
  page.listeners["units:click"]();
  assert.deepEqual(page.links.map((l) => l.current), [undefined, "location"]);
});

test("goes by position when sections sit in another order than the links", () => {
  const page = fakePage({ rabbitry: 900, units: 1500, appearance: 0 });
  bindScrollSpy(page.root, page.win);
  assert.equal(page.links[2].current, "location");
  Object.assign(page.tops, { rabbitry: 50, units: 650, appearance: -850 });
  page.listeners.scroll();
  assert.equal(page.links[0].current, "location");
});
