/*
 * Rabbit page: simple facts (line, birth date, tattoo) edit in place. Each row is
 * a link to the one-card edit page, so without JS it still works; with JS the row
 * turns into a field with Save and Cancel. Enter saves, Esc cancels. The saved
 * facts are re-read from the page so the formatting matches the server's.
 */
import { enter, focusSmooth } from "./motion.mjs";

export function bindRabbitInline(root, win = window) {
  const facts = root.querySelector("[data-facts]");
  if (!facts) return;
  facts.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-inline-name]");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    open(link);
  });

  function close(row, form) {
    form.remove();
    row.querySelector("[data-fact-value]").hidden = false;
    delete row.dataset.editing;
    row.querySelector("a[data-fact-edit]").focus({ preventScroll: true });
  }

  function open(link) {
    const row = link.closest("[data-fact]");
    if (row.dataset.editing) return;
    facts.querySelectorAll("[data-fact][data-editing] [data-inline-cancel]").forEach((b) => b.click());
    row.dataset.editing = "";
    const value = row.querySelector("[data-fact-value]");
    value.hidden = true;
    const id = `inline-${link.dataset.inlineName}`;
    const form = root.createElement("form");
    form.method = "post";
    form.action = link.getAttribute("href");
    form.noValidate = true;
    form.className = "relative z-[2] flex flex-col gap-2";
    form.innerHTML = `
      <label class="sr-only" for="${id}"></label>
      <input id="${id}" class="h-10 w-full rounded-md border border-accent bg-surface px-3 text-ink shadow-[0_0_0_3px_var(--color-accent-soft,transparent)] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" autocomplete="off">
      <p class="hidden text-sm text-danger" role="alert" data-inline-error></p>
      <div class="flex flex-wrap items-center gap-2">
        <button type="submit" class="mo-press inline-flex min-h-9 items-center rounded-md bg-accent px-3 text-sm font-semibold text-on-accent hover:bg-accent/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2">Save</button>
        <button type="button" class="mo-press inline-flex min-h-9 items-center rounded-md px-3 text-sm text-ink hover:bg-side focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" data-inline-cancel>Cancel</button>
        <span class="hidden text-xs text-muted md:inline"><kbd class="rounded border border-line px-1 font-mono">Enter</kbd> save · <kbd class="rounded border border-line px-1 font-mono">Esc</kbd> cancel</span>
      </div>`;
    const input = form.querySelector("input");
    form.querySelector("label").textContent = link.dataset.inlineLabel || "";
    input.name = link.dataset.inlineName;
    input.type = link.dataset.inlineType || "text";
    input.value = link.dataset.inlineValue || "";
    if (input.type === "date") input.max = new Date().toISOString().slice(0, 10);
    const error = form.querySelector("[data-inline-error]");
    error.id = `${id}-error`;
    value.after(form);
    enter(form);
    focusSmooth(input, win);
    if (input.type === "text") input.select();

    form.querySelector("[data-inline-cancel]").addEventListener("click", () => close(row, form));
    form.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { event.preventDefault(); close(row, form); }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const body = new FormData();
      body.append("csrfmiddlewaretoken", root.querySelector('meta[name="csrf-token"]')?.content || "");
      body.append("action", "next");
      body.append(input.name, input.value);
      form.setAttribute("aria-busy", "true");
      try {
        const response = await win.fetch(form.action, {
          method: "POST", body, credentials: "same-origin",
          headers: { "X-Requested-With": "fetch", "X-CSRFToken": body.get("csrfmiddlewaretoken") },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.saved) {
          const errors = data.errors || {};
          const text = (errors[input.name] || errors.__all__ || ["That didn't save. Try again."]).join(" ");
          error.textContent = text;
          error.classList.remove("hidden");
          input.setAttribute("aria-invalid", "true");
          input.setAttribute("aria-describedby", error.id);
          input.focus();
          return;
        }
        await refresh(row.dataset.fact);
      } catch {
        win.location.assign(form.action);
      } finally {
        form.removeAttribute("aria-busy");
      }
    });
  }

  async function refresh(slug) {
    const response = await win.fetch(win.location.pathname, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } });
    const page = new win.DOMParser().parseFromString(await response.text(), "text/html");
    const fresh = page.querySelector("[data-facts]");
    if (!fresh) { win.location.reload(); return; }
    facts.innerHTML = fresh.innerHTML;
    const header = page.querySelector("[data-page-header]");
    const current = root.querySelector("[data-page-header]");
    if (header && current) current.replaceWith(header);
    const row = facts.querySelector(`[data-fact="${slug}"]`);
    if (row) {
      row.classList.add("mo-enter");
      row.querySelector("a[data-fact-edit]")?.focus({ preventScroll: true });
    }
    const status = root.querySelector("[data-facts-status]");
    if (status) status.textContent = "Saved";
  }
}
