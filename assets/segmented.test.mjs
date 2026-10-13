import { test } from "node:test";
import assert from "node:assert/strict";
import { thumbPosition } from "./segmented.mjs";

test("thumbPosition: offset from the group's padding edge and the option's width", () => {
  assert.deepEqual(thumbPosition({ left: 100 }, { left: 103, width: 60 }, 1), { x: 2, w: 60 });
  assert.deepEqual(thumbPosition({ left: 0 }, { left: 72.333, width: 88.666 }, 0), { x: 72.33, w: 88.67 });
});

test("thumbPosition: unequal widths land on the chosen option", () => {
  const group = { left: 10 };
  const options = [{ left: 13, width: 50 }, { left: 63, width: 90 }, { left: 153, width: 40 }];
  assert.deepEqual(options.map((o) => thumbPosition(group, o, 1)), [{ x: 2, w: 50 }, { x: 52, w: 90 }, { x: 142, w: 40 }]);
});

test("thumbPosition: nothing to place", () => {
  assert.equal(thumbPosition({ left: 0 }, null), null);
});
