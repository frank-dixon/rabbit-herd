/**
 * Welcome guide: a small popover anchored to [data-guide="…"] elements.
 * Steps come from <script type="application/json" id="guide-steps">.
 * Skip / next / back post to the server so the step survives reloads.
 * Spec: /workspace/specs/onboarding-samples.md
 */
import { reducedMotion } from "./motion.mjs";

function place(pop, anchor) {
  const r = anchor.getBoundingClientRect();
  const w = pop.offsetWidth;
  const left = Math.min(Math.max(16, r.left), window.innerWidth - w - 16);
  pop.style.left = `${left + window.scrollX}px`;
  pop.style.top = `${r.bottom + window.scrollY + 12}px`;
  pop.style.setProperty("--ax", `${Math.min(w - 24, Math.max(14, r.left - left + Math.min(r.width / 2, 40) - 5))}px`);
}

function post(url, body) {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  const data = new FormData();
  if (body) Object.entries(body).forEach(([k, v]) => data.append(k, v));
  return fetch(url, { method: "POST", body: data, headers: token ? { "X-CSRFToken": token } : {}, credentials: "same-origin" });
}

export function bindGuide(doc = document) {
  const raw = doc.getElementById("guide-steps");
  if (!raw) return;
  let steps;
  try { steps = JSON.parse(raw.textContent); } catch { return; }
  const current = raw.dataset.step;
  if (!current || current === "done") return;
  const i = steps.findIndex((s) => s.id === current);
  if (i < 0) return;
  const step = steps[i];
  const anchor = doc.querySelector(`[data-guide="${step.anchor}"]`) || doc.querySelector("[data-page-header]");
  if (!anchor) return;
  anchor.classList.add("guide-glow");
  const pop = doc.createElement("div");
  pop.className = "guide-pop";
  pop.setAttribute("role", "dialog");
  pop.setAttribute("aria-label", "Welcome guide");
  const finish = step.finish;
  pop.innerHTML = `<div class="guide-k">${i + 1} of ${steps.length}</div>
    <h3 class="guide-t">${step.title}</h3>
    <p class="guide-p">${step.body}</p>
    <div class="guide-f">${finish
      ? `<button type="button" class="btn-sec" data-guide-keep>Keep samples for now</button>
         <button type="button" class="btn-pri" data-guide-clear>Clear samples and start fresh</button>`
      : `<button type="button" class="btn-ghost" data-guide-skip>Skip guide</button>
         <span class="guide-sp"></span>
         ${i ? `<button type="button" class="btn-sec" data-guide-back>Back</button>` : ""}
         <button type="button" class="btn-pri" data-guide-next>Next</button>`}
    </div>
    <div class="guide-dots" aria-hidden="true">${steps.map((_, j) => `<i class="${j <= i ? "on" : ""}"></i>`).join("")}</div>`;
  doc.body.appendChild(pop);
  place(pop, anchor);
  const onResize = () => place(pop, anchor);
  window.addEventListener("resize", onResize);
  const go = async (stepId) => {
    await post("/guide/step/", { step: stepId });
    const next = steps.find((s) => s.id === stepId);
    if (next?.href) location.href = next.href;
    else location.reload();
  };
  pop.querySelector("[data-guide-next]")?.addEventListener("click", () => go(steps[i + 1].id));
  pop.querySelector("[data-guide-back]")?.addEventListener("click", () => go(steps[i - 1].id));
  pop.querySelector("[data-guide-skip]")?.addEventListener("click", async () => {
    await post("/guide/skip/");
    location.reload();
  });
  pop.querySelector("[data-guide-keep]")?.addEventListener("click", () => go("done"));
  pop.querySelector("[data-guide-clear]")?.addEventListener("click", async () => {
    await go("done");
    const form = doc.createElement("form");
    form.method = "post"; form.action = "/samples/clear/";
    const token = doc.querySelector('meta[name="csrf-token"]')?.content;
    if (token) { const i = doc.createElement("input"); i.type = "hidden"; i.name = "csrfmiddlewaretoken"; i.value = token; form.appendChild(i); }
    doc.body.appendChild(form); form.submit();
  });
  const onKey = (e) => { if (e.key === "Escape") pop.querySelector("[data-guide-skip],[data-guide-keep]")?.click(); };
  doc.addEventListener("keydown", onKey);
  if (!reducedMotion()) anchor.scrollIntoView({ block: "center", behavior: "smooth" });
}
