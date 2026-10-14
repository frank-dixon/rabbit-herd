/*
 * Offline use.
 *
 * Registers the service worker, shows a status line while the device is
 * offline, and lets forms marked data-offline-queue (add a weight, add a
 * health note) be kept on the device while offline. Kept entries are posted
 * in order once the device is back online, with a fresh CSRF token from the
 * page doing the sending; the token is never stored with the entry.
 *
 * Every entry carries a client-made op_id; the server applies an op_id once,
 * so a retry or a second tab can never add the same entry twice. Only one tab
 * sends at a time (Web Locks, or a short localStorage lease where those are
 * missing). An entry the server refuses (422, with the form error) is kept
 * and shown with that error; nothing is dropped without the user saying so.
 * Logging out never deletes kept entries, and sending never reloads the page.
 */

export const QUEUE_KEY = "bb-offline-queue";
export const LEASE_KEY = "bb-offline-lease";
export const LOCK_NAME = "bb-offline-sync";

export function newOpId(cryptoObj = globalThis.crypto) {
  if (cryptoObj && typeof cryptoObj.randomUUID === "function") {
    return cryptoObj.randomUUID();
  }
  const bytes = new Uint8Array(16);
  if (cryptoObj && cryptoObj.getRandomValues) {
    cryptoObj.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function readQueue(storage) {
  try {
    const items = JSON.parse(storage.getItem(QUEUE_KEY) || "[]");
    return Array.isArray(items) ? items : [];
  } catch (error) {
    return [];
  }
}

function writeQueue(storage, items) {
  if (items.length) {
    storage.setItem(QUEUE_KEY, JSON.stringify(items));
  } else {
    storage.removeItem(QUEUE_KEY);
  }
}

/** Change one entry (by op_id) in the stored queue, re-read so other tabs' additions survive. */
function updateEntry(storage, opId, change) {
  const items = readQueue(storage);
  const index = items.findIndex((item) => item.op_id === opId);
  if (index === -1) return;
  const next = change(items[index]);
  if (next) {
    items[index] = next;
  } else {
    items.splice(index, 1);
  }
  writeQueue(storage, items);
}

function fieldValue(fields, name) {
  const pair = fields.find(([key]) => key === name);
  return pair ? pair[1] : "";
}

/**
 * Keep one form submission. fields is a list of [name, value] pairs. The
 * entry keeps the form's op_id (or gets one) so every send of it is the
 * same operation to the server.
 */
export function queueEntry(storage, action, fields, label, user = "") {
  const opId = fieldValue(fields, "op_id") || newOpId();
  const kept = fields.filter(([name]) => name !== "csrfmiddlewaretoken" && name !== "op_id");
  kept.push(["op_id", opId]);
  const items = readQueue(storage);
  if (!items.some((item) => item.op_id === opId)) {
    items.push({ op_id: opId, action, fields: kept, label: label || "", user: String(user || ""), at: new Date().toISOString(), error: "" });
  }
  writeQueue(storage, items);
  return items.length;
}

function mine(item, user) {
  return !user || !item.user || item.user === String(user);
}

/** Entries waiting to send for this user (not the ones held with an error). */
export function pendingEntries(storage, user = "") {
  return readQueue(storage).filter((item) => mine(item, user) && !item.error);
}

export function failedEntries(storage, user = "") {
  return readQueue(storage).filter((item) => mine(item, user) && item.error);
}

async function errorText(response) {
  try {
    const data = await response.json();
    if (data && data.error) return String(data.error);
  } catch (error) {
    // not JSON
  }
  if (response.status === 404) return "The rabbit for this entry isn't in your herd any more.";
  return `The server refused this entry (error ${response.status}).`;
}

/**
 * Post this user's kept entries in order. Stops at the first network failure,
 * server error or sign-in page and keeps that entry and the ones after it. An
 * entry the server refuses (4xx) is kept with the server's message and skipped
 * until the user retries or discards it.
 */
export async function flushQueue(storage, fetchFn, token, user = "") {
  let sent = 0;
  let failed = 0;
  const tried = new Set();
  for (;;) {
    const item = pendingEntries(storage, user).find((entry) => !tried.has(entry.op_id || ""));
    if (!item) break;
    if (!item.op_id) {
      // Entries kept before op_ids existed get one now, before their first send.
      const legacy = readQueue(storage);
      const index = legacy.findIndex((entry) => !entry.op_id && entry.at === item.at && entry.action === item.action);
      item.op_id = newOpId();
      item.fields = [...item.fields.filter(([name]) => name !== "op_id"), ["op_id", item.op_id]];
      if (index !== -1) legacy[index] = item;
      writeQueue(storage, legacy);
    }
    tried.add(item.op_id);
    const body = new URLSearchParams(item.fields);
    body.set("csrfmiddlewaretoken", token);
    let response;
    try {
      response = await fetchFn(item.action, {
        method: "POST",
        body,
        credentials: "same-origin",
        headers: { "X-CSRFToken": token, "X-BB-Queue": "1", Accept: "application/json" },
      });
    } catch (error) {
      break;
    }
    if (String(response.url || "").match(/\/(accounts\/)?login\//) || response.status === 401 || response.status === 403) {
      break;
    }
    if (response.ok) {
      updateEntry(storage, item.op_id, () => null);
      sent += 1;
      continue;
    }
    if (response.status >= 400 && response.status < 500) {
      const message = await errorText(response);
      updateEntry(storage, item.op_id, (entry) => ({ ...entry, error: message }));
      failed += 1;
      continue;
    }
    break;
  }
  return { sent, failed, left: pendingEntries(storage, user).length };
}

/**
 * Run fn in one tab only. Another tab already sending means this one skips;
 * that tab re-reads the queue as it goes, so it picks up new entries too.
 */
export async function withSyncLock(win, storage, tabId, fn) {
  const locks = win.navigator && win.navigator.locks;
  if (locks && typeof locks.request === "function") {
    return locks.request(LOCK_NAME, { ifAvailable: true }, (lock) => (lock ? fn() : null));
  }
  const now = Date.now();
  let lease = null;
  try {
    lease = JSON.parse(storage.getItem(LEASE_KEY) || "null");
  } catch (error) {
    lease = null;
  }
  if (lease && lease.until > now && lease.tab !== tabId) return null;
  storage.setItem(LEASE_KEY, JSON.stringify({ tab: tabId, until: now + 30000 }));
  await new Promise((resolve) => setTimeout(resolve, 50));
  try {
    if (JSON.parse(storage.getItem(LEASE_KEY) || "null")?.tab !== tabId) return null;
  } catch (error) {
    return null;
  }
  try {
    return await fn();
  } finally {
    storage.removeItem(LEASE_KEY);
  }
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

export function statusText(online, pending, failed = 0, sent = 0) {
  const kept = pending ? ` ${plural(pending, "entry is", "entries are")} saved on this device and will be added when you're back online.` : "";
  const held = failed ? ` ${plural(failed, "saved entry needs", "saved entries need")} a fix before it can be added.` : "";
  if (!online) {
    return `You're offline. Showing saved pages.${kept}${held}`;
  }
  if (pending) {
    return `Back online. Adding ${plural(pending, "saved entry", "saved entries")}…${held}`;
  }
  const done = sent ? `Added ${plural(sent, "saved entry", "saved entries")}. Refresh to see ${sent === 1 ? "it" : "them"}.` : "";
  return `${done}${held}`.trim();
}

export function logoutWarning(pending, failed) {
  const total = pending + failed;
  if (!total) return "";
  return `${plural(total, "entry hasn't", "entries haven't")} been added yet. ${total === 1 ? "It stays" : "They stay"} on this device and will be added the next time you sign in here. Sign out anyway?`;
}

function describe(item) {
  const day = fieldValue(item.fields, "date") || fieldValue(item.fields, "health_date") || (item.at || "").slice(0, 10);
  return `${item.label || "Entry"}${day ? ` for ${day}` : ""}`;
}

export function bindOffline(doc, win) {
  const nav = win.navigator;
  const storage = win.localStorage;
  if ("serviceWorker" in nav && win.isSecureContext) {
    nav.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => null);
  }
  const tabId = newOpId(win.crypto);
  const status = doc.querySelector("[data-connection-status]");
  const meta = (name) => {
    const tag = doc.querySelector(`meta[name="${name}"]`);
    return tag ? tag.getAttribute("content") || "" : "";
  };
  const token = () => meta("csrf-token");
  const user = () => meta("bb-user");
  let lastSent = 0;
  let errorsBox = null;

  function renderErrors() {
    const failed = failedEntries(storage, user());
    if (!failed.length) {
      if (errorsBox) errorsBox.hidden = true;
      return;
    }
    if (!errorsBox) {
      errorsBox = doc.createElement("div");
      errorsBox.className = "net-banner net-errors";
      errorsBox.setAttribute("role", "alert");
      errorsBox.setAttribute("data-sync-errors", "");
      if (status && status.parentNode) {
        status.parentNode.insertBefore(errorsBox, status.nextSibling);
      } else {
        doc.body.prepend(errorsBox);
      }
    }
    errorsBox.hidden = false;
    errorsBox.replaceChildren();
    const heading = doc.createElement("p");
    heading.textContent = `${plural(failed.length, "saved entry wasn't", "saved entries weren't")} added. ${failed.length === 1 ? "It's" : "They're"} still on this device.`;
    errorsBox.append(heading);
    const list = doc.createElement("ul");
    failed.forEach((item) => {
      const row = doc.createElement("li");
      row.setAttribute("data-sync-error", item.op_id);
      const text = doc.createElement("span");
      text.textContent = `${describe(item)}: ${item.error} `;
      const retry = doc.createElement("button");
      retry.type = "button";
      retry.textContent = "Try again";
      retry.addEventListener("click", () => {
        updateEntry(storage, item.op_id, (entry) => ({ ...entry, error: "" }));
        render();
        flush();
      });
      const discard = doc.createElement("button");
      discard.type = "button";
      discard.textContent = "Discard";
      discard.addEventListener("click", () => {
        if (win.confirm(`Discard ${describe(item).toLowerCase()}? It won't be added.`)) {
          updateEntry(storage, item.op_id, () => null);
          render();
        }
      });
      row.append(text, retry, " ", discard);
      list.append(row);
    });
    errorsBox.append(list);
  }

  function render() {
    renderErrors();
    if (!status) return;
    const text = statusText(nav.onLine, pendingEntries(storage, user()).length, failedEntries(storage, user()).length, lastSent);
    status.textContent = text;
    status.hidden = !text;
  }

  async function flush() {
    if (!nav.onLine || !pendingEntries(storage, user()).length || !token()) {
      return;
    }
    render();
    const result = await withSyncLock(win, storage, tabId, () => flushQueue(storage, win.fetch.bind(win), token(), user()));
    if (result && result.sent) {
      // No reload: what's on screen (and anything being typed) stays put.
      lastSent = result.sent;
      win.setTimeout(() => {
        lastSent = 0;
        render();
      }, 10000);
    }
    render();
  }

  const freshOp = (form) => {
    const input = form.querySelector('input[name="op_id"]');
    if (input) input.value = newOpId(win.crypto);
  };
  doc.querySelectorAll("form[data-offline-queue]").forEach((form) => {
    if (!form.querySelector('input[name="op_id"]')) {
      const input = doc.createElement("input");
      input.type = "hidden";
      input.name = "op_id";
      form.append(input);
    }
    freshOp(form);
    form.addEventListener("submit", (event) => {
      if (nav.onLine) {
        return; // the op_id rides along, so a double submit adds one entry
      }
      event.preventDefault();
      // Photos can't wait on the device; the note itself is queued without them.
      const fields = Array.from(new FormData(form).entries()).filter(([, value]) => typeof value === "string").map(([name, value]) => [name, value]);
      queueEntry(storage, form.action, fields, form.getAttribute("data-offline-queue"), user());
      freshOp(form);
      const note = form.querySelector("[data-offline-note]");
      if (note) {
        note.hidden = false;
        note.textContent = `${form.getAttribute("data-offline-queue")} saved on this device. It will be added when you're back online.`;
      }
      form.querySelectorAll("input:not([type=hidden]):not([type=date]), textarea").forEach((input) => {
        input.value = "";
      });
      render();
    });
  });
  doc.querySelectorAll('form[action$="/logout/"]').forEach((form) => {
    form.addEventListener("submit", (event) => {
      const warning = logoutWarning(pendingEntries(storage, user()).length, failedEntries(storage, user()).length);
      if (warning && !win.confirm(warning)) {
        event.preventDefault();
        return;
      }
      // Kept entries stay (they're tagged with this account and only sent for it).
      if (nav.serviceWorker && nav.serviceWorker.controller) {
        nav.serviceWorker.controller.postMessage("clear-private");
      }
    });
  });
  win.addEventListener("storage", (event) => {
    if (event.key === QUEUE_KEY || event.key === null) render();
  });
  win.addEventListener("online", () => {
    render();
    flush();
  });
  win.addEventListener("offline", render);
  render();
  flush();
}
