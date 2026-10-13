import { test } from "node:test";
import assert from "node:assert/strict";
import { swappable, formUrl } from "./list-swap.mjs";

const here = "https://x.test/rabbits/?tab=active";

test("swappable: only same-path query changes on a plain click", () => {
  assert.equal(swappable("?tab=former", here), true);
  assert.equal(swappable("/rabbits/12/", here), false);
  assert.equal(swappable("https://other.test/rabbits/?tab=former", here), false);
  assert.equal(swappable("?tab=active", here), false);
  assert.equal(swappable("?tab=former", here, { metaKey: true }), false);
  assert.equal(swappable("?tab=former", here, { button: 1 }), false);
  assert.equal(swappable("?tab=former", here, {}, "_blank"), false);
});

test("formUrl: drops empty fields and old query", () => {
  const url = formUrl(here, [["q", "haz"], ["breed", ""], ["view", "list"]]);
  assert.equal(url.search, "?q=haz&view=list");
});
