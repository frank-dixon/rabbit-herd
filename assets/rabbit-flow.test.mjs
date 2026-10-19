// Unit tests for the card flow helpers. Run with: npm run test:js
import assert from "node:assert/strict";
import test from "node:test";

import { autoText, breedSection, crossTotal, needsColorText, parseAuto, refillGenes, relationshipChoices, revealInvalid, totalText, totalTone } from "./rabbit-flow.mjs";

const ALL = [
  ["dam", "Dam (mother)"],
  ["sire", "Sire (father)"],
  ["sibling", "Full sibling (same dam and sire)"],
];
const values = (choices) => choices.map((choice) => choice[0]);

test("the total counts plain numbers, fractions included, like the server", () => {
  assert.equal(crossTotal(["60", " 30 ", "", "12.5", "ten"]), 102.5);
  assert.equal(crossTotal(["75", "12.5", "12.5"]), 100);
  assert.equal(crossTotal(["33.33", "33.33", "33.34"]), 100);
  assert.equal(totalText(crossTotal(["75", "12.5", "12.49"])), "Total so far: 99.99%. Add 0.01% more to reach 100%.");
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

test("gene refill fills empty and still-filled loci, never ones set by hand", () => {
  const result = refillGenes({ A: "", B: "Bb", C: "C_", D: "" }, { C: "C_" }, { A: "aa", B: "B_", C: "cc" });
  assert.deepEqual(result.values, { A: "aa", B: "Bb", C: "cc", D: "" });
  assert.deepEqual(result.auto, { A: "aa", C: "cc" });
});

test("a filled locus the new color no longer proves is cleared", () => {
  const result = refillGenes({ A: "aa" }, { A: "aa" }, {});
  assert.deepEqual(result.values, { A: "" });
  assert.deepEqual(result.auto, {});
});

test("gene_auto round-trips", () => {
  assert.deepEqual(parseAuto("A=aa;En=enen"), { A: "aa", En: "enen" });
  assert.equal(autoText({ En: "enen", A: "aa" }, ["A", "B", "En"]), "A=aa;En=enen");
});

test("breed type picks the breed section shown on the same card", () => {
  assert.equal(breedSection("purebred"), "purebred");
  assert.equal(breedSection("crossbred"), "crossbred");
  assert.equal(breedSection(""), "");
  assert.equal(breedSection("Unknown"), "");
});

test("a failed submit focuses the first visible invalid field and brings its message into view (Critic v7 O2)", () => {
  const calls = [];
  const el = (name, shown, attrs = {}) => ({
    name, getClientRects: () => (shown ? [{}] : []), getAttribute: (k) => attrs[k] ?? null,
    focus: (o) => calls.push([name, "focus", o.preventScroll]), scrollIntoView: (o) => calls.push([name, "scroll", o.block]),
  });
  const hidden = el("hidden-select", false);
  const field = el("purebred", true, { "aria-describedby": "id_purebred_help id_purebred_error" });
  const message = el("message", true);
  const form = { querySelectorAll: () => [hidden, field] };
  const doc = { getElementById: (id) => (id === "id_purebred_error" ? message : null) };
  assert.equal(revealInvalid(form, doc), field);
  assert.deepEqual(calls, [["purebred", "focus", true], ["purebred", "scroll", "nearest"], ["message", "scroll", "nearest"]]);
  assert.equal(revealInvalid({ querySelectorAll: () => [] }, doc), null);
});
