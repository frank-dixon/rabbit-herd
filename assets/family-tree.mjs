/*
 * Family tree pedigree view. Draws the tree from the JSON the server embeds
 * (rabbits/family_tree.py): the rabbit on top, each generation a band below,
 * sire left and dam right, siblings and cousins beside them. Gene chips
 * draw a thread through everyone who carries the allele: solid where known,
 * dashed where probable, drawn in from the source unless motion is reduced.
 * Pan with drag or wheel, zoom with Ctrl+wheel, pinch or the buttons; on
 * phones swipe sideways between generations. Clicking a rabbit opens its
 * genes in the side panel (a bottom sheet on phones). No network needed.
 */
import { reducedMotion } from "./motion.mjs";

const LOCI = ["A", "B", "C", "D", "E", "En", "V", "Si"];
const X0 = 150, ROWH = 184, TOP = 24, GAP = 128;
/** Width the ancestors span: 150px a rabbit across four generations, 92px across five. */
export const spanFor = (gens) => (gens >= 5 ? 16 * 92 : 8 * 150);
const SIZE = [96, 80, 68, 58, 50];
const GEN_TITLES = ["Subject", "Parents", "Grandparents", "Great-grandparents", "Generation 5"];
const GEN_SHORT = ["", "Parents", "Grandparents", "Great-grand", "Gen 5"];
const RANK = { known: 3, probable: 2, guess: 1, unknown: 0 };
const ICON = {
  new: '<svg viewBox="0 0 12 12" fill="currentColor"><path d="M6 0l1.5 4.5L12 6 7.5 7.5 6 12 4.5 7.5 0 6l4.5-1.5z"/></svg>',
  proven: '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6.5l2.5 2.5L10 3"/></svg>',
  inherited: '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 1v10M2.5 7.5L6 11l3.5-3.5"/></svg>',
};

export function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/** An allele as HTML: cchd reads c with chd raised, at reads a with t raised. */
export function allele(a) {
  if (!a) return "?";
  const m = /^(c)(chd|chm|chl|h)$|^(a)(t)$|^(E)(D|s)$|^(e)(j)$/.exec(a);
  if (!m) return esc(a);
  const [base, sup] = m.slice(1).filter(Boolean);
  return `${base}<sup>${sup}</sup>`;
}

export function label(rec) {
  if (rec.level === "known") return "Known";
  if (rec.level === "probable") return `Probable ${rec.pct}%`;
  if (rec.level === "guess") return "Guess";
  return "Unknown";
}

/** Places every rabbit: ancestors by Ahnentafel number, relatives beside them. */
export function layout(data, gens = 4) {
  const SPAN = spanFor(gens), W0 = SPAN + 2 * X0;
  const items = [];
  const byNumber = {};
  for (const [num, key] of Object.entries(data.places)) {
    const n = Number(num);
    const g = Math.floor(Math.log2(n));
    if (g > 4) continue;
    const i = n - 2 ** g;
    const item = { id: "p" + n, num: n, key, gen: g, x: X0 + (SPAN * (i + 0.5)) / 2 ** g, s: SIZE[g] };
    items.push(item);
    byNumber[n] = item;
  }
  const lateral = Object.entries(data.nodes).filter(([, n]) => n.lateral);
  const firstOf = (key) => items.find((it) => it.key === key);
  const side = { 2: -1, 3: 1 };
  const count = {};
  const bump = (k) => (count[k] = (count[k] || 0) + 1);
  for (const [key, n] of lateral.filter(([, n]) => n.lateral.kind === "sibling")) {
    items.push({ id: key, key, gen: 0, x: byNumber[1].x + GAP * bump("sib"), s: SIZE[0] - 16, lat: n.lateral.label });
  }
  for (const [key, n] of lateral.filter(([, n]) => n.lateral.kind === "aunt")) {
    const anchor = byNumber[n.lateral.anchor];
    const dir = side[n.lateral.anchor] || 1;
    items.push({ id: key, key, gen: 1, x: (anchor ? anchor.x : W0 / 2) + dir * GAP * bump("a" + n.lateral.anchor), s: SIZE[1] - 12, lat: n.lateral.label, dir });
  }
  for (const [key, n] of lateral.filter(([, n]) => n.lateral.kind === "cousin")) {
    const aunt = items.find((it) => it.id === n.lateral.anchor);
    items.push({ id: key, key, gen: 0, x: (aunt ? aunt.x : 0) + (aunt?.dir || 1) * GAP * (bump("c" + n.lateral.anchor) - 1), s: SIZE[0] - 16, lat: n.lateral.label });
  }
  // Keep each band's rabbits apart.
  for (let g = 0; g < 5; g += 1) {
    const row = items.filter((it) => it.gen === g).sort((a, b) => a.x - b.x);
    const fixed = row.findIndex((it) => it.num === 2 ** g);
    for (let i = Math.max(fixed, 0) + 1; i < row.length; i += 1) row[i].x = Math.max(row[i].x, row[i - 1].x + (g ? GAP * 0.9 : GAP));
    for (let i = Math.max(fixed, 0) - 1; i >= 0; i -= 1) row[i].x = Math.min(row[i].x, row[i + 1].x - (g ? GAP * 0.9 : GAP));
  }
  const minX = Math.min(...items.map((it) => it.x), X0);
  const shift = minX < 120 ? 120 - minX : 0;
  items.forEach((it) => (it.x += shift));
  const width = Math.max(W0, Math.max(...items.map((it) => it.x)) + 120);
  // Parents of each drawn rabbit, as drawn items.
  for (const it of items) {
    if (it.num) {
      it.parents = [byNumber[it.num * 2], byNumber[it.num * 2 + 1]];
    } else {
      const n = data.nodes[it.key];
      it.parents = [n.sire && firstOf(n.sire), n.dam && firstOf(n.dam)];
    }
  }
  return { items, width };
}

export function bindFamilyTree(root = document) {
  const host = root.querySelector?.("[data-family-tree]");
  const script = root.getElementById?.("family-tree-data");
  if (!host || !script || host.dataset.bound) return;
  host.dataset.bound = "1";
  const data = JSON.parse(script.textContent);
  const N = data.nodes;
  const $ = (sel) => host.querySelector(sel);
  const stage = $("[data-ft-stage]"), world = $("[data-ft-world]"), drawer = $("[data-ft-drawer]"), tip = $("[data-ft-tip]");
  const info = $("[data-ft-info]");
  let items = [], W = 0;
  const subjectName = N[data.subject].name;
  const maxGen = Math.max(...Object.keys(data.places).map((n) => Math.floor(Math.log2(Number(n)))));
  const state = { gens: Math.min(4, maxGen + 1), gene: null, x: 0, y: 0, k: 1, focusGen: 0 };
  const isPhone = () => innerWidth <= 760;
  const visible = (it) => it.gen < state.gens;
  const worldH = () => TOP + state.gens * ROWH + 72;
  const y = (it) => TOP + it.gen * ROWH + 48;

  function thumb(key, size, cls = "") {
    const n = N[key];
    return `<span class="ft-th ${cls}" style="width:${size}px;height:${size}px"><img src="${esc(n.img)}" alt="" draggable="false" loading="lazy" decoding="async">${n.placeholder ? '<span class="ft-ph" title="Placeholder photo"></span>' : ""}</span>`;
  }

  function render() {
    ({ items, width: W } = layout(data, state.gens));
    const H = worldH();
    world.style.width = W + "px";
    world.style.height = H + "px";
    let bands = "", labels = "";
    for (let g = 0; g < state.gens; g += 1) {
      bands += `<rect x="0" y="${TOP + g * ROWH}" width="${W}" height="${ROWH}" class="${g % 2 ? "b2" : "b1"}"/>`;
      labels += `<div class="ft-band" style="top:${TOP + g * ROWH + 16}px">${GEN_TITLES[g]}<em>${g ? "Generation " + g : esc(subjectName)}</em></div>`;
    }
    const families = {};
    for (const it of items) {
      if (!visible(it)) continue;
      const ps = it.parents.filter((p) => p && visible(p));
      if (!ps.length) continue;
      const fk = ps.map((p) => p.id).join("|");
      (families[fk] = families[fk] || { ps, kids: [] }).kids.push(it);
    }
    let conns = "";
    for (const f of Object.values(families)) {
      const py = y(f.ps[0]);
      const busY = py - 34;
      const xs = f.ps.map((p) => p.x).concat(f.kids.map((c) => c.x));
      let d = `M${Math.min(...xs)} ${busY}H${Math.max(...xs)}`;
      f.ps.forEach((p) => (d += `M${p.x} ${busY}V${py}`));
      f.kids.forEach((c) => (d += `M${c.x} ${y(c) + c.s + 44}V${busY}`));
      conns += `<path class="ft-conn" d="${d}"/>`;
    }
    let nodes = "", tags = "";
    for (const it of items) {
      if (!visible(it)) continue;
      const n = N[it.key];
      nodes += `<button type="button" class="ft-node${it.num === 1 ? " subject" : ""}" data-item="${it.id}" style="left:${it.x}px;top:${y(it)}px;--s:${it.s}px" aria-label="${esc(n.name)}, ${esc(n.color || "color not recorded")}${it.lat ? ", " + esc(it.lat) : ""}">${thumb(it.key, it.s)}<span class="ft-sx">${n.sex ? n.sex[0] : "?"}</span><span class="ft-dot"></span><span class="ft-nm">${esc(n.name)}</span><span class="ft-cl">${esc(n.color || "—")}</span></button>`;
      if (it.lat) tags += `<span class="ft-lat" style="left:${it.x}px;top:${y(it) - 20}px">${esc(it.lat)}</span>`;
    }
    world.innerHTML = `<svg class="ft-wires" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><g>${bands}</g><g>${conns}</g><g data-ft-thread></g></svg>${labels}${nodes}${tags}`;
    const more = $("[data-ft-more]");
    const extra = Object.keys(data.places).filter((n) => Math.floor(Math.log2(Number(n))) === 4).length;
    more.hidden = maxGen < 4;
    more.textContent = state.gens === 4 ? `Show 5th generation · ${extra} more` : "Hide 5th generation";
    renderGenNav();
    if (state.gene) drawThread(false);
  }

  /* Thread */
  function drawThread(animate = true) {
    const gene = state.gene;
    const g = world.querySelector("[data-ft-thread]");
    host.style.setProperty("--thread", gene.color);
    const held = gene.nodes;
    const edges = [];
    for (const it of items) {
      if (!visible(it)) continue;
      it.parents.forEach((p) => {
        if (!p || !visible(p)) return;
        const e = gene.edges.find(([from, to]) => from === p.key && to === it.key);
        if (e) edges.push({ from: p, to: it, known: e[2] === "known" });
      });
    }
    const reduce = reducedMotion() || !animate;
    const maxG = Math.max(0, ...edges.map((e) => e.from.gen));
    edges.sort((a, b) => b.from.gen - a.from.gen);
    let defs = "", html = "";
    edges.forEach((e, i) => {
      const a = e.from, b = e.to;
      const ax = a.x, ay = y(a) + a.s / 2, bx = b.x, by = y(b) + b.s / 2, my = (ay + by) / 2;
      const d = `M${ax} ${ay}C${ax} ${my} ${bx} ${my} ${bx} ${by}`;
      const delay = (maxG - a.gen) * 420 + (i % 4) * 40;
      defs += `<mask id="ftm${i}" maskUnits="userSpaceOnUse" x="0" y="0" width="${W}" height="${worldH()}"><path d="${d}" pathLength="1" fill="none" stroke="#fff" stroke-width="12" stroke-linecap="round" class="${reduce ? "" : "ft-draw"}" style="animation-delay:${delay}ms"/></mask>`;
      html += `<g mask="url(#ftm${i})"><path d="${d}" class="ft-edge halo"/><path d="${d}" class="ft-edge${e.known ? "" : " prob"}"/></g>`;
    });
    g.innerHTML = `<defs>${defs}</defs>${html}`;
    world.classList.add("threading");
    world.querySelectorAll(".ft-node").forEach((el) => {
      const it = items.find((x) => x.id === el.dataset.item);
      const h = held[it.key];
      el.classList.toggle("on", Boolean(h));
      const dot = el.querySelector(".ft-dot");
      dot.className = "ft-dot " + (!h ? "" : h[0] === "expressed" ? "exp" : h[1] === "known" ? "car" : "prob");
      dot.title = !h ? "" : h[0] === "expressed" ? "Shows it" : h[1] === "known" ? "Known carrier" : `Probable carrier ${h[2]}%`;
    });
    const shown = items.filter((it) => visible(it) && held[it.key]);
    const keys = [...new Set(shown.map((it) => it.key))];
    const sources = gene.sources.filter((k) => keys.includes(k)).map((k) => N[k].name);
    const proven = edges.filter((e) => e.known).length;
    info.innerHTML = `<h3><i></i>${allele(gene.allele)} · ${esc(gene.label)}</h3><p>${sources.length ? `Source${sources.length > 1 ? "s" : ""}: ${esc(sources.join(", "))}. ` : ""}${edges.length - proven ? "Dashed links are probable, not yet proven by kits." : edges.length ? "Every link is proven." : "No links between generations yet."}</p><dl><div><dt>Carry it</dt><dd>${keys.length}</dd></div><div><dt>Show it</dt><dd>${keys.filter((k) => held[k][0] === "expressed").length}</dd></div><div><dt>Proven links</dt><dd>${proven} of ${edges.length}</dd></div></dl>`;
    info.classList.add("show");
  }

  function setGene(id) {
    state.gene = id && (!state.gene || state.gene.id !== id) ? data.chips.find((c) => c.id === id) || null : null;
    host.querySelectorAll(".ft-chip").forEach((c) => c.setAttribute("aria-pressed", String(Boolean(state.gene) && c.dataset.gene === state.gene.id)));
    if (state.gene) drawThread(true);
    else {
      world.querySelector("[data-ft-thread]").innerHTML = "";
      world.classList.remove("threading");
      info.classList.remove("show");
      world.querySelectorAll(".ft-node").forEach((n) => n.classList.remove("on"));
    }
    syncUrl();
  }

  /* Pan and zoom */
  const zoomLabel = host.querySelector('[data-ft-zoom="fit"]');
  const panelOpen = () => host.classList.contains("open");
  function apply() {
    world.style.transform = `translate(${state.x}px,${state.y}px) scale(${state.k})`;
    zoomLabel.textContent = Math.round(state.k * 100) + "%";
  }
  function fit() {
    const vw = stage.clientWidth;
    const vh = stage.clientHeight;
    const top = isPhone() ? 40 : 0;
    const k = Math.min(vw / W, (vh - top - 56) / worldH()) * 0.98;
    state.k = k;
    state.x = (vw - W * k) / 2;
    state.y = top + Math.max(8, (vh - top - 56 - worldH() * k) / 2);
    apply();
  }
  function zoomAt(f, cx, cy) {
    const k = Math.min(3, Math.max(0.2, state.k * f));
    const r = k / state.k;
    state.x = cx - (cx - state.x) * r;
    state.y = cy - (cy - state.y) * r;
    state.k = k;
    apply();
  }
  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    const b = stage.getBoundingClientRect();
    if (e.ctrlKey || e.metaKey) zoomAt(Math.exp(-e.deltaY * 0.01), e.clientX - b.left, e.clientY - b.top);
    else { state.x -= e.deltaX; state.y -= e.deltaY; apply(); }
  }, { passive: false });
  const ptrs = new Map();
  let drag = null, pinch = null, moved = false;
  stage.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".ft-zoom,.ft-more,.ft-gennav")) return;
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    moved = false;
    if (ptrs.size === 1) drag = { x: e.clientX, y: e.clientY, sx: state.x, sy: state.y, t: Date.now(), touch: e.pointerType === "touch" };
    if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), k: state.k };
      drag = null;
    }
  });
  stage.addEventListener("pointermove", (e) => {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      const r = stage.getBoundingClientRect();
      zoomAt((pinch.k * Math.hypot(a.x - b.x, a.y - b.y)) / pinch.d / state.k, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
      return;
    }
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.hypot(dx, dy) > 4) {
      moved = true;
      stage.classList.add("dragging");
      try { stage.setPointerCapture(e.pointerId); } catch (_) { /* already released */ }
    }
    state.x = drag.sx + (drag.touch && isPhone() ? dx * 0.35 : dx);
    state.y = drag.sy + dy;
    apply();
  });
  function end(e) {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.delete(e.pointerId);
    stage.classList.remove("dragging");
    if (drag && drag.touch && isPhone()) {
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.2 && Date.now() - drag.t < 700) focusGen(state.focusGen + (dx < 0 ? 1 : -1));
    }
    drag = null;
    if (ptrs.size < 2) pinch = null;
  }
  stage.addEventListener("pointerup", end);
  stage.addEventListener("pointercancel", end);
  stage.addEventListener("click", (e) => { if (moved) { e.stopPropagation(); e.preventDefault(); moved = false; } }, true);
  stage.addEventListener("keydown", (e) => {
    const step = { ArrowLeft: [40, 0], ArrowRight: [-40, 0], ArrowUp: [0, 40], ArrowDown: [0, -40] }[e.key];
    if (step && e.target === stage) { e.preventDefault(); state.x += step[0]; state.y += step[1]; apply(); }
    if ((e.key === "+" || e.key === "=") && e.target === stage) zoomAt(1.25, stage.clientWidth / 2, stage.clientHeight / 2);
    if (e.key === "-" && e.target === stage) zoomAt(0.8, stage.clientWidth / 2, stage.clientHeight / 2);
  });

  function focusGen(g) {
    g = Math.max(0, Math.min(state.gens - 1, g));
    state.focusGen = g;
    const row = items.filter((it) => it.gen === g && visible(it) && it.num);
    const minX = Math.min(...row.map((it) => it.x - it.s / 2)) - 24, maxX = Math.max(...row.map((it) => it.x + it.s / 2)) + 24;
    const vw = stage.clientWidth, vh = stage.clientHeight;
    const want = g >= 3 ? (vw / (maxX - minX)) * 2.1 : vw / Math.max(maxX - minX, 1);
    state.k = Math.min(1.1, Math.max(0.5, want));
    const cx = g >= 3 ? row[0].x + spanFor(state.gens) / 4 : (minX + maxX) / 2;
    state.x = vw / 2 - cx * state.k;
    state.y = vh * 0.36 - (TOP + g * ROWH + ROWH / 2) * state.k;
    world.style.transition = reducedMotion() ? "none" : "transform .35s cubic-bezier(.2,.8,.2,1)";
    apply();
    setTimeout(() => (world.style.transition = ""), 380);
    renderGenNav();
  }
  function renderGenNav() {
    const nav = $("[data-ft-gennav]");
    nav.innerHTML = GEN_SHORT.slice(0, state.gens).map((l, i) => `<button type="button" data-g="${i}" aria-current="${i === state.focusGen}">${i ? l : esc(subjectName)}</button>`).join("");
  }
  $("[data-ft-gennav]").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) focusGen(Number(b.dataset.g)); });
  host.querySelector('[data-ft-zoom="in"]').addEventListener("click", () => zoomAt(1.25, stage.clientWidth / 2, stage.clientHeight / 2));
  host.querySelector('[data-ft-zoom="out"]').addEventListener("click", () => zoomAt(0.8, stage.clientWidth / 2, stage.clientHeight / 2));
  zoomLabel.addEventListener("click", fit);
  $("[data-ft-more]").addEventListener("click", () => {
    state.gens = state.gens === 4 ? 5 : 4;
    render();
    if (isPhone()) focusGen(state.gens === 5 ? 4 : state.focusGen); else fit();
    syncUrl();
  });

  /* Tooltip */
  function knownGenes(n) {
    return LOCI.map((L) => {
      const pair = n.genes[L].pair;
      if (!pair.some((r) => r.level === "known")) return "";
      return pair.map((r) => (r.level === "known" ? allele(r.allele) : r.level === "probable" ? allele(r.allele) + "?" : "_")).join(" ");
    }).filter(Boolean);
  }
  world.addEventListener("pointerover", (e) => {
    const el = e.target.closest(".ft-node");
    if (!el || e.pointerType === "touch") return;
    const it = items.find((x) => x.id === el.dataset.item);
    const n = N[it.key];
    const genes = knownGenes(n);
    tip.innerHTML = `<b>${esc(n.name)}</b> <span class="m">· ${esc(n.sex || "Outside")}${it.lat ? " · " + esc(it.lat) : ""}</span><br>${esc(n.color || "Color not recorded")}<br>${genes.length ? `<code>${genes.join(" · ")}</code>` : '<span class="m">No genes known yet</span>'}<br><span class="m">? probable · _ unknown</span>`;
    const b = el.querySelector(".ft-th").getBoundingClientRect();
    tip.style.left = Math.min(innerWidth - 270, Math.max(8, b.left + b.width / 2 - 120)) + "px";
    tip.style.top = b.bottom + 10 + "px";
    tip.classList.add("show");
  });
  world.addEventListener("pointerout", (e) => { if (e.target.closest(".ft-node")) tip.classList.remove("show"); });

  /* Side panel */
  const fromWho = (n, rec) => {
    if (!rec.origin) return "from sire or dam";
    const key = rec.origin_key || n[rec.origin];
    return `from ${rec.origin} ${key && N[key] ? esc(N[key].name) : "(not recorded)"}`;
  };
  function geneRows(n) {
    return LOCI.filter((L) => !["V", "Si"].includes(L) || n.genes[L].pair.some((r) => r.level !== "unknown")).map((L) => {
      const pair = n.genes[L].pair;
      const worst = pair.reduce((a, b) => (RANK[b.level] < RANK[a.level] ? b : a));
      const al = pair.map((r) => `<span class="ft-al"><code class="${r.level === "known" ? "" : r.level === "probable" ? "prob" : "hid"}">${r.level === "known" || r.level === "probable" ? allele(r.allele) : "?"}</code><small>${fromWho(n, r)}</small></span>`).join("");
      const why = pair.map((r) => `<div class="ft-why"><b>${r.level === "unknown" ? "?" : allele(r.allele)}</b> ${esc(r.why)}${r.level === "known" || r.level === "unknown" ? "" : ` · ${label(r)}`}</div>`).join("");
      return `<tr><td class="loc"><b>${esc(L)}</b><span>${esc(n.genes[L].name)}</span></td><td>${al}${why}</td><td class="conf-cell"><span class="ft-conf ${worst.level}">${label(worst)}</span></td></tr>`;
    }).join("");
  }
  function changeList(n) {
    if (!n.changes.length) return `<li class="none"><span></span><div class="ft-why">${n.sire || n.dam ? "Nothing new at this generation." : "Parents are not recorded, so nothing can be traced here yet."}</div></li>`;
    return n.changes.map((c) => `<li><span class="ic ${c.kind}">${ICON[c.kind] || ""}</span><div><div>${esc(c.text)}</div><div class="ft-why">${esc(c.why)}</div><div class="meta"><span class="ft-conf ${c.level}">${label(c)}</span></div></div></li>`).join("");
  }
  let lastFocus = null;
  function openPanel(key) {
    const n = N[key];
    if (!n) return;
    tip.classList.remove("show");
    lastFocus = lastFocus || document.activeElement;
    const link = (k) => (k && N[k] ? `<a href="#" data-open="${esc(k)}">${esc(N[k].name)}</a>` : "");
    const it = items.find((x) => x.key === key);
    const born = n.born ? new Date(n.born + "T12:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";
    drawer.innerHTML = `<div class="grab"></div><div class="dhead">${thumb(key, isPhone() ? 88 : 120, "big")}<div class="dmeta"><h2 id="ft-name">${esc(n.name)}</h2><div class="sub">${esc([n.color, n.sex, it && it.lat].filter(Boolean).join(" · "))}</div>
      <dl class="kv"><dt>Born</dt><dd>${born}</dd><dt>Sire</dt><dd>${link(n.sire) || "Not recorded"}</dd><dt>Dam</dt><dd>${link(n.dam) || "Not recorded"}</dd>${n.kits.length ? `<dt>Kits here</dt><dd>${n.kits.map(link).join(", ")}</dd>` : ""}</dl></div>
      <button type="button" class="close" data-ft-close aria-label="Close"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
      <div class="dbody"><section class="sec"><h3>Genotype</h3><table class="gt">${geneRows(n)}</table></section><section class="sec"><h3>What changed at this generation</h3><ul class="changes">${changeList(n)}</ul></section></div>
      <div class="dfoot"><button type="button" class="ft-btn" data-open="${esc(n.sire || "")}" ${n.sire ? "" : "disabled"}>${n.sire ? "Sire · " + esc(N[n.sire].name) : "No sire record"}</button>${n.detail ? `<a class="ft-btn quiet" href="${esc(n.detail)}">Open record</a>` : ""}<button type="button" class="ft-btn" data-open="${esc(n.dam || "")}" ${n.dam ? "" : "disabled"}>${n.dam ? "Dam · " + esc(N[n.dam].name) : "No dam record"}</button></div>`;
    const was = panelOpen();
    host.classList.add("open");
    document.documentElement.classList.add("ft-locked");
    drawer.focus({ preventScroll: true });
    if (!isPhone()) reveal(key);
    state.open = key;
    syncUrl();
  }
  function reveal(key) {
    const it = items.find((x) => x.key === key && visible(x));
    if (!it) return;
    const room = Math.max(240, drawer.getBoundingClientRect().left - stage.getBoundingClientRect().left);
    state.k = Math.max(state.k, 0.55);
    state.x = room / 2 - it.x * state.k;
    state.y = stage.clientHeight * 0.45 - (y(it) + it.s / 2) * state.k;
    world.style.transition = reducedMotion() ? "none" : "transform .3s cubic-bezier(.2,.8,.2,1)";
    apply();
    setTimeout(() => (world.style.transition = ""), 320);
  }
  function closePanel() {
    if (!panelOpen()) return;
    host.classList.remove("open");
    document.documentElement.classList.remove("ft-locked");
    if (!isPhone()) fit();
    state.open = null;
    syncUrl();
    lastFocus?.focus?.({ preventScroll: true });
    lastFocus = null;
  }
  drawer.addEventListener("click", (e) => {
    const o = e.target.closest("[data-open]");
    if (o && o.dataset.open) { e.preventDefault(); openPanel(o.dataset.open); }
    if (e.target.closest("[data-ft-close]")) closePanel();
  });
  $("[data-ft-scrim]").addEventListener("click", closePanel);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePanel(); });
  world.addEventListener("click", (e) => {
    const el = e.target.closest(".ft-node");
    if (el) openPanel(items.find((x) => x.id === el.dataset.item).key);
  });

  function syncUrl() {
    const q = new URLSearchParams(location.search);
    q.set("view", "family");
    for (const [k, v] of [["gene", state.gene?.id], ["open", state.open], ["gens", state.gens === 5 ? "5" : ""]]) {
      if (v) q.set(k, v); else q.delete(k);
    }
    history.replaceState(history.state, "", location.pathname + "?" + q.toString());
  }

  /* Chips */
  const chips = $("[data-ft-chips]");
  if (!data.chips.length) chips.insertAdjacentHTML("beforeend", '<span class="ft-empty">No hidden genes to trace yet. Record colors and kits to find carriers.</span>');
  for (const c of data.chips) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ft-chip";
    b.dataset.gene = c.id;
    b.style.setProperty("--c", c.color);
    b.setAttribute("aria-pressed", "false");
    b.innerHTML = `<i></i><b>${allele(c.allele)}</b><span>${esc(c.label)}</span>`;
    b.addEventListener("click", () => setGene(c.id));
    chips.appendChild(b);
  }

  /* Boot */
  const q = new URLSearchParams(location.search);
  if (q.get("gens") === "5" && maxGen >= 4) state.gens = 5;
  render();
  if (isPhone()) focusGen(Number(q.get("focus") || 0)); else fit();
  if (q.get("gene")) setGene(q.get("gene"));
  if (q.get("open")) openPanel(q.get("open"));
  addEventListener("resize", () => (isPhone() ? focusGen(state.focusGen) : panelOpen() ? reveal(state.open) : fit()));
}
