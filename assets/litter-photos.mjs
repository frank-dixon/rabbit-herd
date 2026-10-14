// Litter and kit photos: picking a file uploads it right away and swaps the
// image in place, no page reload. A new litter photo also replaces every
// kit tile still showing the litter photo or the placeholder.

function setBusy(el, on) {
  if (on) el.setAttribute("aria-busy", "true");
  else el.removeAttribute("aria-busy");
}

function showError(form, text) {
  let p = form.parentElement.querySelector(".lc-err");
  if (!text) { p?.remove(); return; }
  if (!p) {
    p = document.createElement("p");
    p.className = "lc-err";
    p.setAttribute("role", "alert");
    form.parentElement.append(p);
  }
  p.textContent = text;
}

function swap(img, url) {
  const next = new Image();
  next.onload = () => { img.src = url; };
  next.src = url;
  img.closest(".lc-img")?.querySelector("[data-placeholder-tag]")?.remove();
}

async function upload(form, input) {
  const label = input.closest("label");
  setBusy(label, true);
  showError(form, "");
  try {
    const res = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.url) throw new Error(data.error || "That photo couldn't be saved. Try again.");
    const card = form.closest("[data-litter-card]");
    if (form.dataset.photoForm === "litter") {
      swap(card.querySelector('[data-photo-target="litter"] img'), data.url);
      card.querySelectorAll("img[data-inherits]").forEach((img) => swap(img, data.url));
      const title = card.querySelector("[data-litter-photo-title]");
      if (title) title.textContent = "Litter photo";
      const note = card.querySelector("[data-litter-photo-note]");
      if (note) note.textContent = "Kits show this photo until they have their own.";
      const btn = card.querySelector("[data-litter-photo-btn]");
      if (btn) { btn.classList.replace("lc-btn-pri", "lc-btn-sec"); btn.querySelector("span").textContent = "Change litter photo"; }
    } else {
      const img = form.closest(".lc-img").querySelector("img");
      img.removeAttribute("data-inherits");
      swap(img, data.url);
    }
  } catch (err) {
    showError(form, err.message);
  } finally {
    setBusy(label, false);
    input.value = "";
  }
}

export function bindLitterPhotos(root = document) {
  root.addEventListener("change", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.matches("[data-photo-input]") || !input.files?.length) return;
    const form = input.closest("form[data-photo-form]");
    if (form) upload(form, input);
  });
}
