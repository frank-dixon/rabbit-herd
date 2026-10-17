/*
 * Stacked litter cards on the Rabbits list. A [data-litter-toggle="key"] button
 * shows or hides every [data-litter-of="key"] element (the grid's kit band, or the
 * list's kit rows) with no reload. Open stacks are remembered in localStorage.
 * A search or filter renders stacks open (aria-expanded="true"); the saved state
 * does not close them then.
 */
export const STORE_KEY = "bb-litter-open";

export function readOpen(storage) {
  try {
    const list = JSON.parse(storage?.getItem(STORE_KEY) || "[]");
    return new Set(Array.isArray(list) ? list : []);
  } catch {
    return new Set();
  }
}

function writeOpen(storage, set) {
  try {
    storage?.setItem(STORE_KEY, JSON.stringify([...set].slice(-200)));
  } catch {
    /* private mode or full storage: the toggle still works for this page */
  }
}

export function setOpen(root, key, open) {
  const sel = (attr) => `[${attr}="${key.replace(/"/g, "")}"]`;
  root.querySelectorAll(sel("data-litter-of")).forEach((el) => { el.hidden = !open; });
  root.querySelectorAll(sel("data-litter-toggle")).forEach((btn) => btn.setAttribute("aria-expanded", String(open)));
}

export function applySaved(root, storage) {
  const saved = readOpen(storage);
  root.querySelectorAll("[data-litter-stack]").forEach((stack) => {
    const key = stack.dataset.litterStack;
    const btn = stack.querySelector("[data-litter-toggle]");
    if (btn?.getAttribute("aria-expanded") === "true") return; // a search or filter opened it
    if (saved.has(key)) setOpen(root, key, true);
  });
}

export function bindLitterStacks(doc, win) {
  const storage = (() => { try { return win.localStorage; } catch { return null; } })();
  doc.addEventListener("click", (event) => {
    const btn = event.target.closest?.("[data-litter-toggle]");
    if (!btn) return;
    event.preventDefault();
    const key = btn.dataset.litterToggle;
    const open = btn.getAttribute("aria-expanded") !== "true";
    setOpen(doc, key, open);
    const saved = readOpen(storage);
    if (open) saved.add(key); else saved.delete(key);
    writeOpen(storage, saved);
    if (!open) doc.querySelector(`[data-litter-stack="${key}"] [data-litter-toggle]`)?.focus({ preventScroll: true });
  });
  applySaved(doc, storage);
  doc.addEventListener("list-swap:done", () => applySaved(doc, storage));
}
