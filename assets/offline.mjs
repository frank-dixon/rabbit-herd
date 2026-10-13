/*
 * Offline use.
 *
 * Registers the service worker, shows a status line while the device is
 * offline, and lets forms marked data-offline-queue (add a weight, add a
 * health note) be kept on the device while offline. Kept entries are posted
 * in order once the device is back online, with a fresh CSRF token from the
 * page doing the sending; the token is never stored with the entry.
 */

export const QUEUE_KEY = "bb-offline-queue";

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

/** Keep one form submission. fields is a list of [name, value] pairs. */
export function queueEntry(storage, action, fields, label) {
  const kept = fields.filter(([name]) => name !== "csrfmiddlewaretoken");
  const items = readQueue(storage);
  items.push({ action, fields: kept, label: label || "", at: new Date().toISOString() });
  writeQueue(storage, items);
  return items.length;
}

/**
 * Post kept entries in order. Stops at the first network failure and keeps
 * that entry and the ones after it. A response that lands on the sign-in
 * page means the session ended, so the entries stay for later as well.
 */
export async function flushQueue(storage, fetchFn, token) {
  const items = readQueue(storage);
  let sent = 0;
  while (items.length) {
    const item = items[0];
    const body = new URLSearchParams(item.fields);
    body.set("csrfmiddlewaretoken", token);
    let response;
    try {
      response = await fetchFn(item.action, {
        method: "POST",
        body,
        credentials: "same-origin",
        headers: { "X-CSRFToken": token },
      });
    } catch (error) {
      break;
    }
    if (!response.ok || String(response.url || "").includes("/accounts/login/")) {
      break;
    }
    items.shift();
    sent += 1;
    writeQueue(storage, items);
  }
  return { sent, left: items.length };
}

export function statusText(online, pending) {
  const kept = pending ? ` ${pending} ${pending === 1 ? "entry is" : "entries are"} saved on this device and will be added when you're back online.` : "";
  if (!online) {
    return `You're offline. Showing saved pages.${kept}`;
  }
  return pending ? `Back online. Adding ${pending} saved ${pending === 1 ? "entry" : "entries"}…` : "";
}

export function bindOffline(doc, win) {
  const nav = win.navigator;
  const storage = win.localStorage;
  if ("serviceWorker" in nav && win.isSecureContext) {
    nav.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => null);
  }
  const status = doc.querySelector("[data-connection-status]");
  const token = () => {
    const meta = doc.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") || "" : "";
  };
  function render() {
    if (!status) {
      return;
    }
    const text = statusText(nav.onLine, readQueue(storage).length);
    status.textContent = text;
    status.hidden = !text;
  }
  let flushing = false;
  async function flush() {
    if (flushing || !nav.onLine || !readQueue(storage).length || !token()) {
      return;
    }
    flushing = true;
    render();
    const result = await flushQueue(storage, win.fetch.bind(win), token());
    flushing = false;
    render();
    if (result.sent && !result.left) {
      win.location.reload();
    }
  }
  doc.querySelectorAll("form[data-offline-queue]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (nav.onLine) {
        return;
      }
      event.preventDefault();
      const fields = Array.from(new FormData(form).entries()).map(([name, value]) => [name, String(value)]);
      queueEntry(storage, form.action, fields, form.getAttribute("data-offline-queue"));
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
  doc.querySelectorAll('form[action$="/accounts/logout/"]').forEach((form) => {
    form.addEventListener("submit", () => {
      storage.removeItem(QUEUE_KEY);
      if (nav.serviceWorker && nav.serviceWorker.controller) {
        nav.serviceWorker.controller.postMessage("clear-private");
      }
    });
  });
  win.addEventListener("online", () => {
    render();
    flush();
  });
  win.addEventListener("offline", render);
  render();
  flush();
}
