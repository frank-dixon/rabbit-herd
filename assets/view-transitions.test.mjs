import { test } from "node:test";
import assert from "node:assert/strict";
import { quiet, startQuiet, bindQuietTransitions } from "./view-transitions.mjs";

const aborted = () => {
  const reject = () => Promise.reject(new Error("Transition was aborted because of invalid state"));
  return { ready: reject(), finished: reject(), updateCallbackDone: Promise.resolve() };
};

test("an aborted transition's promises are handled", async () => {
  const seen = [];
  const onUnhandled = (reason) => seen.push(reason);
  process.on("unhandledRejection", onUnhandled);
  quiet(aborted());
  startQuiet({ startViewTransition: () => aborted() }, () => {});
  await new Promise((r) => setTimeout(r, 20));
  process.off("unhandledRejection", onUnhandled);
  assert.deepEqual(seen, []);
  assert.equal(quiet(null), null);
});

test("page-to-page transitions are quieted on both sides", () => {
  const events = {};
  bindQuietTransitions({ addEventListener: (name, fn) => { events[name] = fn; } });
  assert.deepEqual(Object.keys(events).sort(), ["pagereveal", "pageswap"]);
  events.pagereveal({ viewTransition: null });
  events.pageswap({ viewTransition: aborted() });
});
