/*
 * New pairing: once a doe and a buck are both chosen, fetch the relatedness,
 * age and same-pair check and show it in [data-pairing-check]. The separate
 * Check button is for no-JS only. Works inside the shared modal too (delegated).
 */
export function bindPairingCheck(doc, win = window) {
  const hide = (root) => root.querySelectorAll("[data-pair-check-btn]").forEach((b) => { b.hidden = true; b.style.display = "none"; });
  hide(doc);
  new win.MutationObserver(() => hide(doc)).observe(doc.body, { childList: true, subtree: true });
  let seq = 0;
  doc.addEventListener("change", async (event) => {
    const target = event.composedPath?.()[0] || event.target;
    const form = target.closest?.("form");
    const outs = [...(form?.querySelectorAll("[data-pairing-check]") || [])];
    const out = outs[0];
    if (!out || !["doe", "buck"].includes(target.name)) return;
    const doe = form.elements.doe?.value;
    const buck = form.elements.buck?.value;
    if (!doe || !buck) { outs.forEach((o) => o.replaceChildren()); return; }
    const mine = ++seq;
    try {
      const url = new URL(form.getAttribute("action") || "/pairings/", win.location.href);
      url.search = new URLSearchParams({ doe, buck }).toString();
      const response = await win.fetch(url, { credentials: "same-origin" });
      if (!response.ok) throw new Error(String(response.status));
      const page = new win.DOMParser().parseFromString(await response.text(), "text/html");
      if (mine !== seq) return;
      outs.forEach((o) => {
        const fresh = page.querySelector(`[data-pairing-check="${o.dataset.pairingCheck}"]`);
        if (fresh) o.innerHTML = fresh.innerHTML;
      });
    } catch (error) {
      console.error(error);
    }
  });
}
