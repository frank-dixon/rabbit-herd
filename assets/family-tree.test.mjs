import test from "node:test";
import assert from "node:assert/strict";
import { allele, esc, label, layout, spanFor } from "./family-tree.mjs";

test("alleles get their superscripts", () => {
  assert.equal(allele("cchd"), "c<sup>chd</sup>");
  assert.equal(allele("at"), "a<sup>t</sup>");
  assert.equal(allele("b"), "b");
  assert.equal(allele(null), "?");
});

test("labels read Known, Probable % and Guess", () => {
  assert.equal(label({ level: "known" }), "Known");
  assert.equal(label({ level: "probable", pct: 75 }), "Probable 75%");
  assert.equal(label({ level: "guess", pct: 50 }), "Guess");
  assert.equal(label({ level: "unknown" }), "Unknown");
});

test("names are escaped", () => {
  assert.equal(esc('<b>"x"</b>'), "&lt;b&gt;&quot;x&quot;&lt;/b&gt;");
});

test("layout puts sire left of dam and relatives beside them", () => {
  const data = {
    places: { 1: "r1", 2: "r2", 3: "r3", 4: "o4" },
    nodes: {
      r1: {}, r2: {}, r3: {}, o4: {},
      r5: { sire: "r2", dam: "r3", lateral: { kind: "sibling", label: "Littermate", anchor: 1 } },
    },
  };
  const { items } = layout(data, 4);
  const at = (id) => items.find((it) => it.id === id);
  assert.ok(at("p2").x < at("p3").x);
  assert.equal(at("p1").x, (at("p2").x + at("p3").x) / 2);
  assert.ok(at("r5").x > at("p1").x);
  assert.deepEqual(at("r5").parents.map((p) => p.id), ["p2", "p3"]);
  assert.deepEqual(at("p2").parents.map((p) => p && p.id), ["p4", undefined]);
  assert.ok(spanFor(5) > spanFor(4));
});
