import test from "node:test";
import assert from "node:assert/strict";
import { QUEUE_KEY, flushQueue, queueEntry, readQueue, statusText } from "./offline.mjs";

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
  assert.deepEqual(item.fields, [["lb", "4"]]);
  assert.equal(item.action, "/rabbits/1/weights/");
});

test("flush posts in order with a fresh token and empties the queue", async () => {
  const storage = memory();
  queueEntry(storage, "/a/", [["lb", "1"]]);
  queueEntry(storage, "/b/", [["lb", "2"]]);
  const calls = [];
  const result = await flushQueue(storage, async (url, init) => {
    calls.push([url, init.body.get("csrfmiddlewaretoken"), init.body.get("lb")]);
    return { ok: true, url: "/rabbits/1/" };
  }, "fresh");
  assert.deepEqual(calls, [["/a/", "fresh", "1"], ["/b/", "fresh", "2"]]);
  assert.deepEqual(result, { sent: 2, left: 0 });
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
  assert.deepEqual(result, { sent: 1, left: 1 });
  result = await flushQueue(storage, async () => ({ ok: true, url: "/accounts/login/?next=/" }), "t");
  assert.deepEqual(result, { sent: 0, left: 1 });
});

test("status text", () => {
  assert.equal(statusText(true, 0), "");
  assert.match(statusText(false, 0), /^You're offline\. Showing saved pages\.$/);
  assert.match(statusText(false, 2), /2 entries are saved on this device/);
  assert.match(statusText(true, 1), /Adding 1 saved entry/);
});
