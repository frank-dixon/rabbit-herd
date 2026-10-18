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

test("phone view fits a generation and its parents between the nav and the zoom strip", async () => {
  const { layout, phoneView } = await import("./family-tree.mjs");
  const places = { 1: "a", 2: "b", 3: "c", 4: "d", 5: "e", 6: "f", 7: "g" };
  const nodes = Object.fromEntries(Object.values(places).map((k) => [k, { name: k }]));
  const { items } = layout({ places, nodes }, 4);
  for (const g of [0, 1]) {
    const v = phoneView(items, g, 3, 390, 584, { top: 48, bottom: 56 });
    const rows = items.filter((it) => it.num && it.gen >= g && it.gen <= g + 1);
    for (const it of rows) {
      const left = v.x + (it.x - it.s / 2) * v.k, right = v.x + (it.x + it.s / 2) * v.k;
      assert.ok(left >= 0 && right <= 390, `gen ${it.gen} node inside the width`);
    }
    const top = v.y + (24 + g * 184) * v.k, bottom = v.y + (24 + (g + 2) * 184) * v.k;
    assert.ok(Math.abs(top - 48) < 0.5, "starts right under the nav, no empty band");
    assert.ok(bottom <= 584 - 56 + 0.5, "ends above the zoom strip");
  }
});
