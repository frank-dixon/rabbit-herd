import { test } from "node:test";
import assert from "node:assert/strict";
import { measureStack } from "./bottom-stack.mjs";

function fakeDoc(parts) {
  const vars = {};
  const el = (h, position = "fixed", display = "block") => ({ h, position, display, getBoundingClientRect: () => ({ height: h }) });
  const map = { "[data-app-tabs]": parts.tabs, ".temp-rail": parts.rail, ".pin-main": parts.pin, "[data-action-bar]": parts.bar };
  const doc = { body: { style: { setProperty: (k, v) => { vars[k] = v; } } }, querySelector: (sel) => (map[sel] ? el(...map[sel]) : null) };
  const win = { getComputedStyle: (e) => ({ position: e.position, display: e.display }) };
  return { doc, win, vars };
}

test("stacks the tab bar, rail and pinned button", () => {
  const { doc, win, vars } = fakeDoc({ tabs: [64], rail: [44], pin: [48] });
  assert.deepEqual(measureStack(doc, win), { tabs: 64, rail: 44, action: 48, total: 156 });
  assert.equal(vars["--stack-h"], "156px");
  assert.equal(vars["--rail-h"], "44px");
});

test("sub-pixel heights are kept, so the layers meet with no strip between them", () => {
  const { doc, win, vars } = fakeDoc({ tabs: [57.5], rail: [24], pin: [48] });
  measureStack(doc, win);
  assert.equal(vars["--tabbar-h"], "57.5px");
  assert.equal(vars["--stack-h"], "129.5px");
});

test("a form action bar counts, and a hidden or static one doesn't", () => {
  assert.equal(measureStack(fakeDoc({ rail: [24], bar: [76] }).doc, fakeDoc({}).win).total, 100);
  assert.equal(measureStack(fakeDoc({ tabs: [64, "fixed", "none"], bar: [76, "static"] }).doc, fakeDoc({}).win).total, 0);
});

test("the stack height also goes on <html>, for its scroll-padding (Critic v6 M5)", () => {
  const { doc, win } = fakeDoc({ rail: [44], bar: [76] });
  const root = {};
  doc.documentElement = { style: { setProperty: (k, v) => { root[k] = v; } } };
  measureStack(doc, win);
  assert.equal(root["--stack-h"], "120px");
});
