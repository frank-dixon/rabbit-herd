// Unit tests for the card flow helpers. Run with: npm run test:js
import assert from "node:assert/strict";
import test from "node:test";

import { crossTotal, needsColorText, relationshipChoices, totalText, totalTone } from "./rabbit-flow.mjs";

const ALL = [
  ["dam", "Dam (mother)"],
  ["sire", "Sire (father)"],
  ["sibling", "Full sibling (same dam and sire)"],
];
const values = (choices) => choices.map((choice) => choice[0]);

test("the total counts whole numbers only, like the server", () => {
  assert.equal(crossTotal(["60", " 30 ", "", "12.5", "ten"]), 90);
  assert.equal(crossTotal(["-5", "50"]), 45);
});

test("the total uses the approved wording", () => {
  assert.equal(totalText(100), "Total: 100%. The mix adds up.");
  assert.equal(totalText(90), "Total so far: 90%. Add 10% more to reach 100%.");
  assert.equal(totalText(110), "Total so far: 110%. That's 10% over, so lower a share.");
  assert.deepEqual([totalTone(100), totalTone(90), totalTone(110)], ["good", "short", "over"]);
});

test("a dam or sire taken on one row leaves the other rows", () => {
  assert.deepEqual(values(relationshipChoices(ALL, ["dam", ""], 1)), ["sire", "sibling"]);
  assert.deepEqual(values(relationshipChoices(ALL, ["dam", ""], 0)), ["dam", "sire", "sibling"]);
  assert.deepEqual(values(relationshipChoices(ALL, ["dam", "sire"], 0)), ["dam", "sibling"]);
  // Changing or removing the row brings the choice back.
  assert.deepEqual(values(relationshipChoices(ALL, ["sibling", ""], 1)), ["dam", "sire", "sibling"]);
  assert.deepEqual(values(relationshipChoices(ALL, [""], 0)), ["dam", "sire", "sibling"]);
  // A row keeps a value it already holds.
  assert.deepEqual(values(relationshipChoices(ALL, ["dam", "dam"], 1)), ["dam", "sire", "sibling"]);
});

test("the color description box is needed only for Another color", () => {
  assert.equal(needsColorText("__other__", "__other__"), true);
  assert.equal(needsColorText("Creme", "__other__"), false);
  assert.equal(needsColorText("", "__other__"), false);
});
