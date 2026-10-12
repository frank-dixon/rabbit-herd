import { test } from "node:test";
import assert from "node:assert/strict";
import { phraseMatches } from "./delete-dialog.mjs";

test("matches case-insensitively with spaces trimmed", () => {
  assert.ok(phraseMatches("  Delete   speedwell ", "delete Speedwell"));
  assert.ok(phraseMatches("DELETE SPEEDWELL", "delete Speedwell"));
});

test("rejects partial or different text", () => {
  assert.ok(!phraseMatches("delete Speed", "delete Speedwell"));
  assert.ok(!phraseMatches("Speedwell", "delete Speedwell"));
  assert.ok(!phraseMatches("", "delete Speedwell"));
});
