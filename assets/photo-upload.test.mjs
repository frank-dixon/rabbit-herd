// Unit tests for the photo shrinking helpers. Run with: npm run test:js
import assert from "node:assert/strict";
import test from "node:test";

import { MAX_UPLOAD_BYTES, fitWithin, needsShrink } from "./photo-upload.mjs";

test("a big photo fits inside 2560 pixels and keeps its shape", () => {
  assert.deepEqual(fitWithin(4032, 3024), { width: 2560, height: 1920 });
  assert.deepEqual(fitWithin(3024, 4032), { width: 1920, height: 2560 });
});

test("a small photo keeps its size", () => {
  assert.deepEqual(fitWithin(1200, 800), { width: 1200, height: 800 });
});

test("photos are redrawn when too wide or too heavy", () => {
  assert.equal(needsShrink(4032, 3024, 1000), true);
  assert.equal(needsShrink(2000, 1500, MAX_UPLOAD_BYTES + 1), true);
  assert.equal(needsShrink(2000, 1500, 1000), false);
});

test("the limit stays under Vercel's 4.5 MB request cap", () => {
  assert.ok(MAX_UPLOAD_BYTES < 4.5 * 1024 * 1024);
});
