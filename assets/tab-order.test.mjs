import assert from "node:assert/strict";
import test from "node:test";
import { addNext, insertAt, insertionIndex, removeTab } from "./tab-order.mjs";

const T = ["today", "rabbits", "litters"];

test("inserting a new page between tabs or at either end", () => {
  assert.deepEqual(insertAt(T, "tasks", 0), ["tasks", "today", "rabbits", "litters"]);
  assert.deepEqual(insertAt(T, "tasks", 1), ["today", "tasks", "rabbits", "litters"]);
  assert.deepEqual(insertAt(T, "tasks", 3), ["today", "rabbits", "litters", "tasks"]);
});

test("moving a tab reorders without duplicates", () => {
  assert.deepEqual(insertAt(T, "today", 3), ["rabbits", "litters", "today"]);
  assert.deepEqual(insertAt(T, "litters", 0), ["litters", "today", "rabbits"]);
  assert.deepEqual(insertAt(T, "rabbits", 1), T);
});

test("a full bar swaps instead of growing", () => {
  const full = ["a", "b", "c", "d", "e"];
  assert.deepEqual(insertAt(full, "x", 1), ["a", "x", "c", "d", "e"]);
  assert.deepEqual(insertAt(full, "x", 5), ["a", "b", "c", "d", "x"]);
  assert.deepEqual(insertAt(full, "e", 0), ["e", "a", "b", "c", "d"]);
});

test("tap-to-add fills the next empty slot", () => {
  assert.deepEqual(addNext(T, "tasks"), [...T, "tasks"]);
  assert.equal(addNext(["a", "b", "c", "d", "e"], "x"), null);
  assert.equal(addNext(T, "today"), null);
});

test("never fewer than three tabs", () => {
  assert.equal(removeTab(T, "today"), null);
  assert.deepEqual(removeTab([...T, "tasks"], "today"), ["rabbits", "litters", "tasks"]);
});

test("insertion point follows slot midpoints", () => {
  const rects = [[0, 100], [100, 200], [200, 300]];
  assert.equal(insertionIndex(10, rects), 0);
  assert.equal(insertionIndex(60, rects), 1);
  assert.equal(insertionIndex(260, rects), 3);
});
