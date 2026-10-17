import { test } from "node:test";
import assert from "node:assert/strict";
import { readOpen, STORE_KEY } from "./litter-stack.mjs";

const store = (v) => ({ getItem: (k) => (k === STORE_KEY ? v : null) });

test("readOpen tolerates missing, bad and valid storage", () => {
  assert.equal(readOpen(null).size, 0);
  assert.equal(readOpen(store("not json")).size, 0);
  assert.equal(readOpen(store('{"a":1}')).size, 0);
  assert.deepEqual([...readOpen(store('["l4","p1"]'))], ["l4", "p1"]);
});
