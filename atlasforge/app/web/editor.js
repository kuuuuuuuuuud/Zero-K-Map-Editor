// Atlas Map Forge - editor stage A: move / add / delete metal spots, geovents and start points.
// State lives in S.edits (a list, see atlasforge/edits.py); the server applies it to the generated design.
"use strict";

const ED = {
  on: false,
  tool: "move",
  sel: null,            // { kind, x, z } selected metal spot (for the metal field)
  drag: null,           // { kind, ref, x, z } while a spot is being dragged
  hover: null,          // map position under the pointer (add tools)
  pending: null,        // ghosts that stay until the server answered
  last: null,           // { tpl, values, seed } the current map was generated with
  seq: 0,
  timer: null,
  base: {},             // fields of a loaded project file we do not know (kept when saving)
};

// ------------------------------------------------------------------ symmetry (mirrors atlasforge/symmetry.py)
function edOrbit(x, z) {
  const sy = S.map && S.map.sym;
  if (!sy || !S.symmetry) return [[x, z]];
  const W = S.map.W, H = S.map.H;
  if (sy.kind === "rot") {
    const out = [];
    for (let k = 0; k < sy.n; k++) {
      const a = 2 * Math.PI * k / sy.n, dx = x - W / 2, dz = z - H / 2;
      out.push([W / 2 + dx * Math.cos(a) - dz * Math.sin(a), H / 2 + dx * Math.sin(a) + dz * Math.cos(a)]);
    }
    return out;
  }
  if (sy.layout === "ew") return [[x, z], [W - x, z]];
  if (sy.layout === "ns") return [[x, z], [x, H - z]];
  return [[x, z], [W - x, H - z]];
}

// ------------------------------------------------------------------ settings guard (decision: confirm before regenerating)
function edSettingsKey() {
  const seed = Math.max(1, parseInt($("seed").value, 10) || 1);
  return JSON.stringify([S.tpl.id, S.values[S.tpl.id], seed]);
}

function edAsk() {
  return new Promise((resolve) => {
    const box = $("ed-confirm");
    const done = (v) => { box.classList.add("hidden"); $("ed-ok").onclick = $("ed-cancel").onclick = null; resolve(v); };
    $("ed-ok").onclick = () => done(true);
    $("ed-cancel").onclick = () => done(false);
    box.classList.remove("hidden");
  });
}

async function editorGuard() {
  if (!S.edits.length || !ED.last || edSettingsKey() === ED.last.key) return true;
  if (ED.asking) return false;
  ED.asking = true;
  try {
    if (await edAsk()) { S.edits = []; S.redo = []; edUpdateUi(); return true; }
    // cancelled: put the old settings back, the map stays untouched
    S.values[ED.last.tpl] = JSON.parse(ED.last.values);
    store("values", S.values);
    $("seed").value = ED.last.seed;
    if (S.tpl.id !== ED.last.tpl) selectTemplate(ED.last.tpl); else renderParams();
    return false;
  } finally { ED.asking = false; }
}

function editorAfterPreview(m, seed) {
  S.edits = m.edits || [];
  S.redo = [];
  S.symmetry = m.symmetry !== false;
  $("ed-sym").checked = S.symmetry;
  ED.last = { key: JSON.stringify([m.template, m.values, seed]), tpl: m.template, values: JSON.stringify(m.values), seed };
  ED.sel = null;
  edShowProblems(m);
  edUpdateUi();
}

// ------------------------------------------------------------------ sending edits
function edSend(delay = 80) {
  clearTimeout(ED.timer);
  ED.timer = setTimeout(async () => {
    const seq = ++ED.seq;
    try {
      const r = await api("edit", { id: S.map.id, edits: S.edits, symmetry: S.symmetry });
      if (seq !== ED.seq) return;
      // an edit the server refuses is dropped again, with the reason
      const bad = (r.problems || []).filter((p) => p.index === S.edits.length - 1 && ED.fresh);
      if (bad.length) {
        toast(bad[0].reason.charAt(0).toUpperCase() + bad[0].reason.slice(1) + ".");
        S.edits.pop();
        r.problems = r.problems.filter((p) => p !== bad[0]);
        edSend(0);
      }
      const wasFresh = ED.fresh;
      ED.fresh = false;
      const known = new Set((S.map.issues || []).map((i) => `${i.text}|${i.x}|${i.z}`));
      Object.assign(S.map, r);
      const added = (r.issues || []).filter((i) => !known.has(`${i.text}|${i.x}|${i.z}`));
      if (wasFresh && added.length) {                              // a placement just made something invalid
        const worst = added.find((i) => i.level === "error") || added[0];
        toast((worst.level === "error" ? "Problem: " : "Warning: ") + worst.text + (added.length > 1 ? ` (+${added.length - 1} more)` : "") + ".");
      }
      ED.pending = null;
      S.img.reach = {};
      if (S.route) await loadRoute(S.route);
      renderReport();
      renderFacts();
      edShowProblems(S.map);
      edUpdateUi();
      draw();
    } catch (e) { toast(e.message); ED.pending = null; draw(); }
  }, delay);
}

function edCommit(edit) {
  S.edits.push(edit);
  S.redo = [];
  ED.fresh = true;
  edUpdateUi();
  edSend();
}

function edShowProblems(m) {
  const ul = $("report");
  for (const li of ul.querySelectorAll("li.ed-problem")) li.remove();
  for (const p of m.problems || []) {
    const li = document.createElement("li");
    li.className = "no ed-problem";
    li.textContent = `Edit ${p.index + 1} skipped: ${p.reason}`;
    ul.appendChild(li);
  }
}

const edUndo = () => { if (S.edits.length) { S.redo.push(S.edits.pop()); edUpdateUi(); edSend(); } };
const edRedo = () => { if (S.redo.length) { S.edits.push(S.redo.pop()); ED.fresh = false; edUpdateUi(); edSend(); } };

function edUpdateUi() {
  $("ed-toggle").classList.toggle("on", ED.on);
  $("ed-extra").classList.toggle("hidden", !ED.on);
  for (const b of document.querySelectorAll("#ed-extra [data-tool]")) b.classList.toggle("on", b.dataset.tool === ED.tool);
  $("ed-undo").disabled = !S.edits.length;
  $("ed-redo").disabled = !S.redo.length;
  $("ed-count").textContent = S.edits.length ? `${S.edits.length} edit${S.edits.length > 1 ? "s" : ""}` : "";
  cv.classList.toggle("editing", ED.on);
  $("ed-save").disabled = !S.map;
  if (S.map && S.map.sym) $("ed-sym").disabled = false;
}

// ------------------------------------------------------------------ picking and dragging
function edPick(sx, sy) {
  const m = S.map;
  let best = null, bd = 1e9;
  const test = (kind, x, z, rad, ref) => {
    const [px, py] = toScreen(x, z);
    const d = Math.hypot(px - sx, py - sy);
    if (d <= rad + 4 && d < bd) { bd = d; best = { kind, x, z, ref }; }
  };
  for (const g of m.geos) test("geo", g[0], g[1], Math.max(6, Math.min(16, 48 * S.view.s)) * 1.3, g);
  for (const mx of m.mexes) test("mex", mx.x, mx.z, mexRadius(mx.metal), mx);
  m.teams.forEach((team) => team.forEach((p) => test("start", p[0], p[1], Math.max(9, Math.min(20, 70 * S.view.s)), p)));
  return best || edBoxPick(sx, sy);
}

// ------------------------------------------------------------------ start boxes (set_box)
// A rectangular polygon (4 axis-aligned points) resizes at its corners; any polygon moves from its inside.
function edRect(poly) {
  return poly.length === 4 && poly.every((p, i) => {
    const q = poly[(i + 1) % 4];
    return Math.abs(p[0] - q[0]) < 1e-6 || Math.abs(p[1] - q[1]) < 1e-6;
  });
}

function edInside(poly, x, z) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) c = !c;
  }
  return c;
}

function edBoxPick(sx, sy) {
  const [mx, mz] = toMap(sx, sy);
  let inside = null;
  for (const b of S.map.boxes || []) {
    for (let pi = 0; pi < b.polygons.length; pi++) {
      const poly = b.polygons[pi], ref = { team: b.team, poly: pi, pts: poly };
      if (edRect(poly)) {
        const ci = poly.findIndex((p) => Math.hypot(toScreen(p[0], p[1])[0] - sx, toScreen(p[0], p[1])[1] - sy) <= 9);
        if (ci >= 0) return { kind: "boxcorner", x: poly[ci][0], z: poly[ci][1], ref: { ...ref, corner: ci } };
      }
      if (!inside && edInside(poly, mx, mz)) inside = { kind: "box", x: mx, z: mz, ref };
    }
  }
  return inside;
}

// points of the box while it is dragged: d.cur is the pointer (box) or the grabbed corner (boxcorner)
function edBoxPts(d) {
  const pts = d.ref.pts, W = S.map.W, H = S.map.H;
  const xs = pts.map((p) => p[0]), zs = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
  if (d.kind === "boxcorner") {
    const c = pts[d.ref.corner];
    const a = c[0] === x0 ? [d.cur[0], x1] : [x0, d.cur[0]];
    const b = c[1] === z0 ? [d.cur[1], z1] : [z0, d.cur[1]];
    const [ax, bx] = [Math.min(...a), Math.max(...a)], [az, bz] = [Math.min(...b), Math.max(...b)];
    return [[ax, az], [bx, az], [bx, bz], [ax, bz]].map((p) => [Math.round(p[0]), Math.round(p[1])]);
  }
  const dx = Math.min(Math.max(d.cur[0] - d.x, -x0), W - x1), dz = Math.min(Math.max(d.cur[1] - d.z, -z0), H - z1);
  return pts.map((p) => [Math.round(p[0] + dx), Math.round(p[1] + dz)]);
}

const edPos = (e) => {
  const r = cv.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
};
const edClamp = (p) => [Math.min(Math.max(p[0], 0), S.map.W), Math.min(Math.max(p[1], 0), S.map.H)];

cv.addEventListener("pointerdown", (e) => {
  if (!ED.on || !S.map || e.button !== 0) return;
  const [sx, sy] = edPos(e);
  const hit = edPick(sx, sy);
  const [mx, mz] = edClamp(toMap(sx, sy));
  if (ED.tool === "move") {
    if (!hit) return;                                  // empty ground: normal panning
    e.stopImmediatePropagation();
    ED.sel = hit.kind === "mex" ? hit : null;
    if (ED.sel) $("ed-metal").value = hit.ref.metal;
    ED.drag = { kind: hit.kind, x: hit.x, z: hit.z, cur: [hit.x, hit.z], ref: hit.ref };
    cv.setPointerCapture(e.pointerId);
    draw();
  } else if (ED.tool === "del") {
    e.stopImmediatePropagation();
    if (!hit) return;
    if (hit.kind === "start") { toast("Start points cannot be deleted."); return; }
    if (hit.kind.startsWith("box")) { toast("Start boxes cannot be deleted, drag them instead."); return; }
    ED.pending = null;
    edCommit({ op: "del_" + hit.kind, at: [hit.x, hit.z] });
  } else {                                             // mex / geo: add
    e.stopImmediatePropagation();
    if (ED.tool === "mex") {
      const metal = Math.min(9, Math.max(0.1, parseFloat($("ed-metal").value) || 2));
      edCommit({ op: "add_mex", at: [Math.round(mx), Math.round(mz)], metal });
    } else edCommit({ op: "add_geo", at: [Math.round(mx), Math.round(mz)] });
  }
}, true);

cv.addEventListener("pointermove", (e) => {
  if (!S.map) return;
  const [hx, hy] = edPos(e);
  const prev = ED.issueHover;
  ED.issueHover = (S.map.issues || []).find((i) => {
    const [ix, iy] = toScreen(i.x, i.z);
    return Math.hypot(ix - hx, iy - hy) < 24;
  }) || null;
  if (prev !== ED.issueHover && !ED.drag) draw();
}, true);

cv.addEventListener("pointermove", (e) => {
  if (!ED.on || !S.map) return;
  const [sx, sy] = edPos(e);
  if (ED.drag) {
    e.stopImmediatePropagation();
    ED.drag.cur = edClamp(toMap(sx, sy));
    draw();
  } else if (ED.tool === "mex" || ED.tool === "geo") {
    ED.hover = edClamp(toMap(sx, sy));
    draw();
  }
}, true);

const edEnd = (e) => {
  if (!ED.drag) return;
  e.stopImmediatePropagation();
  const d = ED.drag;
  ED.drag = null;
  const moved = Math.hypot(d.cur[0] - d.x, d.cur[1] - d.z) * S.view.s > 3;   // a click only selects
  if (moved && d.kind.startsWith("box")) {
    edCommit({ op: "set_box", team: d.ref.team, poly: d.ref.poly, points: edBoxPts(d) });
  } else if (moved) {
    ED.pending = { kind: d.kind, pts: edOrbit(d.cur[0], d.cur[1]) };
    edCommit({ op: "move_" + d.kind, from: [d.x, d.z], to: [Math.round(d.cur[0]), Math.round(d.cur[1])] });
  }
  draw();
};
cv.addEventListener("pointerup", edEnd, true);
cv.addEventListener("pointercancel", edEnd, true);
cv.addEventListener("pointerleave", () => { ED.hover = null; if (ED.on) draw(); });

// ------------------------------------------------------------------ drawing
function drawEditor() {
  if (!S.map) return;
  for (const i of S.map.issues || []) {                            // live checks: red = error, yellow = warning
    const [sx, sy] = toScreen(i.x, i.z);
    ctx.beginPath();
    ctx.arc(sx, sy, 18, 0, Math.PI * 2);
    ctx.lineWidth = 3;
    ctx.strokeStyle = i.level === "error" ? "#ff4d4d" : "#ffd23c";
    ctx.stroke();
    ctx.fillStyle = ctx.strokeStyle;                               // "!" badge so the warning is visible on any terrain
    ctx.beginPath();
    ctx.arc(sx + 14, sy - 14, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#111";
    ctx.font = "bold 11px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("!", sx + 14, sy - 13);
  }
  const hi = ED.issueHover;                                        // tooltip with the reason, next to the object
  if (hi) {
    const [sx, sy] = toScreen(hi.x, hi.z);
    ctx.font = "12px sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    const w = ctx.measureText(hi.text).width + 12;
    const tx = Math.min(sx + 24, cv.width - w - 4), ty = Math.max(sy - 30, 14);
    ctx.fillStyle = "rgba(20,20,20,.92)";
    ctx.fillRect(tx, ty - 11, w, 22);
    ctx.strokeStyle = hi.level === "error" ? "#ff4d4d" : "#ffd23c";
    ctx.lineWidth = 1;
    ctx.strokeRect(tx, ty - 11, w, 22);
    ctx.fillStyle = "#fff";
    ctx.fillText(hi.text, tx + 6, ty);
  }
  if (!ED.on) return;
  if (ED.tool === "move") {                            // corner handles of rectangular start boxes
    for (const b of S.map.boxes || []) for (const poly of b.polygons) if (edRect(poly)) for (const p of poly) {
      const [sx, sy] = toScreen(p[0], p[1]);
      ctx.fillStyle = "#fff";
      ctx.fillRect(sx - 4, sy - 4, 8, 8);
    }
  }
  if (ED.drag && ED.drag.kind.startsWith("box")) {     // live preview of the box being dragged
    const pts = edBoxPts(ED.drag);
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#fff";
    ctx.beginPath();
    pts.forEach((p, i) => { const [sx, sy] = toScreen(p[0], p[1]); i ? ctx.lineTo(sx, sy) : ctx.moveTo(sx, sy); });
    ctx.closePath();
    ctx.stroke();
    ctx.restore();
  }
  const ghost = (kind, pts, strong) => {
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#fff";
    ctx.fillStyle = kind === "geo" ? "rgba(255,122,26,.45)" : kind === "start" ? "rgba(255,255,255,.3)" : "rgba(60,200,255,.45)";
    pts.forEach((p, i) => {
      const [sx, sy] = toScreen(p[0], p[1]);
      ctx.globalAlpha = i === 0 || strong ? 1 : 0.7;
      ctx.beginPath();
      if (kind === "geo") ctx.rect(sx - 8, sy - 8, 16, 16);
      else ctx.arc(sx, sy, kind === "start" ? 14 : mexRadius(2), 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });
    ctx.restore();
  };
  if (ED.drag && !ED.drag.kind.startsWith("box")) ghost(ED.drag.kind, edOrbit(ED.drag.cur[0], ED.drag.cur[1]), true);
  else if (ED.pending) ghost(ED.pending.kind, ED.pending.pts, false);
  else if (ED.hover && (ED.tool === "mex" || ED.tool === "geo")) ghost(ED.tool, edOrbit(ED.hover[0], ED.hover[1]), false);
  if (ED.sel && ED.sel.ref) {
    const [sx, sy] = toScreen(ED.sel.ref.x, ED.sel.ref.z);
    ctx.beginPath();
    ctx.arc(sx, sy, mexRadius(ED.sel.ref.metal) + 5, 0, Math.PI * 2);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#ffd23c";
    ctx.stroke();
  }
}

// ------------------------------------------------------------------ toolbar and keys
$("ed-toggle").onclick = () => { ED.on = !ED.on; ED.drag = ED.hover = null; edUpdateUi(); draw(); };
for (const b of document.querySelectorAll("#ed-extra [data-tool]")) b.onclick = () => { ED.tool = b.dataset.tool; edUpdateUi(); };
$("ed-undo").onclick = edUndo;
$("ed-redo").onclick = edRedo;
$("ed-sym").onchange = () => { S.symmetry = $("ed-sym").checked; edSend(0); };
$("ed-metal").onchange = () => {
  const v = Math.min(9, Math.max(0.1, parseFloat($("ed-metal").value) || 2));
  if (ED.sel && ED.sel.ref) edCommit({ op: "set_metal", at: [ED.sel.x, ED.sel.z], metal: v });
};

document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, textarea") || !S.map) return;
  if ((e.ctrlKey || e.metaKey) && !e.altKey) {
    const k = e.key.toLowerCase();
    if (k === "z" && !e.shiftKey) { e.preventDefault(); edUndo(); }
    else if (k === "y" || (k === "z" && e.shiftKey)) { e.preventDefault(); edRedo(); }
    return;
  }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (k === "e") { $("ed-toggle").click(); }
  else if (ED.on && k === "v") { ED.tool = "move"; edUpdateUi(); }
  else if (ED.on && k === "1") { ED.tool = "mex"; edUpdateUi(); e.stopImmediatePropagation(); }
  else if (ED.on && k === "2") { ED.tool = "geo"; edUpdateUi(); e.stopImmediatePropagation(); }
  else if (ED.on && k === "x") { ED.tool = "del"; edUpdateUi(); }
}, true);

// ------------------------------------------------------------------ project files (.forge.json)
async function edSave() {
  const title = ($("title").value || S.map.title || "map").trim();
  const data = Object.assign({}, ED.base, {
    template: S.map.template, values: S.map.values, seed: S.map.seed, symmetry: S.symmetry, edits: S.edits, title,
    app_version: S.info.version,
  });
  try {
    const r = await api("project_save", { data });
    toastAction("Project saved: " + r.path, "Open folder", () => api("open", { path: r.path }).catch((e) => toast(e.message)));
  } catch (e) { toast(e.message); }
}

async function edOpen(file) {
  edLoad({ text: await file.text() });
}

async function edLoad(req) {
  try { applyProject(await api("project_load", req)); } catch (e) { toast(e.message); }
}

function applyProject(r) {
  const p = r.project;
  const t = S.info.templates.find((x) => x.id === p.template);
  if (!t) throw new Error("Unknown template: " + p.template);
  ED.base = r.extra || {};
  S.values[p.template] = Object.assign({}, S.values[p.template] || {}, p.values || {});
  S.seeds[p.template] = p.seed;
  S.edits = p.edits || [];
  S.symmetry = p.symmetry !== false;
  ED.last = null;                                    // loading replaces the map: nothing to confirm
  selectTemplate(p.template);
  clearTimeout(pvTimer);
  $("seed").value = p.seed;
  S.titleEdited[p.template] = !!p.title;
  runPreview(true).then(() => { if (p.title) $("title").value = p.title; });
}

$("ed-save").onclick = () => S.map && edSave();
$("ed-open").onclick = async () => {
  if (!pickAvailable) return $("ed-file").click();
  try {
    const p = await window.pywebview.api.pick_project(S.info.settings.projdir || "");
    if (p) edLoad({ path: p });
  } catch (e) { toast(e.message); }
};
$("ed-file").onchange = () => { const f = $("ed-file").files[0]; $("ed-file").value = ""; if (f) edOpen(f); };
edUpdateUi();
