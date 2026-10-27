// Atlas Map Forge - terrain tools: brush (raise/lower/smooth, circle/square, height limit),
// ramp tool and undo/redo of terrain strokes. Strokes are mirrored ew_ns like the object editor.
"use strict";

const SQ = 8;   // elmos per heightmap square (atlasforge.SQ)

const BR = {
  on: false,
  radius: 30,      // brush radius in heightmap pixels (5..300)
  strength: 5,     // raise/lower: elmos per dab (1..400); smooth: smoothing passes (1..50)
  mode: "raise",   // LMB action: raise | lower | smooth (RMB always lowers)
  active: "raise", // what the current pointer button does (for the cursor colour)
  shape: "circle", // circle | square
  limit: null,     // height bound in elmos (max for raise, min for lower) or null
  canUndo: false,
  canRedo: false,
  painting: false,
  cur: null,       // [sx, sy] screen position of the pointer (for the cursor)
  stroke: null,    // { x0, z0, x1, z1 } current stroke in heightmap pixels (preview)
  seq: 0,
};
const RA = {
  on: false,
  a: null,         // [mx, mz] ramp start in elmos
  cur: null,       // [sx, sy] screen position of the pointer
  width: 24,
  start: 0,
  end: 100,
};
function brushEnabled() { return !!(S.map && S.map.template === "editor"); }

async function brEnsureHeightmap() {
  if (!S.map || S.img.heightmap) return;
  try {
    const img = await api(layerUrl("heightmap", 1024));
    if (S.map) { S.img.heightmap = img; draw(); }
  } catch (e) { /* the heightmap layer arrives with the next stroke instead */ }
}

function brSetOn(v) {
  BR.on = !!v;
  if (BR.on && RA.on) RA.on = false;
  if (BR.on && ED.on) { ED.on = false; ED.drag = ED.hover = null; }
  BR.painting = false; BR.stroke = null;
  if (BR.on) brEnsureHeightmap();
  brUpdateUi(); draw();
}

function raSetOn(v) {
  RA.on = !!v;
  if (RA.on && BR.on) brSetOn(false);
  if (RA.on && ED.on) { ED.on = false; ED.drag = ED.hover = null; }
  RA.a = null; RA.cur = null;
  if (RA.on) brEnsureHeightmap();
  brUpdateUi(); draw();
}

function brUpdateUi() {
  const ok = brushEnabled();
  $("brush-tools").classList.toggle("hidden", !ok);
  if (!ok) { cv.classList.remove("brushing"); return; }
  $("brush-mode").classList.toggle("on", BR.on);
  $("ramp-mode").classList.toggle("on", RA.on);
  $("brush-extra").classList.toggle("hidden", !BR.on);
  $("ramp-extra").classList.toggle("hidden", !RA.on);
  for (const b of document.querySelectorAll("#brush-extra [data-br-mode]")) b.classList.toggle("on", b.dataset.brMode === BR.mode);
  for (const b of document.querySelectorAll("#brush-extra [data-br-shape]")) b.classList.toggle("on", b.dataset.brShape === BR.shape);
  $("brush-radius-val").textContent = BR.radius;
  $("brush-strength-val").textContent = BR.strength;
  $("brush-strength-label").textContent = BR.mode === "smooth" ? "Passes" : "Strength";
  const limitOn = BR.mode !== "smooth";
  $("brush-limit").classList.toggle("hidden", !limitOn);
  $("brush-limit-label").classList.toggle("hidden", !limitOn);
  $("brush-limit-label").textContent = BR.mode === "lower" ? "Min H" : "Max H";
  $("ramp-width-val").textContent = RA.width;
  $("br-undo").disabled = !BR.canUndo;
  $("br-redo").disabled = !BR.canRedo;
  cv.classList.toggle("brushing", BR.on || RA.on);
  S.showHeightmap = BR.on || RA.on;
}

// called from editorAfterPreview after every generated preview
function brushAfterPreview() {
  BR.on = false; RA.on = false; RA.a = null; RA.cur = null;
  BR.painting = false; BR.stroke = null;
  BR.canUndo = BR.canRedo = false;
  S.brushVer = 0;
  S.img.heightmap = null;
  S.showHeightmap = false;
  brUpdateUi();
  edUpdateUi();
}

function brImage(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

async function brApplyTerrain(r, check) {
  if (!S.map) return;
  if (r.height) S.map.height = r.height;
  const [relief, heightmap] = await Promise.all([
    r.preview ? brImage(r.preview) : Promise.resolve(null),
    r.heightmap ? brImage(r.heightmap) : Promise.resolve(null),
  ]);
  if (relief) { S.img.relief = relief; S.img.reliefSize = 1024; }
  if (heightmap) S.img.heightmap = heightmap;
  S.img.reach = {};
  S.brushVer = (S.brushVer || 0) + 1;
  if (r.can_undo !== undefined) BR.canUndo = !!r.can_undo;
  if (r.can_redo !== undefined) BR.canRedo = !!r.can_redo;
  brUpdateUi();
  renderFacts();
  draw();
  if (check) {
    if (r.ok !== undefined) S.map.ok = r.ok;
    if (r.lines) S.map.lines = r.lines;
    renderReport();
    updateBuildButton();
    maybeHiRes();
    brReloadGrid();
  }
}

async function brSendLine(x1, y1, x2, y2, check) {
  const seq = ++BR.seq;
  try {
    const r = await api("brush_line", {
      id: S.map.id, x1, y1, x2, y2, radius: BR.radius, strength: BR.strength,
      mode: BR.active, symmetry: "ew_ns", shape: BR.shape,
      limit: (BR.active === BR.mode && BR.mode !== "smooth") ? BR.limit : null,
      check: !!check,
    });
    if (seq !== BR.seq || !S.map) return;
    await brApplyTerrain(r, check);
  } catch (e) { if (seq === BR.seq) toast(e.message); }
}

async function brReloadGrid() {
  if (!S.map) return;
  const v = (S.brushVer || 0) + ":" + Date.now();
  try {
    const [height, cells] = await Promise.all([
      api(`layer/${S.map.id}/height?v=${v}`),
      api(`layer/${S.map.id}/cells?v=${v}`),
    ]);
    if (!S.map) return;
    S.grid = { nx: S.map.grid[0], nz: S.map.grid[1], height: new Int16Array(height), cells: new Uint8Array(cells) };
  } catch (e) { /* the readout keeps its previous values until the next preview */ }
}

function brSnapStroke(px, pz) {
  const s = BR.stroke;
  if (!s) return;
  const dx = px - s.x0, dz = pz - s.z0;
  const len = Math.hypot(dx, dz);
  if (len < 0.5) { s.x1 = s.x0; s.z1 = s.z0; return; }   // below one cell: keep a point dab
  const angle = Math.round(Math.atan2(dz, dx) / (Math.PI / 4)) * (Math.PI / 4);
  s.x1 = s.x0 + len * Math.cos(angle);
  s.z1 = s.z0 + len * Math.sin(angle);
}

async function raSend(x1, y1, x2, y2) {
  const seq = ++BR.seq;
  try {
    const r = await api("ramp", {
      id: S.map.id, x1, y1, x2, y2, width: RA.width,
      start_height: RA.start, end_height: RA.end, symmetry: "ew_ns",
    });
    if (seq !== BR.seq || !S.map) return;
    await brApplyTerrain(r, true);
  } catch (e) { if (seq === BR.seq) toast(e.message); }
}

async function brHistory(kind) {
  if (!S.map) return;
  const seq = ++BR.seq;
  try {
    const r = await api(kind, { id: S.map.id });
    if (seq !== BR.seq || !S.map) return;
    if (r.message) { toast(r.message); brUpdateUi(); return; }
    await brApplyTerrain(r, false);
  } catch (e) { if (seq === BR.seq) toast(e.message); }
}
const brUndo = () => brHistory("undo");
const brRedo = () => brHistory("redo");

function drawBrush() {
  if (!S.map) return;
  if (RA.on && RA.a && RA.cur) {
    const [ax, az] = RA.a;
    const [sx0, sy0] = toScreen(ax, az);
    const [sx1, sy1] = RA.cur;
    const half = (RA.width * SQ * S.view.s) / 2;
    ctx.save();
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(sx0, sy0);
    ctx.lineTo(sx1, sy1);
    ctx.strokeStyle = "rgba(95,211,138,.28)";
    ctx.lineWidth = Math.max(2, half * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(sx0, sy0);
    ctx.lineTo(sx1, sy1);
    ctx.strokeStyle = "#5fd38a";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = "#5fd38a";
    for (const [x, y] of [[sx0, sy0], [sx1, sy1]]) {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
    return;
  }
  if (BR.on && BR.painting && BR.stroke) {
    const [lx0, ly0] = toScreen(BR.stroke.x0 * SQ, BR.stroke.z0 * SQ);
    const [lx1, ly1] = toScreen(BR.stroke.x1 * SQ, BR.stroke.z1 * SQ);
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(lx0, ly0);
    ctx.lineTo(lx1, ly1);
    ctx.strokeStyle = "rgba(95,211,138,.65)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 5]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#5fd38a";
    for (const [x, y] of [[lx0, ly0], [lx1, ly1]]) {
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }
  if (!BR.on || !BR.cur) return;
  const [sx, sy] = BR.cur;
  const rad = Math.max(3, BR.radius * SQ * S.view.s);
  const col = BR.active === "lower" ? "#ff5d4d" : BR.active === "smooth" ? "#46c8ff" : "#5fd38a";
  ctx.save();
  ctx.beginPath();
  if (BR.shape === "square") ctx.rect(sx - rad, sy - rad, rad * 2, rad * 2);
  else ctx.arc(sx, sy, rad, 0, Math.PI * 2);
  ctx.fillStyle = col + "2e";
  ctx.fill();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = col;
  ctx.stroke();
  ctx.restore();
}

// ------------------------------------------------------------------ mouse: paint with the brush
cv.addEventListener("pointerdown", (e) => {
  if (!BR.on || !S.map || (e.button !== 0 && e.button !== 2)) return;
  const r = cv.getBoundingClientRect();
  const [mx, mz] = toMap(e.clientX - r.left, e.clientY - r.top);
  if (mx < 0 || mz < 0 || mx > S.map.W || mz > S.map.H) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  BR.active = e.button === 2 ? "lower" : BR.mode;
  BR.painting = true;
  BR.cur = [e.clientX - r.left, e.clientY - r.top];
  BR.stroke = { x0: mx / SQ, z0: mz / SQ, x1: mx / SQ, z1: mz / SQ };
  cv.setPointerCapture(e.pointerId);
  brUpdateUi();
  draw();
}, true);

cv.addEventListener("pointermove", (e) => {
  if (!S.map) return;
  const r = cv.getBoundingClientRect();
  const sx = e.clientX - r.left, sy = e.clientY - r.top;
  if (BR.on) {
    BR.cur = [sx, sy];
    if (BR.painting) {
      e.stopImmediatePropagation();
      const [mx, mz] = toMap(sx, sy);
      const px = Math.min(Math.max(mx, 0), S.map.W) / SQ;
      const pz = Math.min(Math.max(mz, 0), S.map.H) / SQ;
      brSnapStroke(px, pz);
    } else if (typeof readout === "function") {
      readout(e);                                  // hover: keep the elevation + passability tooltip live
    }
    draw();
  }
}, true);

const brEnd = (e) => {
  if (!BR.on || !BR.painting) return;
  e.stopImmediatePropagation();
  BR.painting = false;
  const s = BR.stroke;
  BR.stroke = null;
  if (s) {
    const len = Math.hypot(s.x1 - s.x0, s.z1 - s.z0);
    if (len < 0.5) brSendLine(s.x0, s.z0, s.x0, s.z0, true);   // click: a single dab
    else brSendLine(s.x0, s.z0, s.x1, s.z1, true);
  }
  draw();
};
cv.addEventListener("pointerup", brEnd, true);
cv.addEventListener("pointercancel", (e) => {
  if (!BR.painting) return;
  BR.painting = false;
  BR.stroke = null;
  draw();
}, true);
cv.addEventListener("pointerleave", () => { if (BR.on && !BR.painting) { BR.cur = null; draw(); } }, true);

// ------------------------------------------------------------------ mouse: pick the ramp endpoints
cv.addEventListener("pointerdown", (e) => {
  if (!RA.on || !S.map || e.button !== 0) return;
  const r = cv.getBoundingClientRect();
  const sx = e.clientX - r.left, sy = e.clientY - r.top;
  const [mx, mz] = toMap(sx, sy);
  if (mx < 0 || mz < 0 || mx > S.map.W || mz > S.map.H) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  if (!RA.a) {
    RA.a = [mx, mz];
    RA.cur = [sx, sy];
  } else {
    const [ax, az] = RA.a;
    RA.a = null;
    RA.cur = null;
    raSend(ax / SQ, az / SQ, mx / SQ, mz / SQ);
  }
  draw();
}, true);

cv.addEventListener("pointermove", (e) => {
  if (!RA.on || !S.map) return;
  const r = cv.getBoundingClientRect();
  RA.cur = [e.clientX - r.left, e.clientY - r.top];
  if (typeof readout === "function") readout(e);   // keep the tooltip live while aiming the ramp
  draw();
}, true);

cv.addEventListener("pointerleave", () => { if (RA.on) { RA.cur = null; draw(); } }, true);
cv.addEventListener("contextmenu", (e) => { if (BR.on || RA.on) e.preventDefault(); });

// ------------------------------------------------------------------ toolbar
$("brush-mode").onclick = () => brSetOn(!BR.on);
$("ramp-mode").onclick = () => raSetOn(!RA.on);
for (const b of document.querySelectorAll("#brush-extra [data-br-mode]")) b.onclick = () => { BR.mode = b.dataset.brMode; brUpdateUi(); draw(); };
for (const b of document.querySelectorAll("#brush-extra [data-br-shape]")) b.onclick = () => { BR.shape = b.dataset.brShape; brUpdateUi(); draw(); };
$("brush-radius").oninput = () => { BR.radius = parseInt($("brush-radius").value, 10) || 30; brUpdateUi(); draw(); };
$("brush-strength").oninput = () => { BR.strength = parseInt($("brush-strength").value, 10) || 5; brUpdateUi(); };
$("brush-limit").oninput = () => { const v = $("brush-limit").value; BR.limit = v === "" ? null : parseFloat(v); };
$("ramp-width").oninput = () => { RA.width = parseInt($("ramp-width").value, 10) || 24; brUpdateUi(); };
$("ramp-start").oninput = () => { RA.start = parseFloat($("ramp-start").value) || 0; };
$("ramp-end").oninput = () => { RA.end = parseFloat($("ramp-end").value) || 0; };
$("br-undo").onclick = brUndo;
$("br-redo").onclick = brRedo;

brUpdateUi();

