"use strict";
/* Atlas Map Forge - app page. Talks to the local server (server.py). */

const $ = (id) => document.getElementById(id);
const TOKEN = window.FORGE_TOKEN || new URLSearchParams(location.search).get("t") || "";
const CLASS_NAMES = { tanks: "Tanks", bots: "Bots", spiders: "Spiders", amphibians: "Amph", hovers: "Hover" };
const TEAM_COLORS = ["#4dff6a", "#ff4d4d", "#5aa0ff", "#ffd23c", "#c86eff", "#3ce6e6", "#ff9628", "#f0f0f0"];

const S = {
  info: null,          // /api/state
  tpl: null,           // selected template info
  values: {},          // per template id: parameter values
  seeds: {},
  map: null,           // last preview response
  seq: 0,
  busy: false,
  img: { relief: null, reliefSize: 0, hazard: null, gates: null, reach: {} },
  grid: null,          // { nx, nz, height: Int16Array, cells: Uint8Array }
  layers: { mexes: true, geos: true, starts: true, boxes: true, gates: true, hazard: true, grid: false, features: true },
  route: "",
  view: { cx: 0, cy: 0, s: 0.1 },
  titleEdited: {},
  titles: {},
  job: null,
  edits: [],           // manual edits of the current map (see atlasforge/edits.py)
  redo: [],
  symmetry: true,
};

// ------------------------------------------------------------------ helpers
async function api(path, body) {
  const opt = { headers: { "X-Forge-Token": TOKEN } };
  if (body !== undefined) {
    opt.method = "POST";
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch("/api/" + path, opt);
  const ct = r.headers.get("Content-Type") || "";
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).error || msg; } catch (e) { /* not json */ }
    throw new Error(msg);
  }
  if (ct.startsWith("application/json")) return r.json();
  if (ct.startsWith("image/")) return createImageBitmap(await r.blob());
  return r.arrayBuffer();
}
const layerUrl = (name, size) => `layer/${S.map.id}/${name}` + (size ? `?size=${size}` : "");

function toast(msg, ms = 5000) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}
function toastAction(msg, label, action, ms = 8000) {
  const t = $("toast");
  t.textContent = msg + " ";
  const b = document.createElement("button");
  b.className = "ghost";
  b.textContent = label;
  b.onclick = () => { t.classList.add("hidden"); action(); };
  t.append(b);
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}
function store(k, v) { try { localStorage.setItem("forge." + k, JSON.stringify(v)); } catch (e) { /* storage off */ } }
function recall(k, d) { try { const v = localStorage.getItem("forge." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const rgb = (c) => `rgb(${c[0]},${c[1]},${c[2]})`;

// page errors go to the app log (app.log next to the settings) so problems can be diagnosed
function clientLog(msg) { api("clientlog", { msg: String(msg) }).catch(() => {}); }
window.addEventListener("error", (e) => clientLog(`error: ${e.message} at ${e.filename}:${e.lineno}`));
window.addEventListener("unhandledrejection", (e) => clientLog(`unhandled: ${e.reason}`));

// ------------------------------------------------------------------ start
async function init() {
  try {
    S.info = await api("state");
  } catch (e) {
    $("empty").textContent = "Could not reach the forge: " + e.message;
    return;
  }
  $("ver").textContent = "v" + S.info.version;
  S.values = recall("values", {});
  S.seeds = recall("seeds", {});
  S.titles = recall("titles", {});
  S.titleEdited = recall("titleEdited", {});
  for (const [k, v] of Object.entries(recall("layers", {}))) if (k in S.layers) S.layers[k] = v;
  syncToolbar();
  renderGallery();
  renderWho();
  if (!hasAuthor()) setTimeout(openSettings, 400);           // first start: ask for the author name
  const last = recall("template", S.info.templates[0].id);
  selectTemplate(S.info.templates.find((t) => t.id === last) ? last : S.info.templates[0].id);
}

const hasAuthor = () => !!(S.info && S.info.settings.config.author.trim());
function renderWho() {
  const c = S.info.settings.config;
  $("adv-badge").classList.toggle("hidden", !c.advanced);
  $("who").textContent = hasAuthor() ? `Author: ${c.author}` : "No author name set";
  $("author-note").classList.toggle("hidden", hasAuthor());
  updateBuildButton();
}

// ------------------------------------------------------------------ gallery and controls
const MODE_LABELS = { "": "All", "1v1": "1v1", team: "Teams", ffa: "FFA", coop: "Co-op" };
const TAG_LABELS = { land: "Land", sea: "Sea", twist: "Twists", chokes: "Chokes" };
const PF = { mode: "", tags: [], q: "" };            // picker filters (remembered per viewer)

function badges(t) {
  return [...t.modes.map((m) => `<span class="bdg m-${m}">${MODE_LABELS[m] || m}</span>`),
          ...t.tags.filter((g) => g !== "land").map((g) => `<span class="bdg t-${g}">${TAG_LABELS[g] || g}</span>`)].join("");
}

function renderGallery() {
  Object.assign(PF, recall("picker", {}));
  $("tpl-count").textContent = `${S.info.templates.length} available`;
  const fm = $("flt-mode");
  fm.innerHTML = "";
  for (const [k, label] of Object.entries(MODE_LABELS)) {
    const b = document.createElement("button");
    b.textContent = label;
    b.dataset.v = k;
    b.onclick = () => { PF.mode = k; renderPicker(); };
    fm.appendChild(b);
  }
  const ft = $("flt-tags");
  ft.innerHTML = "";
  for (const [k, label] of Object.entries(TAG_LABELS)) {
    const b = document.createElement("button");
    b.textContent = label;
    b.dataset.v = k;
    b.onclick = () => { PF.tags = PF.tags.includes(k) ? PF.tags.filter((x) => x !== k) : [...PF.tags, k]; renderPicker(); };
    ft.appendChild(b);
  }
  $("picker-search").value = PF.q || "";
}

function pickerMatches(t) {
  if (PF.mode && !t.modes.includes(PF.mode)) return false;
  if (PF.tags.some((g) => !t.tags.includes(g))) return false;
  const q = (PF.q || "").trim().toLowerCase();
  return !q || `${t.title} ${t.description} ${t.id} ${t.players}`.toLowerCase().includes(q);
}

function renderPicker() {
  store("picker", PF);
  for (const b of $("flt-mode").children) b.classList.toggle("on", b.dataset.v === PF.mode);
  for (const b of $("flt-tags").children) b.classList.toggle("on", PF.tags.includes(b.dataset.v));
  const list = S.info.templates.filter(pickerMatches);
  const grid = $("picker-grid");
  grid.innerHTML = "";
  for (const t of list) {
    const b = document.createElement("button");
    b.className = "pcard" + (S.tpl && S.tpl.id === t.id ? " on" : "");
    b.innerHTML = `<img src="thumbs/${t.id}.jpg" alt="" loading="lazy"><span class="pc-body"><b>${esc(t.title)}</b>
      <span class="pc-players">${esc(t.players)}</span><span class="badges">${badges(t)}</span><p>${esc(t.description)}</p></span>`;
    b.onclick = () => { closePicker(); if (!S.tpl || S.tpl.id !== t.id) selectTemplate(t.id); };
    grid.appendChild(b);
  }
  $("picker-n").textContent = `${list.length} of ${S.info.templates.length} templates`;
  $("picker-empty").classList.toggle("hidden", list.length > 0);
}

function openPicker() {
  renderPicker();
  $("picker").classList.remove("hidden");
  setTimeout(() => $("picker-search").focus(), 30);
}
function closePicker() { $("picker").classList.add("hidden"); }
$("current-tpl").onclick = openPicker;
$("picker-close").onclick = closePicker;
$("picker").addEventListener("click", (e) => { if (e.target === $("picker")) closePicker(); });
$("picker-search").addEventListener("input", () => { PF.q = $("picker-search").value; renderPicker(); });
$("picker-search").addEventListener("keydown", (e) => {
  if (e.key === "Escape") closePicker();
  if (e.key === "Enter") { const first = $("picker-grid").querySelector(".pcard"); if (first) first.click(); }
});
$("picker-reset").onclick = (e) => { e.preventDefault(); PF.mode = ""; PF.tags = []; PF.q = ""; $("picker-search").value = ""; renderPicker(); };

function selectTemplate(id) {
  S.tpl = S.info.templates.find((t) => t.id === id);
  store("template", id);
  $("cur-thumb").src = `thumbs/${id}.jpg`;
  $("cur-title").textContent = S.tpl.title;
  $("cur-meta").textContent = S.tpl.players;
  $("cur-badges").innerHTML = badges(S.tpl);
  $("tpl-title").textContent = S.tpl.title;
  $("tpl-desc").textContent = S.tpl.description;
  const vals = Object.assign({}, ...S.tpl.params.map((p) => ({ [p.key]: p.default })), S.values[id] || {});
  for (const k of Object.keys(vals)) if (!S.tpl.params.some((p) => p.key === k)) delete vals[k];
  S.values[id] = vals;
  clampValues(id);
  $("seed").value = S.seeds[id] || 7;
  renderParams();
  $("title").value = S.titles[id] || S.tpl.title;
  schedulePreview(0, true);
}

const isAdvanced = () => !!(S.info && S.info.settings.config.advanced);
const pLimits = (p) => isAdvanced()
  ? [p.adv_min ?? p.min, p.adv_max ?? p.max] : [p.min, p.max];
const pChoices = (p) => (isAdvanced() && p.adv_choices ? p.adv_choices : p.choices);
const beyond = (p, v) => (p.kind === "choice" ? !p.choices.map(String).includes(String(v))
  : (p.kind === "int" || p.kind === "float") && (v < p.min || v > p.max));

function clampValues(id) {
  // keep stored values inside what the current mode allows
  const t = S.info.templates.find((x) => x.id === id);
  const vals = S.values[id];
  for (const p of t.params) {
    if (!(p.key in vals)) continue;
    if (p.kind === "choice") {
      if (!pChoices(p).map(String).includes(String(vals[p.key]))) vals[p.key] = p.default;
    } else if (p.kind === "int" || p.kind === "float") {
      const [lo, hi] = pLimits(p);
      vals[p.key] = Math.min(hi, Math.max(lo, vals[p.key]));
    }
  }
}

// Group order: Map, Resources, Terrain, template-specific groups, Advanced last.
const GROUP_ORDER = ["Map", "Resources", "Terrain"];
function groupRank(g) {
  if (g === "Advanced") return 4;
  const i = GROUP_ORDER.indexOf(g);
  return i >= 0 ? i : 3;
}
function groupTitle(g) { return GROUP_TITLES[g] || g || `${S.tpl.title} settings`; }

function renderParams() {
  const box = $("params");
  // the seed row lives inside the groups after the first render: take it out before clearing
  const seedRow = $("seed").closest(".seed-row");
  box.innerHTML = "";
  const vals = S.values[S.tpl.id];
  $("adv-note").classList.toggle("hidden", !isAdvanced());
  const groups = new Map();
  for (const p of S.tpl.params) {
    const g = p.group || "";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(p);
  }
  const sorted = [...groups].sort((a, b) => groupRank(a[0]) - groupRank(b[0]));
  const collapsedSaved = recall("groups", {});
  let seedPending = !S.tpl.params.some((p) => p.key === "size");
  for (const [g, params] of sorted) {
    const title = groupTitle(g);
    const collapsed = title in collapsedSaved ? !!collapsedSaved[title] : g === "Advanced";
    const head = document.createElement("button");
    head.type = "button";
    head.className = "group-head";
    head.setAttribute("aria-expanded", String(!collapsed));
    head.innerHTML = `<span class="chev" aria-hidden="true">&#9662;</span>${esc(title)}`;
    const body = document.createElement("div");
    body.className = "group-body";
    body.hidden = collapsed;
    head.onclick = () => {
      const open = head.getAttribute("aria-expanded") === "true";
      head.setAttribute("aria-expanded", String(!open));
      body.hidden = open;
      if (open) hideInfo();
      store("groups", { ...recall("groups", {}), [title]: open });
    };
    box.appendChild(head);
    box.appendChild(body);
    if (seedPending) { body.appendChild(seedRow); seedPending = false; }
    for (const p of params) {
      body.appendChild(paramField(p, vals));
      if (p.key === "size") body.appendChild(seedRow);
    }
  }
}

function paramField(p, vals) {
    const f = document.createElement("div");
    f.className = "field";
    const help = p.help ? `<div class="help">${esc(p.help)}</div>` : "";
    const ib = infoButton(p);
    if (p.kind === "bool") {
      f.innerHTML = `<div class="lrow"><label class="switch"><input type="checkbox"><span></span>${esc(p.label)}</label>${ib}</div>${help}`;
      const cb = f.querySelector("input");
      cb.checked = !!vals[p.key];
      cb.onchange = () => setValue(p.key, cb.checked);
    } else if (p.kind === "choice") {
      f.innerHTML = `<label>${esc(p.label)}${ib}</label><div class="chips"></div>${help}`;
      const chips = f.querySelector(".chips");
      for (const c of pChoices(p)) {
        const b = document.createElement("button");
        b.dataset.v = String(c);
        let label = esc(c);
        if (c === "default" || c === "biome") label = c === "biome" ? "biome" : "template";
        if (p.key === "size") label = `${c}&times;${c}`;
        if (p.key === "biome" && S.info.biomes[c]) {
          label = `<span class="sw">${S.info.biomes[c].map((x) => `<i style="background:${rgb(x)}"></i>`).join("")}</span>` + label;
        }
        b.innerHTML = label;
        b.classList.toggle("on", String(vals[p.key]) === String(c));
        b.classList.toggle("beyond", beyond(p, c));
        b.onclick = () => {
          for (const o of chips.children) o.classList.toggle("on", o === b);
          setValue(p.key, c);
        };
        chips.appendChild(b);
      }
    } else {
      const fmt = (v) => (p.kind === "float" ? Number(v).toFixed(1) : String(v));
      const [lo, hi] = pLimits(p);
      f.innerHTML = `<label>${esc(p.label)}${ib} <span class="val"></span></label>
        <input type="range" min="${lo}" max="${hi}" step="${p.step || (p.kind === "float" ? 0.1 : 1)}">${help}`;
      const r = f.querySelector("input");
      const out = f.querySelector(".val");
      r.value = vals[p.key];
      const show = (v) => {
        out.textContent = p.key === "mex_count" && Number(v) === 0 ? "template default" : fmt(v);
        const b = beyond(p, Number(v));
        out.classList.toggle("beyond", b);
        f.classList.toggle("beyond", b);
      };
      show(vals[p.key]);
      r.oninput = () => show(r.value);
      r.onchange = () => setValue(p.key, p.kind === "float" ? parseFloat(r.value) : parseInt(r.value, 10));
    }
    const btn = f.querySelector(".pinfo");
    if (btn) btn.onclick = (e) => { e.preventDefault(); e.stopPropagation(); showInfo(p, btn); };
    return f;
}

const GROUP_TITLES = { Map: "Map", Resources: "Resources", Terrain: "Terrain and decoration" };

function infoButton(p) {
  if (!p.info && !p.help) return "";
  return `<button class="pinfo" type="button" title="What does this do?" aria-label="About ${esc(p.label)}">i</button>`;
}

function rangeText(p) {
  const show = (v) => (v === "default" ? "template default" : v === "biome" ? "biome default" : String(v));
  if (p.kind === "bool") return `Default: ${p.default ? "on" : "off"}`;
  if (p.kind === "choice") {
    let t = `Options: ${p.choices.map(show).join(", ")}. Default: ${show(p.default)}.`;
    if (p.adv_choices) t += ` Advanced mode adds: ${p.adv_choices.filter((c) => !p.choices.map(String).includes(String(c))).map(show).join(", ")}.`;
    return t;
  }
  let t = `Range ${p.min} to ${p.max}, default ${p.key === "mex_count" && p.default === 0 ? "0 (template default)" : p.default}.`;
  if (p.adv_min != null || p.adv_max != null) t += ` Advanced mode: ${p.adv_min ?? p.min} to ${p.adv_max ?? p.max}.`;
  return t;
}

function showInfo(p, anchor) {
  const pop = $("infopop");
  if (!pop.classList.contains("hidden") && pop.dataset.key === p.key) { hideInfo(); return; }
  pop.dataset.key = p.key;
  pop.innerHTML = `<b>${esc(p.label)}</b><p>${esc(p.info || p.help)}</p><div class="range">${esc(rangeText(p))}</div>`;
  pop.classList.remove("hidden");
  const r = anchor.getBoundingClientRect();
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let x = r.right + 10, y = r.top - 8;
  if (x + w > innerWidth - 8) x = Math.max(8, r.left - w - 10);
  if (y + h > innerHeight - 8) y = Math.max(8, innerHeight - h - 8);
  pop.style.left = `${x}px`;
  pop.style.top = `${y}px`;
}
function hideInfo() { $("infopop").classList.add("hidden"); }
document.addEventListener("click", (e) => { if (!e.target.closest("#infopop")) hideInfo(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideInfo(); });
$("params").addEventListener("scroll", hideInfo, true);

function setValue(k, v) {
  S.values[S.tpl.id][k] = v;
  store("values", S.values);
  if ($("auto").checked) schedulePreview(250);
}

// ------------------------------------------------------------------ preview
let pvTimer = null;
function schedulePreview(ms, refit = false) {
  clearTimeout(pvTimer);
  pvTimer = setTimeout(() => runPreview(refit), ms);
}

async function runPreview(refit) {
  if (!(await editorGuard())) return;                          // manual edits would be lost: ask first
  const seq = ++S.seq;
  const seed = Math.max(1, parseInt($("seed").value, 10) || 1);
  S.seeds[S.tpl.id] = seed;
  store("seeds", S.seeds);
  const veilT = setTimeout(() => $("veil").classList.add("on"), 120);
  S.busy = true;
  updateBuildButton();
  try {
    const prev = S.map;
    const m = await api("preview", { template: S.tpl.id, values: S.values[S.tpl.id], seed, edits: S.edits, symmetry: S.symmetry });
    if (seq !== S.seq) return;                                 // a newer preview is on its way
    const [relief, height, cells, hazard, gates] = await Promise.all([
      api(`layer/${m.id}/relief?size=1024`),
      api(`layer/${m.id}/height`),
      api(`layer/${m.id}/cells`),
      m.has_hazard ? api(`layer/${m.id}/hazard`) : null,
      m.gates.length ? api(`layer/${m.id}/gates`) : null,
    ]);
    if (seq !== S.seq) return;
    S.map = m;
    editorAfterPreview(m, seed);
    S.img = { relief, reliefSize: 1024, hazard, gates, reach: {} };
    S.grid = { nx: m.grid[0], nz: m.grid[1], height: new Int16Array(height), cells: new Uint8Array(cells) };
    $("empty").classList.add("hidden");
    $("readout").innerHTML = "Scroll to zoom, drag to move";
    const sameFrame = prev && prev.W === m.W && prev.H === m.H && !refit;
    if (!sameFrame) fit();
    if (S.route) await loadRoute(S.route);
    $("route-ships").classList.toggle("hidden", m.movement_profile !== "naval");
    if (S.route === "ships" && m.movement_profile !== "naval") { S.route = ""; syncToolbar(); }
    renderReport();
    renderFacts();
    updateLegend();
    if (!S.titleEdited[S.tpl.id]) $("title").value = m.title;
    refreshVersions();
    draw();
    maybeHiRes();
    if (!runPreview.logged) { runPreview.logged = true; clientLog(`first preview shown (${m.template}, ${m.seconds} s)`); }
  } catch (e) {
    if (seq === S.seq) toast(e.message);
  } finally {
    clearTimeout(veilT);
    if (seq === S.seq) {
      $("veil").classList.remove("on");
      S.busy = false;
      updateBuildButton();
    }
  }
}

function renderReport() {
  const m = S.map;
  const b = $("check-badge");
  const warned = m.ok && m.lines.some((l) => l.startsWith("WARNING:"));
  b.textContent = !m.ok ? "PROBLEMS" : warned ? "WARNINGS" : "OK";
  b.className = "badge " + (!m.ok ? "bad" : warned ? "warn" : "ok");
  $("report").innerHTML = m.lines.map((l) => {
    const bad = /\bNO\b|not connected|unreachable for [a-z ]+: [1-9]/.test(l);
    const info = (/^(Spiders|Amphibians|Hovers)/.test(l.trim()) && /\bNO\b/.test(l) && m.movement_profile !== "naval")
      || /optional on naval maps/.test(l);
    return `<li class="${info ? "info" : bad ? "no" : ""}">${esc(l.replace(/\s{2,}/g, " "))}</li>`;
  }).join("");
}

function renderFacts() {
  const m = S.map;
  const players = m.teams.length > 2 && m.teams.every((t) => t.length === 1)
    ? `${m.teams.length}-player free-for-all` : m.teams.map((t) => t.length).join(" vs ");
  const rows = [
    ["Size", `${m.size[0]} × ${m.size[1]}  (${m.W} elmos)`],
    ["Biome", m.biome || "-"],
    ["Players", players],
    ["Metal spots", `${m.mexes.length}  (${m.metal_total} metal)`],
    ["Geo vents", m.geos.length],
    ["Height", `${Math.round(m.height[0])} to ${Math.round(m.height[1])}`],
    ["Preview took", `${m.seconds.toFixed(1)} s`],
  ];
  $("facts").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
}

// hi-res relief once the user zooms in
async function maybeHiRes() {
  const m = S.map;
  if (!m) return;
  const need = S.view.s * m.W * (window.devicePixelRatio || 1);
  const levels = [1024, 2048, 3072].filter((l) => l <= Math.max(1024, (m.grid[0] - 1) * 4));
  let want = levels[0];
  for (const l of levels) if (need > want * 1.25) want = l;
  if (want <= S.img.reliefSize || maybeHiRes.loading === m.id + want) return;
  maybeHiRes.loading = m.id + want;
  try {
    const img = await api(layerUrl("relief", want));
    if (S.map && S.map.id === m.id && want > S.img.reliefSize) {
      S.img.relief = img;
      S.img.reliefSize = want;
      draw();
    }
  } catch (e) { /* keep the low-res picture */ }
  maybeHiRes.loading = null;
}

async function loadRoute(cls) {
  if (!S.map || !cls || S.img.reach[cls]) return;
  const id = S.map.id;
  const img = await api(layerUrl("reach_" + cls));
  if (S.map && S.map.id === id) S.img.reach[cls] = img;
}

// ------------------------------------------------------------------ viewer
const cv = $("map");
const ctx = cv.getContext("2d");

function resize() {
  const r = cv.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.round(r.width * dpr);
  cv.height = Math.round(r.height * dpr);
  draw();
}

function fit() {
  if (!S.map) return;
  const r = cv.getBoundingClientRect();
  const top = $("toolbar").getBoundingClientRect().bottom - r.top + 12;   // keep the map clear of the toolbar
  const bottom = 56;
  const availH = r.height - top - bottom;
  S.view.s = Math.min((r.width - 40) / S.map.W, availH / S.map.H);
  S.view.cx = S.map.W / 2;
  S.view.cy = S.map.H / 2 - (top + availH / 2 - r.height / 2) / S.view.s;
  draw();
}

function zoomAt(f, sx, sy) {
  if (!S.map) return;
  const r = cv.getBoundingClientRect();
  if (sx === undefined) { sx = r.width / 2; sy = r.height / 2; }
  const v = S.view;
  const minS = Math.min(r.width / S.map.W, r.height / S.map.H) * 0.4;
  const ns = Math.min(Math.max(v.s * f, minS), 6);
  const ex = v.cx + (sx - r.width / 2) / v.s;
  const ey = v.cy + (sy - r.height / 2) / v.s;
  v.cx = ex - (sx - r.width / 2) / ns;
  v.cy = ey - (sy - r.height / 2) / ns;
  v.s = ns;
  draw();
  clearTimeout(zoomAt._t);
  zoomAt._t = setTimeout(maybeHiRes, 150);
}

function toScreen(x, z) {
  const r = cv.getBoundingClientRect();
  return [(x - S.view.cx) * S.view.s + r.width / 2, (z - S.view.cy) * S.view.s + r.height / 2];
}
function toMap(sx, sy) {
  const r = cv.getBoundingClientRect();
  return [(sx - r.width / 2) / S.view.s + S.view.cx, (sy - r.height / 2) / S.view.s + S.view.cy];
}

let drawQueued = false;
function draw() {
  if (drawQueued) return;
  drawQueued = true;
  requestAnimationFrame(() => { drawQueued = false; paint(); });
}

function paint() {
  const dpr = window.devicePixelRatio || 1;
  const r = cv.getBoundingClientRect();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#08090b";
  ctx.fillRect(0, 0, r.width, r.height);
  const m = S.map;
  if (!m || !S.img.relief) return;
  const s = S.view.s;
  const [ox, oy] = toScreen(0, 0);
  const w = m.W * s, h = m.H * s;

  ctx.save();
  ctx.shadowColor = "rgba(0,0,0,.6)";
  ctx.shadowBlur = 24;
  ctx.fillStyle = "#000";
  ctx.fillRect(ox, oy, w, h);
  ctx.restore();
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(S.img.relief, ox, oy, w, h);

  if (S.route && S.img.reach[S.route]) ctx.drawImage(S.img.reach[S.route], ox, oy, w, h);
  if (S.layers.hazard && S.img.hazard) ctx.drawImage(S.img.hazard, ox, oy, w, h);
  if (S.layers.gates && S.img.gates) ctx.drawImage(S.img.gates, ox, oy, w, h);
  if (S.layers.grid) drawGrid(ox, oy, w, h);
  if (S.layers.boxes) drawBoxes();
  if (S.layers.gates) drawGateLabels();
  if (S.layers.features && m.features) drawFeatures(m.features);
  if (S.layers.geos) for (const g of m.geos) drawGeo(g[0], g[1]);
  if (S.layers.mexes) for (const x of m.mexes) drawMex(x);
  for (const k of m.marks) drawMark(k);
  if (S.layers.starts) drawStarts();
  drawEditor();
  ctx.strokeStyle = "rgba(255,255,255,.08)";
  ctx.lineWidth = 1;
  ctx.strokeRect(ox + 0.5, oy + 0.5, w - 1, h - 1);
}

function drawGrid(ox, oy, w, h) {
  const m = S.map, s = S.view.s;
  ctx.save();
  ctx.strokeStyle = "rgba(255,255,255,.18)";
  ctx.lineWidth = 1;
  ctx.fillStyle = "rgba(255,255,255,.55)";
  ctx.font = "11px " + getComputedStyle(document.body).fontFamily;
  for (let i = 1; i < m.size[0]; i++) {
    const x = Math.round(ox + i * 512 * s) + 0.5;
    ctx.beginPath(); ctx.moveTo(x, oy); ctx.lineTo(x, oy + h); ctx.stroke();
    if (512 * s > 26) ctx.fillText(String(i), x + 3, oy + 12);
  }
  for (let i = 1; i < m.size[1]; i++) {
    const y = Math.round(oy + i * 512 * s) + 0.5;
    ctx.beginPath(); ctx.moveTo(ox, y); ctx.lineTo(ox + w, y); ctx.stroke();
    if (512 * s > 26) ctx.fillText(String(i), ox + 3, y - 3);
  }
  ctx.restore();
}

function teamColor(team) {                      // same colour as the team's start box
  return TEAM_COLORS[team % TEAM_COLORS.length];
}

function drawBoxes() {
  ctx.save();
  for (const b of S.map.boxes) {
    const col = TEAM_COLORS[b.team % TEAM_COLORS.length];
    for (const poly of b.polygons) {
      ctx.beginPath();
      poly.forEach(([x, z], i) => { const [sx, sy] = toScreen(x, z); i ? ctx.lineTo(sx, sy) : ctx.moveTo(sx, sy); });
      ctx.closePath();
      ctx.fillStyle = col + "1c";
      ctx.fill();
      ctx.setLineDash([7, 5]);
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = col + "cc";
      ctx.stroke();
      ctx.setLineDash([]);
      const xs = poly.map((p) => p[0]), zs = poly.map((p) => p[1]);
      const [lx, ly] = toScreen(Math.min(...xs), Math.min(...zs));
      label(b.name, lx + 6, ly + 6, col, "left", "top");
    }
  }
  ctx.restore();
}

function drawGateLabels() {
  for (const g of S.map.gates) {
    const [x, y] = toScreen(g.x, g.z);
    label(g.name, x, y, "#ffd640", "center", "middle");
  }
}

function label(text, x, y, color, align, base) {
  ctx.save();
  ctx.font = "600 11.5px " + getComputedStyle(document.body).fontFamily;
  ctx.textAlign = align;
  ctx.textBaseline = base;
  const w = ctx.measureText(text).width;
  const bx = align === "center" ? x - w / 2 - 5 : x - 5;
  const by = base === "middle" ? y - 9 : y - 3;
  ctx.fillStyle = "rgba(10,11,14,.78)";
  roundRect(bx, by, w + 10, 18, 4);
  ctx.fill();
  ctx.fillStyle = color;
  ctx.fillText(text, x, base === "middle" ? y + 0.5 : y + 0.5);
  ctx.restore();
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function mexRadius(metal) { return Math.max(3.2, Math.min(15, (22 + metal * 9) * S.view.s)); }

function drawMex(x) {
  const [sx, sy] = toScreen(x.x, x.z);
  const r = mexRadius(x.metal);
  ctx.beginPath();
  ctx.arc(sx, sy, r, 0, Math.PI * 2);
  ctx.fillStyle = "#3cc8ff";
  ctx.fill();
  ctx.lineWidth = Math.max(1, r * 0.22);
  ctx.strokeStyle = "#fff";
  ctx.stroke();
  if (r > 9) {
    ctx.fillStyle = "#04212e";
    ctx.font = `700 ${Math.round(r * 0.8)}px ` + getComputedStyle(document.body).fontFamily;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(x.metal.toFixed(1), sx, sy + 0.5);
  }
}

function drawFeatures(list) {
  const r = Math.max(1.6, Math.min(7, 26 * S.view.s));
  const cols = { rock: "#b9b2a6", crystal: "#5ff0d2", wreck: "#d08a52" };
  ctx.save();
  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(0,0,0,.65)";
  for (const [x, z, kind] of list) {
    const [sx, sy] = toScreen(x, z);
    ctx.fillStyle = cols[kind] || "#ccc";
    ctx.beginPath();
    if (kind === "wreck") ctx.rect(sx - r, sy - r * 0.7, r * 2, r * 1.4);
    else if (kind === "crystal") { ctx.moveTo(sx, sy - r * 1.3); ctx.lineTo(sx + r, sy); ctx.lineTo(sx, sy + r * 1.3); ctx.lineTo(sx - r, sy); ctx.closePath(); }
    else ctx.arc(sx, sy, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function drawGeo(x, z) {
  const [sx, sy] = toScreen(x, z);
  const r = Math.max(5, Math.min(16, 48 * S.view.s));
  ctx.fillStyle = "#ff7a1a";
  ctx.strokeStyle = "#000";
  ctx.lineWidth = 1.5;
  ctx.fillRect(sx - r, sy - r, r * 2, r * 2);
  ctx.strokeRect(sx - r, sy - r, r * 2, r * 2);
}

function drawMark(k) {
  const [sx, sy] = toScreen(k.x, k.z);
  const r = Math.max(10, Math.min(24, 80 * S.view.s));
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const a = Math.PI / 6 + (i * Math.PI) / 3;
    i ? ctx.lineTo(sx + r * Math.cos(a), sy + r * Math.sin(a)) : ctx.moveTo(sx + r * Math.cos(a), sy + r * Math.sin(a));
  }
  ctx.closePath();
  ctx.fillStyle = rgb(k.color);
  ctx.fill();
  ctx.strokeStyle = "#000";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.fillStyle = "#000";
  ctx.font = `700 ${Math.round(r * 0.75)}px ` + getComputedStyle(document.body).fontFamily;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(k.text, sx, sy + 0.5);
}

function drawStarts() {
  const ffa = S.map.teams.length > 2 && S.map.teams.every((t) => t.length === 1);   // number the players
  S.map.teams.forEach((team, ti) => {
    team.forEach((p, i) => {
      const [sx, sy] = toScreen(p[0], p[1]);
      const r = Math.max(9, Math.min(20, 70 * S.view.s));
      const col = teamColor(ti);
      ctx.beginPath();
      ctx.arc(sx, sy, r + 3, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(0,0,0,.55)";
      ctx.fill();
      ctx.beginPath();
      ctx.arc(sx, sy, r, 0, Math.PI * 2);
      ctx.fillStyle = col;
      ctx.fill();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = "#0b0b0b";
      ctx.stroke();
      ctx.fillStyle = "#0b0b0b";
      ctx.font = `800 ${Math.round(r * 0.95)}px ` + getComputedStyle(document.body).fontFamily;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(ffa ? ti + 1 : i + 1), sx, sy + 1);
    });
  });
}

// mouse: pan, zoom, readout
let drag = null;
cv.addEventListener("pointerdown", (e) => {
  drag = { x: e.clientX, y: e.clientY, cx: S.view.cx, cy: S.view.cy };
  cv.setPointerCapture(e.pointerId);
  cv.classList.add("drag");
});
cv.addEventListener("pointermove", (e) => {
  if (drag) {
    S.view.cx = drag.cx - (e.clientX - drag.x) / S.view.s;
    S.view.cy = drag.cy - (e.clientY - drag.y) / S.view.s;
    draw();
  }
  readout(e);
});
const endDrag = () => { drag = null; cv.classList.remove("drag"); maybeHiRes(); };
cv.addEventListener("pointerup", endDrag);
cv.addEventListener("pointercancel", endDrag);
cv.addEventListener("pointerleave", () => { if (!drag) $("readout").innerHTML = "Scroll to zoom, drag to move"; });
cv.addEventListener("wheel", (e) => {
  e.preventDefault();
  const r = cv.getBoundingClientRect();
  zoomAt(Math.exp(-e.deltaY * 0.0016), e.clientX - r.left, e.clientY - r.top);
}, { passive: false });
cv.addEventListener("dblclick", (e) => {
  const r = cv.getBoundingClientRect();
  zoomAt(e.shiftKey ? 0.5 : 2, e.clientX - r.left, e.clientY - r.top);
});

function readout(e) {
  const m = S.map, g = S.grid;
  if (!m || !g) return;
  const r = cv.getBoundingClientRect();
  const sx = e.clientX - r.left, sy = e.clientY - r.top;
  const [x, z] = toMap(sx, sy);
  if (x < 0 || z < 0 || x > m.W || z > m.H) { $("readout").innerHTML = "Outside the map"; return; }
  const ix = Math.min(g.nx - 1, Math.round(x / 8)), iz = Math.min(g.nz - 1, Math.round(z / 8));
  const i = iz * g.nx + ix;
  const bits = g.cells[i];
  let html = `<span>x <b>${Math.round(x)}</b> z <b>${Math.round(z)}</b></span><span>height <b>${g.height[i]}</b></span>`;
  if (bits & 64) html += `<span class="cls lava">Lava - nobody survives</span>`;
  else {
    html += S.info.classes.map((c, k) => `<span class="cls ${(bits >> k) & 1 ? "y" : ""}">${CLASS_NAMES[c]}</span>`).join("");
    if (bits & 128) html += `<span class="cls lava">Damaging ground</span>`;
    if (bits & 32) html += `<span class="cls ev">${esc(m.event_label || "event zone")}</span>`;
    if (m.movement_profile === "naval") html += `<span class="cls ${g.height[i] < -15 ? "y" : ""}">Ships</span>`;
  }
  let best = null, bd = 1e9;
  for (const mx of m.mexes) {
    const [px, py] = toScreen(mx.x, mx.z);
    const d = Math.hypot(px - sx, py - sy);
    if (d < bd) { bd = d; best = mx; }
  }
  if (best && bd < mexRadius(best.metal) + 4) html += `<span>metal spot <b>${best.metal.toFixed(1)}</b></span>`;
  $("readout").innerHTML = html;
}

// toolbar
function syncToolbar() {
  for (const b of document.querySelectorAll("#layers button")) b.classList.toggle("on", !!S.layers[b.dataset.layer]);
  for (const b of document.querySelectorAll("#routes button")) b.classList.toggle("on", b.dataset.route === S.route);
  updateLegend();
}
function toggleLayer(k) {
  S.layers[k] = !S.layers[k];
  store("layers", S.layers);
  syncToolbar();
  draw();
}
async function setRoute(cls) {
  S.route = S.route === cls ? "" : cls;
  syncToolbar();
  if (S.route) {
    try { await loadRoute(S.route); } catch (e) { toast(e.message); }
  }
  draw();
}
function updateLegend() {
  const l = $("legend");
  if (!S.route || !S.map) { l.innerHTML = ""; return; }
  const line = S.map.lines.find((x) => x.trim().toLowerCase().startsWith(S.route)) || "";
  l.innerHTML = `<span class="key"></span>out of reach &middot; ${esc(line.replace(/\s{2,}/g, " "))}`;
}
document.querySelectorAll("#layers button").forEach((b) => (b.onclick = () => toggleLayer(b.dataset.layer)));
document.querySelectorAll("#routes button").forEach((b) => (b.onclick = () => setRoute(b.dataset.route)));
$("z-in").onclick = () => zoomAt(1.5);
$("z-out").onclick = () => zoomAt(1 / 1.5);
$("z-fit").onclick = fit;

// ------------------------------------------------------------------ build
function mapName(title, v) {
  return `${S.info.settings.config.prefix} ${title} v${v}`;
}
function updateName() {
  $("mapname").textContent = mapName($("title").value.trim() || "...", $("version").value || 1);
}
let verTimer = null;
function refreshVersions() {
  clearTimeout(verTimer);
  verTimer = setTimeout(async () => {
    const title = $("title").value.trim();
    if (!title) return;
    try {
      const v = await api("versions?title=" + encodeURIComponent(title));
      refreshVersions.existing = v.existing;
      if (!refreshVersions.manual) $("version").value = v.suggested;
      versionNote();
      updateName();
    } catch (e) { /* not important */ }
  }, 200);
}
refreshVersions.existing = [];
function versionNote() {
  const ex = refreshVersions.existing || [];
  const v = parseInt($("version").value, 10);
  const n = $("version-note");
  if (ex.includes(v)) {
    n.innerHTML = `<b>v${v}</b> of this map already exists. A changed map needs a new version number, otherwise players get download conflicts.`;
    n.className = "note warn";
  } else if (ex.length) {
    n.textContent = `Existing versions: ${ex.map((x) => "v" + x).join(", ")}.`;
    n.className = "note";
  } else n.className = "note hidden";
}
$("title").addEventListener("input", () => {
  S.titleEdited[S.tpl.id] = true;
  S.titles[S.tpl.id] = $("title").value;
  store("titleEdited", S.titleEdited);
  store("titles", S.titles);
  refreshVersions.manual = false;
  updateName();
  refreshVersions();
});
$("version").addEventListener("input", () => { refreshVersions.manual = true; versionNote(); updateName(); });

function updateBuildButton() {
  const b = $("btn-build");
  const running = S.job && S.job.state === "running";
  b.disabled = !S.map || S.busy || running || !hasAuthor();
  b.classList.toggle("warn", !!S.map && !S.map.ok);
  b.title = hasAuthor() ? "" : "Set your author name in Settings first";
  b.textContent = running ? "Building..." : !hasAuthor() ? "Build map (author name needed)"
    : S.map && !S.map.ok ? "Build anyway (check found problems)" : "Build map";
}

$("btn-build").onclick = async () => {
  if (!S.map) return;
  $("result").classList.add("hidden");
  unlockAudio();
  try {
    const job = await api("build", { id: S.map.id, title: $("title").value.trim(), version: parseInt($("version").value, 10), install: $("install").checked });
    S.job = job;
    $("progress").classList.remove("hidden");
    $("logbox").classList.remove("hidden");
    updateBuildButton();
    pollJob(job.id);
  } catch (e) {
    toast(e.message);
  }
};

async function pollJob(id) {
  let j;
  try { j = await api("job/" + id); } catch (e) { toast(e.message); return; }
  S.job = j;
  $("bar").style.width = Math.round(j.progress * 100) + "%";
  $("phase").textContent = j.phase;
  $("elapsed").textContent = Math.round(j.seconds) + " s";
  $("log").textContent = j.log.join("\n");
  if (j.state === "running") { setTimeout(() => pollJob(id), 500); return; }
  updateBuildButton();
  const r = $("result");
  r.classList.remove("hidden");
  if (j.state === "done") {
    const res = j.result;
    r.className = "result";
    r.innerHTML = `<div class="ttl">${esc(res.name)} is ready</div>
      <code>${esc(res.file)}</code> &middot; ${(res.bytes / 1e6).toFixed(1)} MB &middot; ${Math.round(j.seconds)} s
      ${res.installed ? `<p>Installed into Zero-K. In the lobby, switch off <b>Only show featured maps</b> to see it.</p>` : ""}
      ${res.warning ? `<p class="warnline">${esc(res.warning)}</p>` : ""}
      <div class="acts"><button class="ghost" id="open-file">Show file</button>${res.installed ? `<button class="ghost" id="open-inst">Show in Zero-K maps</button>` : ""}</div>
      <div class="support">Enjoying Atlas Map Forge? Support me on Ko-fi to help development.
        <button class="kofi" id="kofi-result">Support on Ko-fi</button></div>`;
    $("kofi-result").onclick = openKofi;
    $("open-file").onclick = () => api("open", { path: res.path }).catch((e) => toast(e.message));
    if (res.installed) $("open-inst").onclick = () => api("open", { path: res.installed }).catch((e) => toast(e.message));
    refreshVersions.manual = false;
    refreshVersions();
    showDone(res, j.seconds);
  } else {
    r.className = "result err";
    r.innerHTML = `<div class="ttl">Build failed</div>${esc(j.error || "unknown error")}`;
  }
}

// ------------------------------------------------------------------ settings
let pickAvailable = false;
window.addEventListener("pywebviewready", () => { pickAvailable = true; });
function openSettings() {
  const st = S.info.settings, c = st.config;
  $("s-author").value = c.author;
  $("s-zerok").value = c.zerok || "";
  $("s-zerok").placeholder = st.zerok_found[0] || "not found - please choose the folder";
  $("s-zerok-found").textContent = st.zerok_found.length ? "Found automatically: " + st.zerok_found.join(", ") + " (leave empty to use it)" : "Zero-K was not found automatically.";
  $("s-outdir").value = c.outdir || "";
  $("s-outdir").placeholder = st.default_outdir;
  $("s-projdir").value = c.projdir || "";
  $("s-projdir").placeholder = st.default_projdir;
  $("s-advanced").checked = !!c.advanced;
  $("s-check-res").classList.add("hidden");
  $("s-check-pick").classList.toggle("hidden", !pickAvailable);
  for (const b of document.querySelectorAll("[data-pick]")) b.classList.toggle("hidden", !pickAvailable);
  $("s-error").classList.add("hidden");
  $("settings").classList.remove("hidden");
  $("s-author").focus();
}
document.querySelectorAll("[data-pick]").forEach((b) => (b.onclick = async () => {
  const inp = $(b.dataset.pick);
  const p = await window.pywebview.api.pick_folder(inp.value || inp.placeholder || "");
  if (p) inp.value = p;
}));
$("s-cancel").onclick = () => $("settings").classList.add("hidden");
$("s-save").onclick = async () => {
  try {
    const wasAdv = isAdvanced();
    const st = await api("config", {
      author: $("s-author").value.trim(), zerok: $("s-zerok").value.trim(), outdir: $("s-outdir").value.trim(),
      projdir: $("s-projdir").value.trim(),
      advanced: $("s-advanced").checked,
    });
    S.info.settings = st;
    $("settings").classList.add("hidden");
    renderWho();
    if (wasAdv !== isAdvanced()) {
      for (const id of Object.keys(S.values)) clampValues(id);
      store("values", S.values);
      renderParams();
      schedulePreview(0);
    }
    updateName();
    refreshVersions();
  } catch (e) {
    $("s-error").textContent = e.message;
    $("s-error").classList.remove("hidden");
  }
};
$("s-advanced").addEventListener("change", () => {
  if ($("s-advanced").checked && !isAdvanced()) {          // turning it on needs a confirmation
    $("s-advanced").checked = false;
    $("adv-warn").classList.remove("hidden");
  }
});
$("adv-cancel").onclick = () => $("adv-warn").classList.add("hidden");
$("adv-ok").onclick = () => { $("adv-warn").classList.add("hidden"); $("s-advanced").checked = true; };
$("s-check-pick").onclick = async () => {
  const p = await window.pywebview.api.pick_file($("s-check").value || "");
  if (p) { $("s-check").value = p; $("s-check-go").click(); }
};
$("s-check-go").onclick = async () => {
  const out = $("s-check-res");
  out.classList.remove("hidden", "yes", "no");
  out.textContent = "Checking...";
  try {
    const r = await api("verify", { path: $("s-check").value.trim() });
    out.textContent = r.text;
    out.classList.add(r.forge ? "yes" : "no");
  } catch (e) {
    out.textContent = e.message;
    out.classList.add("no");
  }
};
function openKofi() {
  api("link", { to: "kofi" }).catch(() => window.open(S.info.support_url, "_blank"));
}
$("btn-kofi").onclick = openKofi;
$("btn-settings").onclick = openSettings;
$("fix-author").onclick = (e) => { e.preventDefault(); openSettings(); };

// ------------------------------------------------------------------ misc wiring
$("btn-preview").onclick = () => schedulePreview(0);
$("btn-dice").onclick = () => { $("seed").value = 1 + Math.floor(Math.random() * 99999); schedulePreview(0); };
$("seed").addEventListener("change", () => schedulePreview(0));
$("auto").checked = recall("auto", true);
$("auto").onchange = () => store("auto", $("auto").checked);

document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
  if (!$("picker").classList.contains("hidden")) { if (e.key === "Escape") closePicker(); return; }
  if (!$("adv-warn").classList.contains("hidden")) { if (e.key === "Escape") $("adv-warn").classList.add("hidden"); return; }
  if (!$("settings").classList.contains("hidden")) { if (e.key === "Escape") $("settings").classList.add("hidden"); return; }
  const k = e.key.toLowerCase();
  if (k === "f") fit();
  else if (k === "+" || k === "=") zoomAt(1.5);
  else if (k === "-") zoomAt(1 / 1.5);
  else if (k === "r") $("btn-dice").click();
  else if (k === "t") { e.preventDefault(); openPicker(); }
  else if (k === "m") toggleLayer("mexes");
  else if (k === "s") toggleLayer("starts");
  else if (k === "b") toggleLayer("boxes");
  else if (k === "g") toggleLayer("grid");
  else if (k >= "0" && k <= "5") setRoute(["", ...S.info.classes][+k]);
});

new ResizeObserver(resize).observe(cv);
init();

// ------------------------------------------------------------------ build finished dialog
let audioCtx = null;
function unlockAudio() {
  // created on the click that starts the build, so the browser allows the sound later
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
  } catch (e) { audioCtx = null; }
}

function playDone() {
  // short rising anvil-like chime (three bell tones), made in code: no sound file needed
  try {
    unlockAudio();
    if (!audioCtx) return;
    const t0 = audioCtx.currentTime + 0.02;
    const out = audioCtx.createGain();
    out.gain.value = 0.22;
    out.connect(audioCtx.destination);
    [[523.25, 0], [659.25, 0.12], [1046.5, 0.24]].forEach(([f, dt]) => {
      for (const [mul, vol] of [[1, 1], [2.76, 0.25], [5.4, 0.08]]) {
        const o = audioCtx.createOscillator(), g = audioCtx.createGain();
        o.type = "sine";
        o.frequency.value = f * mul;
        g.gain.setValueAtTime(0, t0 + dt);
        g.gain.linearRampToValueAtTime(vol, t0 + dt + 0.008);
        g.gain.exponentialRampToValueAtTime(0.0008, t0 + dt + (mul === 1 ? 1.4 : 0.5));
        o.connect(g); g.connect(out);
        o.start(t0 + dt); o.stop(t0 + dt + 1.5);
      }
    });
  } catch (e) { /* no sound is fine */ }
}

function showDone(res, seconds) {
  $("done-name").textContent = res.name;
  $("done-meta").textContent = `${(res.bytes / 1e6).toFixed(1)} MB \u00b7 built in ${Math.round(seconds)} s`;
  $("done-note").innerHTML = res.installed
    ? "Installed into Zero-K. In the lobby, switch off <b>Only show featured maps</b> to find it."
    : esc(res.warning || "Saved to your output folder.");
  const shot = $("done-shot");
  try {
    const src = S.img && S.img.relief;
    if (!src) throw new Error("no preview");
    const c = document.createElement("canvas");
    const w = src.naturalWidth || src.width, h = src.naturalHeight || src.height, k = Math.min(1, 600 / Math.max(w, h));
    c.width = Math.round(w * k); c.height = Math.round(h * k);
    c.getContext("2d").drawImage(src, 0, 0, c.width, c.height);
    shot.src = c.toDataURL("image/jpeg", 0.88);
    shot.classList.remove("hidden");
  } catch (e) { shot.classList.add("hidden"); }
  const acts = $("done-acts");
  acts.innerHTML = `<button class="ghost" id="done-file">Show file</button>`
    + (res.installed ? `<button class="ghost" id="done-inst">Show in Zero-K maps</button>` : "");
  $("done-file").onclick = () => api("open", { path: res.path }).catch((e) => toast(e.message));
  if (res.installed) $("done-inst").onclick = () => api("open", { path: res.installed }).catch((e) => toast(e.message));
  $("done").classList.remove("hidden");
  playDone();
  setTimeout(() => $("done-close").focus(), 50);
}
const closeDone = () => $("done").classList.add("hidden");
$("done-close").onclick = closeDone;
$("done-kofi").onclick = openKofi;
$("done").addEventListener("click", (e) => { if (e.target.id === "done") closeDone(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("done").classList.contains("hidden")) closeDone(); });

// the page itself never scrolls (only the side panels do); undo any scroll a focus change caused
window.addEventListener("scroll", () => { if (scrollX || scrollY) scrollTo(0, 0); });
