"""Local web server behind the Atlas Map Forge app.

Serves the user interface (atlasforge/app/web) and a small JSON API on 127.0.0.1. Every API call needs
the session token that is written into the page, so other web pages cannot use the API.

  GET  /api/state                       version, settings, Zero-K folders, templates
  POST /api/preview  {template, values, seed}  -> design id, check report, overlay data
  GET  /api/layer/<id>/<name>?size=N    relief (JPEG), hazard, gates, reach_<class> (PNG), cells, height (raw)
  GET  /api/versions?title=...          map versions that already exist
  POST /api/edit     {id, edits, symmetry}  -> moved/added/deleted spots, check report, problems
  POST /api/build    {id, title, version, install}  -> job id
  GET  /api/job/<job>                   progress, log, result
  POST /api/config   {author, zerok, outdir, projdir, advanced}
  POST /api/project_save {data}        write a project to the project folder -> {path, folder}
  POST /api/project_load {text} or {path}  read a project from text or from a .forge.json file
  POST /api/verify   {path}             does a map file carry the Forge watermark?
  POST /api/open     {path}             show a built map in the file manager
  POST /api/link     {to}               open a known web page (Ko-fi) in the default browser
"""
import io
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
from PIL import Image
from scipy import ndimage

from .. import SQ, __version__
from .. import config as C
from .. import project

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".otf": "font/otf", ".ico": "image/x-icon"}
CLASSES = ("tanks", "bots", "spiders", "amphibians", "hovers")
KEEP_DESIGNS = 6


def _png(rgba):
    b = io.BytesIO()
    Image.fromarray(rgba).save(b, "PNG", compress_level=1)
    return b.getvalue()


def _json_safe(o):
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


class Entry:
    def __init__(self, design, ok, lines):
        self.base = design                                    # as generated; edits are applied to a copy
        self.design, self.ok, self.lines = design, ok, lines
        self.base_ok, self.base_lines = ok, lines
        self.edits, self.symmetry, self.problems, self.issues = [], True, [], []
        self.layers = {}
        self.lock = threading.Lock()


class Job:
    def __init__(self):
        self.id = uuid.uuid4().hex[:12]
        self.state = "running"
        self.progress = 0.0
        self.phase = "Starting"
        self.log = []
        self.result = None
        self.error = None
        self.started = time.time()

    def to_dict(self):
        return dict(id=self.id, state=self.state, progress=round(self.progress, 3), phase=self.phase,
                    log=self.log[-200:], result=self.result, error=self.error,
                    seconds=round(time.time() - self.started, 1))


class Forge:
    """App state: recent designs, build jobs, settings."""

    def __init__(self):
        self.designs = OrderedDict()
        self.jobs = {}
        self.make_lock = threading.Lock()
        self.build_lock = threading.Lock()
        self.token = secrets.token_urlsafe(18)

    # ------------------------------------------------------------------ settings
    def settings(self):
        from ..install import find_zerok
        cfg = C.load()
        found = find_zerok()
        return dict(config=dict(cfg.__dict__, prefix=C.PREFIX), zerok_found=found, zerok=cfg.zerok or (found[0] if found else ""),
                    outdir=cfg.outdir or C.default_outdir(), default_outdir=C.default_outdir(),
                    projdir=cfg.projdir or C.default_projdir(), default_projdir=C.default_projdir())

    def set_config(self, data):
        cfg = C.load()
        for k in ("author", "zerok", "outdir", "projdir"):
            if k in data and data[k] is not None:
                setattr(cfg, k, str(data[k]).strip())
        if "advanced" in data:
            cfg.advanced = bool(data["advanced"])
        if cfg.zerok and not os.path.isdir(cfg.zerok):
            raise ValueError(f"Zero-K folder not found: {cfg.zerok}")
        C.save(cfg)
        return self.settings()

    def state(self):
        from ..biomes import BIOMES
        from ..templates import all_templates
        swatches = {k: [list(b[c]) for c in ("low", "mid", "high", "rock")] for k, b in BIOMES.items()}
        return dict(version=__version__, settings=self.settings(), support_url=C.SUPPORT_URL, templates=[t.info() for t in all_templates()],
                    classes=list(CLASSES), biomes=swatches)

    # ------------------------------------------------------------------ preview
    def preview(self, data):
        from .. import forge
        tid = data["template"]
        seed = int(data.get("seed", 1))
        log = []
        t0 = time.time()
        with self.make_lock:
            d = forge.make(tid, data.get("values") or {}, seed=seed, log=log.append, advanced=C.load().advanced)
            ok, lines = forge.check(d)
        did = uuid.uuid4().hex[:12]
        print(f"preview {tid} seed {seed}: {time.time() - t0:.1f} s", flush=True)
        e = Entry(d, ok, lines)
        self.designs[did] = e
        while len(self.designs) > KEEP_DESIGNS:
            self.designs.popitem(last=False)
        out = self._design_payload(did, e, seed, time.time() - t0)
        if data.get("edits"):                                 # opened from a project file: apply its edits
            out.update(self.edit(dict(id=did, edits=data["edits"], symmetry=data.get("symmetry", True))))
        return out

    def _design_payload(self, did, e, seed, seconds):
        from ..biomes import BIOMES
        from ..formats import startboxes_lua
        from .luatable import startboxes
        d, ok, lines, tid = e.design, e.ok, e.lines, e.design.template
        W, H = (d.hm.shape[1] - 1) * SQ, (d.hm.shape[0] - 1) * SQ
        try:
            boxes = startboxes(d.startboxes or startboxes_lua(d.sym, d.starts))
        except Exception:                                     # drawing boxes is a nicety, never fatal
            boxes = []
        gates = []
        for name, gm in d.gates or []:
            zz, xx = np.nonzero(gm)
            if len(xx):
                gates.append(dict(name=name, x=float(xx.mean() * SQ), z=float(zz.mean() * SQ)))
        team_cols = d.start_colors or None
        return _json_safe(dict(
            sym=dict(kind="rot" if hasattr(d.sym, "ops") else "mirror", layout=d.sym.layout, n=getattr(d.sym, "n", 2)),
            edits=e.edits, symmetry=e.symmetry, problems=e.problems, issues=e.issues,
            id=did, ok=ok, lines=lines, seconds=round(seconds, 2),
            template=tid, values=d.values, seed=seed, title=d.title, description=d.description,
            size=list(d.size), W=W, H=H, grid=[int(d.hm.shape[1]), int(d.hm.shape[0])],
            biome=str(d.values.get("biome") or next((k for k, b in BIOMES.items() if all(d.biome.get(x) == y for x, y in b.items())), "")),
            mexes=[dict(x=m["x"], z=m["z"], metal=m["metal"]) for m in d.mexes],
            geos=[[g[0], g[1]] for g in d.geos], teams=d.teams, starts=d.starts, start_colors=team_cols,
            side_labels=list(d.side_labels), boxes=boxes, gates=gates,
            marks=[dict(x=x, z=z, text=t, color=list(c)) for (x, z, t, c) in d.marks],
            has_hazard=bool(d.hazard is not None and d.hazard.any())
            or bool(d.event_zone is not None and d.event_zone.any()),
            event_label=d.event_label,
            movement_profile=d.movement_profile,
            has_blocked=bool(d.blocked is not None and d.blocked.any()),
            height=[float(d.hm.min()), float(d.hm.max())],
            metal_total=round(float(sum(m["metal"] for m in d.mexes)), 1),
            features=[[round(x), round(z), "crystal" if n.startswith("forge_crystal") else
                       "rock" if n.startswith("forge_rock") else "wreck"] for (n, x, z, _r) in d.features],
        ))


    def edit(self, data):
        """Apply a list of manual edits (metal spots, geovents, start points) to the generated design."""
        from .. import forge
        from ..edits import apply_edits, editor_checks
        e = self.entry(data["id"])
        edits = data.get("edits") or []
        if not isinstance(edits, list):
            raise ValueError("edits must be a list")
        sym_on = bool(data.get("symmetry", True))
        t0 = time.time()
        with e.lock:
            d, problems = apply_edits(e.base, edits, sym_on)
            if edits:
                with self.make_lock:
                    ok, lines = forge.check(d)
                issues = editor_checks(d, sym_on)
                ok = ok and not any(i["level"] == "error" for i in issues)
                lines = lines + [("ERROR: " if i["level"] == "error" else "WARNING: ") + i["text"] for i in issues]
            else:
                issues, ok, lines = [], e.base_ok, e.base_lines
            e.design, e.edits, e.symmetry, e.problems, e.issues = d, list(edits), sym_on, problems, issues
            e.ok, e.lines = ok, lines
            for key in [k for k in e.layers if k[0].startswith("reach_")]:
                del e.layers[key]
        out = self._design_payload(data["id"], e, d.seed, time.time() - t0)
        for k in ("values", "title", "description", "biome", "size", "W", "H", "grid", "height", "features",
                  "marks", "gates", "side_labels"):
            out.pop(k, None)                                   # unchanged by edits: keep the reply small
        return out

    # ------------------------------------------------------------------ project files (.forge.json)
    def project_dump(self, data):
        return dict(text=project.dumps(self._project_from(data["data"])))

    def project_save(self, data):
        """Write the project to the project folder as <title>.forge.json (an existing file of that name is replaced)."""
        base = self._project_from(data["data"])
        name = re.sub(r"[^A-Za-z0-9 ._()-]", "_", str(base.get("title") or "")).strip() or "map"
        cfg = C.load()
        folder = cfg.projdir or C.default_projdir()
        path = os.path.abspath(os.path.join(folder, name + ".forge.json"))
        try:
            os.makedirs(folder, exist_ok=True)
            project.save(path, base)
        except OSError as ex:
            raise ValueError(f"Cannot write the project file: {ex.strerror or ex}") from None
        return dict(path=path, folder=os.path.abspath(folder))

    def _project_from(self, data):
        d = dict(data)
        d.pop("format", None)
        d.pop("version", None)
        base = project.new_project(d.pop("template"), d.pop("values", {}), d.pop("seed", 1), d.pop("symmetry", True),
                                   d.pop("edits", []), d.pop("title", None), d.pop("app_version", __version__))
        base.update(d)                                         # unknown fields of a loaded file are kept
        project.validate(base, templates=self._template_ids())
        return base

    def project_load(self, data):
        if data.get("path"):
            p = os.path.abspath(str(data["path"]))
            if not p.endswith((".forge.json", ".json")):
                raise ValueError("Projects are .forge.json files")
            if not os.path.isfile(p) or os.path.getsize(p) > 5 * 1024 * 1024:
                raise ValueError("Project file not found or larger than 5 MB")
            with open(p, encoding="utf8") as f:
                text = f.read()
        else:
            text = str(data.get("text", ""))
        p = project.loads(text)
        project.validate(p, templates=self._template_ids())
        known = ("format", "version", "app_version", "template", "values", "seed", "symmetry", "edits", "title")
        return dict(project=p, extra={k: v for k, v in p.items() if k not in known})

    @staticmethod
    def _template_ids():
        from ..templates import all_templates
        return {t.info()["id"] for t in all_templates()}

    def entry(self, did):
        e = self.designs.get(did)
        if e is None:
            raise KeyError("This preview has expired, please preview again.")
        return e

    def layer(self, did, name, size=1024):
        e = self.entry(did)
        key = (name, size)
        with e.lock:
            if key not in e.layers:
                e.layers[key] = self._make_layer(e, name, size)
            return e.layers[key]

    def _make_layer(self, e, name, size):
        from .. import forge
        from ..checks import unit_masks
        d = e.design
        n = d.hm.shape
        if name == "relief":
            size = int(min(max(size, 256), 4096))
            b = io.BytesIO()
            forge.preview(d, size=size, overlays=False).convert("RGB").save(b, "JPEG", quality=90)
            return "image/jpeg", b.getvalue()
        if name == "height":                                   # int16 elmos, row-major (z, x)
            return "application/octet-stream", np.clip(np.round(d.hm), -32768, 32767).astype("<i2").tobytes()
        if name == "cells":                                    # bit k: class k can stand here (lava excluded)
            masks = unit_masks(d.hm)
            bits = np.zeros(n, np.uint8)
            for k, cls in enumerate(CLASSES):
                m = masks[cls] if d.blocked is None else masks[cls] & ~d.blocked
                bits |= (m.astype(np.uint8) << k)
            if d.blocked is not None:
                bits |= (d.blocked.astype(np.uint8) << 6)
            if d.hazard is not None:
                bits |= (d.hazard.astype(np.uint8) << 7)
            if d.event_zone is not None:
                bits |= (d.event_zone.astype(np.uint8) << 5)
            return "application/octet-stream", bits.tobytes()
        rgba = np.zeros(n + (4,), np.uint8)
        if name == "hazard":
            if d.event_zone is not None:                     # timed events (lava bombs): amber
                ez = d.event_zone
                edge = ez & ~ndimage.binary_erosion(ez, iterations=2)
                rgba[ez] = (255, 176, 40, 34)
                rgba[edge] = (255, 186, 60, 190)
            if d.hazard is not None:
                edge = d.hazard & ~ndimage.binary_erosion(d.hazard, iterations=2)
                rgba[d.hazard] = (255, 70, 30, 70)
                rgba[edge] = (255, 90, 40, 230)
            return "image/png", _png(rgba)
        if name == "gates":
            for _, gm in d.gates or []:
                edge = gm & ~ndimage.binary_erosion(gm, iterations=2)
                rgba[gm] = (255, 214, 64, 22)
                rgba[edge] = (255, 214, 64, 150)
            return "image/png", _png(rgba)
        if name.startswith("reach_"):
            cls = name[6:]
            if cls not in CLASSES + ("ships",):
                raise KeyError(name)
            m = unit_masks(d.hm)[cls]
            if d.blocked is not None:
                m = m & ~d.blocked
            lab, _ = ndimage.label(m)
            reach = np.zeros(n, bool)
            seeds = d.naval_starts if cls == "ships" and d.naval_starts else d.teams
            for team in seeds:
                for p in team:
                    lz, lx = min(int(p[1] / SQ), n[0] - 1), min(int(p[0] / SQ), n[1] - 1)
                    if lab[lz, lx]:
                        reach |= lab == lab[lz, lx]
            rgba[~reach] = (8, 10, 16, 175)                     # where this class can't go: dark
            edge = reach & ~ndimage.binary_erosion(reach, iterations=1)
            rgba[edge] = (120, 230, 255, 200)
            return "image/png", _png(rgba)
        raise KeyError(f"unknown layer {name}")

    # ------------------------------------------------------------------ versions
    def versions(self, title):
        from ..install import existing_versions
        cfg = C.load()
        s = self.settings()
        folders = [s["outdir"]] + ([os.path.join(s["zerok"], "maps")] if s["zerok"] else [])
        have = existing_versions(cfg, title, folders)
        return dict(existing=have, suggested=(max(have) + 1) if have else 1,
                    name_preview=cfg.map_name(title, (max(have) + 1) if have else 1))

    # ------------------------------------------------------------------ build
    def build(self, data):
        if not self.build_lock.acquire(blocking=False):
            raise RuntimeError("A map is already being built. Please wait until it is finished.")
        try:
            C.load().require_author()
            e = self.entry(data["id"])
            title = (data.get("title") or e.design.title).strip()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 '\-.()]{0,47}", title):
                raise ValueError("Map title: 1-48 letters, digits, spaces and ' - . ( ) only.")
            version = int(data.get("version") or 1)
            if not 1 <= version <= 999:
                raise ValueError("Version must be between 1 and 999.")
        except Exception:
            self.build_lock.release()
            raise
        job = Job()
        self.jobs[job.id] = job
        threading.Thread(target=self._run_build, args=(job, e, title, version, bool(data.get("install", True))),
                         daemon=True).start()
        return job.to_dict()

    def _run_build(self, job, e, title, version, do_install):
        from .. import forge
        from ..install import install

        def log(*a):
            line = " ".join(str(x) for x in a).strip()
            job.log.append(line)
            m = re.search(r"texture (\d+)/(\d+)", line)
            if m:
                job.progress = 0.10 + 0.65 * int(m.group(1)) / int(m.group(2))
                job.phase = "Painting the texture"
            elif "trees" in line:
                job.progress, job.phase = 0.08, "Painting the texture"
            elif line.startswith("materials"):
                job.progress, job.phase = 0.80, "Detail materials"
            elif line.startswith("->"):
                job.progress, job.phase = 0.95, "Packing the map"
        try:
            s = self.settings()
            cfg = C.load()
            outdir = s["outdir"]
            os.makedirs(outdir, exist_ok=True)
            job.phase = "Placing trees"
            info = forge.build(e.design, outdir=outdir, config=cfg, title=title, version=version, log=log)
            info["installed"] = None
            info["warning"] = None
            if do_install:
                if not s["zerok"]:
                    info["warning"] = ("Not installed: the Zero-K folder was not found. Set it in Settings, "
                                       "the map is in your output folder.")
                else:
                    job.phase = "Installing into Zero-K"
                    info["installed"] = install(info["path"], s["zerok"], log=log)
            job.result = _json_safe(info)
            job.progress, job.phase, job.state = 1.0, "Done", "done"
        except Exception as ex:                                  # report, never crash the app
            job.error = str(ex)
            job.log.append(traceback.format_exc(limit=3))
            job.state, job.phase = "error", "Failed"
        finally:
            self.build_lock.release()

    # ------------------------------------------------------------------ watermark
    def verify(self, data):
        from .. import watermark
        p = str(data.get("path") or "").strip().strip('"')
        if not p or not os.path.isfile(p):
            raise ValueError("File not found: " + p)
        r = watermark.verify(p)
        r["text"] = watermark.describe(r)
        return _json_safe(r)

    # ------------------------------------------------------------------ links
    def open_link(self, data):
        import webbrowser
        links = {"kofi": C.SUPPORT_URL, "github": "https://github.com/Scuide/atlas-map-forge"}
        url = links.get(str(data.get("to")))
        if not url:
            raise ValueError("unknown link")
        webbrowser.open(url)
        return dict(ok=True, url=url)

    # ------------------------------------------------------------------ file manager
    def open_path(self, path):
        s = self.settings()
        allowed = [os.path.abspath(s["outdir"]), os.path.abspath(s["projdir"])] +             ([os.path.abspath(s["zerok"])] if s["zerok"] else [])
        p = os.path.abspath(path)
        if not any(p == a or p.startswith(a + os.sep) for a in allowed):
            raise PermissionError("Only the output, project and Zero-K folders can be opened.")
        if sys.platform.startswith("win"):
            if os.path.isfile(p):
                subprocess.Popen(["explorer", "/select,", p])
            else:
                os.startfile(p)                                  # noqa: S606 (Windows only)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R" if os.path.isfile(p) else "", p])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(p) if os.path.isfile(p) else p])
        return dict(ok=True)


def make_handler(forge_state, quiet=True):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AtlasMapForge/" + __version__

        def log_message(self, fmt, *args):
            if not quiet:
                super().log_message(fmt, *args)

        def _send(self, code, body, ctype="application/json", cache=False):
            if not isinstance(body, (bytes, bytearray)):
                body = json.dumps(body).encode("utf8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorised(self, q):
            tok = self.headers.get("X-Forge-Token") or (q.get("t") or [""])[0]
            return secrets.compare_digest(tok, forge_state.token)

        def _static(self, path):
            if path in ("", "/"):
                path = "/index.html"
            full = os.path.abspath(os.path.join(WEB, path.lstrip("/")))
            if not full.startswith(os.path.abspath(WEB) + os.sep) or not os.path.isfile(full):
                return self._send(404, {"error": "not found"})
            with open(full, "rb") as f:
                body = f.read()
            if path == "/index.html":
                body = body.replace(b"__FORGE_TOKEN__", forge_state.token.encode())
            ext = os.path.splitext(full)[1].lower()
            self._send(200, body, MIME.get(ext, "application/octet-stream"), cache=ext in (".otf", ".jpg"))

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if not u.path.startswith("/api/"):
                return self._static(u.path)
            if not self._authorised(q):
                return self._send(403, {"error": "forbidden"})
            try:
                parts = u.path.split("/")[2:]
                if parts == ["state"]:
                    return self._send(200, forge_state.state())
                if parts[0] == "layer" and len(parts) == 3:
                    ctype, body = forge_state.layer(parts[1], parts[2], int((q.get("size") or ["1024"])[0]))
                    return self._send(200, body, ctype, cache=True)
                if parts == ["versions"]:
                    return self._send(200, forge_state.versions((q.get("title") or [""])[0]))
                if parts[0] == "job" and len(parts) == 2:
                    job = forge_state.jobs.get(parts[1])
                    return self._send(200, job.to_dict()) if job else self._send(404, {"error": "unknown job"})
                return self._send(404, {"error": "unknown endpoint"})
            except KeyError as ex:
                return self._send(404, {"error": str(ex).strip("'\"")})
            except Exception as ex:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(ex).__name__}: {ex}"})

        def do_POST(self):
            u = urlparse(self.path)
            if not self._authorised(parse_qs(u.query)):
                return self._send(403, {"error": "forbidden"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                route = u.path[len("/api/"):]
                fn = {"preview": forge_state.preview, "edit": forge_state.edit, "project_dump": forge_state.project_dump,
                      "project_load": forge_state.project_load,
                      "project_save": forge_state.project_save, "build": forge_state.build,
                      "clientlog": lambda d: (print("page:", str(d.get("msg", ""))[:500], flush=True), {"ok": True})[1],
                      "config": forge_state.set_config, "verify": forge_state.verify,
                      "open": lambda d: forge_state.open_path(d["path"]),
                      "link": forge_state.open_link}.get(route)
                if fn is None:
                    return self._send(404, {"error": "unknown endpoint"})
                return self._send(200, fn(data))
            except (ValueError, KeyError, PermissionError, RuntimeError) as ex:
                return self._send(400, {"error": str(ex).strip("'\"")})
            except Exception as ex:
                traceback.print_exc()
                return self._send(500, {"error": f"{type(ex).__name__}: {ex}"})

    return Handler


def serve(port=0, quiet=True):
    """Start the server in a background thread. Returns (server, url_with_token, Forge state)."""
    os.environ.setdefault("ATLASFORGE_MP", "spawn")    # builds run from a server thread: fork is unsafe there
    state = Forge()
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state, quiet))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/", state
