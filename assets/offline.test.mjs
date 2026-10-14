import test from "node:test";
import assert from "node:assert/strict";
import { LEASE_KEY, QUEUE_KEY, failedEntries, flushQueue, logoutWarning, pendingEntries, queueEntry, readQueue, statusText, withSyncLock } from "./offline.mjs";

function memory() {
  const data = new Map();
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
  };
}

test("queued entries never keep the CSRF token", () => {
  const storage = memory();
  queueEntry(storage, "/rabbits/1/weights/", [["csrfmiddlewaretoken", "abc"], ["lb", "4"]], "Weight");
  const [item] = readQueue(storage);
  assert.deepEqual(item.fields.filter(([k]) => k !== "op_id"), [["lb", "4"]]);
  assert.match(item.op_id, /^[0-9a-f-]{36}$/);
  assert.equal(item.action, "/rabbits/1/weights/");
});

test("flush posts in order with a fresh token and empties the queue", async () => {
  const storage = memory();
  queueEntry(storage, "/a/", [["lb", "1"]]);
  queueEntry(storage, "/b/", [["lb", "2"]]);
  const calls = [];
  const result = await flushQueue(storage, async (url, init) => {
    calls.push([url, init.body.get("csrfmiddlewaretoken"), init.body.get("lb")]);
    return { ok: true, status: 201, url: "/rabbits/1/" };
  }, "fresh");
  assert.deepEqual(calls, [["/a/", "fresh", "1"], ["/b/", "fresh", "2"]]);
  assert.deepEqual(result, { sent: 2, failed: 0, left: 0 });
  assert.equal(storage.getItem(QUEUE_KEY), null);
});

test("flush stops at a network failure or a sign-in page and keeps the rest", async () => {
  const storage = memory();
  queueEntry(storage, "/a/", []);
  queueEntry(storage, "/b/", []);
  let n = 0;
  let result = await flushQueue(storage, async () => {
    n += 1;
    if (n === 2) throw new TypeError("offline");
    return { ok: true, url: "/x/" };
  }, "t");
  assert.deepEqual(result, { sent: 1, failed: 0, left: 1 });
  result = await flushQueue(storage, async () => ({ ok: true, url: "/accounts/login/?next=/" }), "t");
  assert.deepEqual(result, { sent: 0, failed: 0, left: 1 });
});

test("status text", () => {
  assert.equal(statusText(true, 0), "");
  assert.match(statusText(false, 0), /^You're offline\. Showing saved pages\.$/);
  assert.match(statusText(false, 2), /2 entries are saved on this device/);
  assert.match(statusText(true, 1), /Adding 1 saved entry/);
});

// Regression: the duplicate bug. Each tab flushed the same stored entries,
// so 3 tabs made 3 rows. Every send now carries the entry's op_id (the server
// applies an op_id once), and only one tab holds the sync lock.
test("every send of an entry carries the same op_id and the queue header", async () => {
  const storage = memory();
  queueEntry(storage, "/a/", [["lb", "1"], ["op_id", "11111111-1111-4111-8111-111111111111"]]);
  const seen = [];
  const fetchFn = async (url, init) => {
    seen.push([init.body.get("op_id"), init.headers["X-BB-Queue"]]);
    throw new TypeError("offline");
  };
  await flushQueue(storage, fetchFn, "t");
  await flushQueue(storage, fetchFn, "t");
  assert.deepEqual(seen, [["11111111-1111-4111-8111-111111111111", "1"], ["11111111-1111-4111-8111-111111111111", "1"]]);
  assert.equal(readQueue(storage).length, 1);
});

test("queueing the same op_id twice keeps one entry", () => {
  const storage = memory();
  const fields = [["lb", "1"], ["op_id", "22222222-2222-4222-8222-222222222222"]];
  queueEntry(storage, "/a/", fields);
  queueEntry(storage, "/a/", fields);
  assert.equal(readQueue(storage).length, 1);
});

test("three tabs flushing at once send each entry once (lease fallback)", async () => {
  const storage = memory();
  queueEntry(storage, "/a/", [["lb", "1"]]);
  queueEntry(storage, "/b/", [["lb", "2"]]);
  const posts = [];
  const fetchFn = async (url) => {
    posts.push(url);
    await new Promise((r) => setTimeout(r, 20));
    return { ok: true, status: 201, url };
  };
  const win = { navigator: {} };
  await Promise.all(["t1", "t2", "t3"].map((tab) => withSyncLock(win, storage, tab, () => flushQueue(storage, fetchFn, "x"))));
  assert.deepEqual(posts, ["/a/", "/b/"]);
  assert.equal(storage.getItem(QUEUE_KEY), null);
  assert.equal(storage.getItem(LEASE_KEY), null);
});

test("Web Locks: a tab that can't get the lock skips", async () => {
  let held = false;
  const locks = { request: async (name, opts, cb) => { if (held) return cb(null); held = true; try { return await cb({ name }); } finally { held = false; } } };
  const win = { navigator: { locks } };
  const ran = [];
  const slow = (tab) => async () => { ran.push(tab); await new Promise((r) => setTimeout(r, 10)); return tab; };
  const results = await Promise.all([withSyncLock(win, null, "a", slow("a")), withSyncLock(win, null, "b", slow("b"))]);
  assert.deepEqual(ran, ["a"]);
  assert.deepEqual(results, ["a", null]);
});

// Regression: the silent-loss bug. A form error came back as a 200 page, which
// the queue counted as sent and dropped. The server now answers 422 with the
// error; the entry stays, marked, and the next entries still go.
test("a refused entry is kept with the server's message and the rest still send", async () => {
  const storage = memory();
  queueEntry(storage, "/bad/", [["lb", "999"]], "Weight");
  queueEntry(storage, "/good/", [["lb", "4"]], "Weight");
  const result = await flushQueue(storage, async (url) => (url === "/bad/"
    ? { ok: false, status: 422, url, json: async () => ({ ok: false, error: "That weight looks off." }) }
    : { ok: true, status: 201, url }), "t");
  assert.deepEqual(result, { sent: 1, failed: 1, left: 0 });
  const [kept] = readQueue(storage);
  assert.equal(kept.action, "/bad/");
  assert.equal(kept.error, "That weight looks off.");
  // A refused entry is not re-sent on its own.
  let calls = 0;
  await flushQueue(storage, async () => { calls += 1; return { ok: true, status: 201 }; }, "t");
  assert.equal(calls, 0);
  assert.equal(failedEntries(storage).length, 1);
});

test("a server error stops the flush and keeps everything", async () => {
  const storage = memory();
  queueEntry(storage, "/a/", []);
  const result = await flushQueue(storage, async () => ({ ok: false, status: 503, url: "/a/" }), "t");
  assert.deepEqual(result, { sent: 0, failed: 0, left: 1 });
  assert.equal(readQueue(storage)[0].error, "");
});

test("entries are sent only for the account that kept them", async () => {
  const storage = memory();
  queueEntry(storage, "/a/", [], "Weight", "1");
  queueEntry(storage, "/b/", [], "Weight", "2");
  const posts = [];
  await flushQueue(storage, async (url) => { posts.push(url); return { ok: true, status: 201 }; }, "t", "2");
  assert.deepEqual(posts, ["/b/"]);
  assert.equal(pendingEntries(storage, "1").length, 1);
});

test("logout warning counts kept entries", () => {
  assert.equal(logoutWarning(0, 0), "");
  assert.match(logoutWarning(1, 0), /^1 entry hasn't been added yet\. It stays on this device/);
  assert.match(logoutWarning(2, 1), /^3 entries haven't/);
});

test("status after sending says to refresh instead of reloading", () => {
  assert.equal(statusText(true, 0, 0, 2), "Added 2 saved entries. Refresh to see them.");
  assert.match(statusText(true, 0, 1, 0), /1 saved entry needs a fix/);
});
