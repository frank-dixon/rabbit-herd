import { test } from "node:test";
import assert from "node:assert/strict";
import { moveIndex } from "./photo-step.mjs";

test("moveIndex moves one photo and keeps the rest in order", () => {
  assert.deepEqual(moveIndex(4, 3, 0), [3, 0, 1, 2]);
  assert.deepEqual(moveIndex(4, 0, 2), [1, 2, 0, 3]);
  assert.deepEqual(moveIndex(3, 1, 1), [0, 1, 2]);
  assert.deepEqual(moveIndex(3, 5, 0), [0, 1, 2]);
});
