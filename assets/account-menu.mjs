/*
 * Sidebar account menu: the gear opens a menu upward. Esc or a click outside
 * closes it; arrow keys move between items. Without JS the gear opens Settings.
 * Bound for each footer (side menu and phone drawer).
 */

export function bindAccountMenu(doc) {
  doc.querySelectorAll("[data-account-menu]").forEach((root) => bindOne(doc, root));
}

function bindOne(doc, root) {
  const button = root.querySelector("[data-account-button]");
  const pop = root.querySelector("[data-account-pop]");
  const items = () => [...pop.querySelectorAll('[role="menuitem"]')];
  let open = false;
  const show = (focusFirst) => {
    open = true; pop.hidden = false; pop.classList.remove("is-leaving");
    button.setAttribute("aria-expanded", "true");
    if (focusFirst) items()[0]?.focus();
  };
  const hide = async (refocus) => {
    if (!open) return;
    open = false; button.setAttribute("aria-expanded", "false");
    if (refocus) button.focus();
    pop.classList.add("is-leaving");
    await new Promise((r) => setTimeout(r, 140));
    if (!open) { pop.hidden = true; pop.classList.remove("is-leaving"); }
  };
  button.addEventListener("click", (event) => { event.preventDefault(); open ? hide(false) : show(event.detail === 0); });
  button.addEventListener("keydown", (event) => {
    if (event.key === "ArrowUp" || event.key === "ArrowDown") { event.preventDefault(); show(true); }
  });
  pop.addEventListener("keydown", (event) => {
    const list = items(); const i = list.indexOf(doc.activeElement);
    if (event.key === "ArrowDown") { event.preventDefault(); list[(i + 1) % list.length].focus(); }
    else if (event.key === "ArrowUp") { event.preventDefault(); list[(i - 1 + list.length) % list.length].focus(); }
    else if (event.key === "Home") { event.preventDefault(); list[0].focus(); }
    else if (event.key === "End") { event.preventDefault(); list[list.length - 1].focus(); }
    else if (event.key === "Tab") hide(false);
  });
  doc.addEventListener("keydown", (event) => { if (event.key === "Escape" && open) hide(true); });
  doc.addEventListener("pointerdown", (event) => { if (open && !root.contains(event.target)) hide(false); });
}
