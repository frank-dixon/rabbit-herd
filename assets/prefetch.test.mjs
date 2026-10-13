import test from "node:test";
import assert from "node:assert/strict";
import { prefetchable } from "./prefetch.mjs";

const loc = new URL("https://app.example/rabbits/");
const a = (href, attrs = {}) => ({ href, target: attrs.target || "", hasAttribute: (n) => n in attrs, closest: () => null });

test("same-origin page links are prefetched without their hash", () => {
  assert.equal(prefetchable(a("https://app.example/rabbits/3/#weights"), loc), "https://app.example/rabbits/3/");
});

test("skips other origins, the current page, sign-out, downloads and photo files", () => {
  assert.equal(prefetchable(a("https://other.example/"), loc), null);
  assert.equal(prefetchable(a("https://app.example/rabbits/#top"), loc), null);
  assert.equal(prefetchable(a("https://app.example/accounts/logout/"), loc), null);
  assert.equal(prefetchable(a("https://app.example/rabbits/photos/4/"), loc), null);
  assert.equal(prefetchable(a("https://app.example/export/", { download: "" }), loc), null);
  assert.equal(prefetchable(a("https://app.example/rabbits/2/", { target: "_blank" }), loc), null);
});
