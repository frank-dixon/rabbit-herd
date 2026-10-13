import test from "node:test";
import assert from "node:assert/strict";
import { MAX_PULL, THRESHOLD, pullDistance } from "./ptr.mjs";

test("pull resists past the threshold and caps", () => {
  assert.equal(pullDistance(-10), 0);
  assert.equal(pullDistance(50), 30);
  assert.ok(pullDistance(THRESHOLD + 40) - pullDistance(THRESHOLD) < 40 * 0.6);
  assert.equal(pullDistance(5000), MAX_PULL);
});
