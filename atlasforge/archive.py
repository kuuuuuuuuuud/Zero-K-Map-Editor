"""Heightmap + resources -> finished .sdz map archive (texture, SMF/SMT, minimap, mapinfo, configs)."""
import multiprocessing as mp
import os
import zipfile
import zlib

import numpy as np
from PIL import Image, ImageDraw

from . import SQ, TEX_PER_SQ, TILE
from . import __version__, watermark
from .badge import draw_badge
from .config import ForgeConfig, TOOL_NAME
from .formats import (dds_bytes, mapinfo_lua, metal_layout_lua, minimap_dxt, png_bytes, smt_header,
                      startboxes_lua, tiles_from_strip, write_smf)
from .features import grass_map, place_trees
from .render import (PAINT_LAYERS, NoiseBank, build_texture_fields, crack_field, detail_bmp, material_files,
                     render_rgb)

STRIP = 1024          # texture rows per worker job
_JOB = None           # per-process render job (set by _init_worker)


def _init_worker(job):
    global _JOB
    _JOB = job


def _render_strip(r0):
    TF, Wpx, biome, water_h, NB, decals, Hpx = _JOB
    r1 = min(Hpx, r0 + STRIP)
    parts, emis = [], []
    for a in range(r0, r1, 256):             # 256-row blocks keep peak memory around 450 MB
        e = np.zeros((min(r1, a + 256) - a, Wpx, 4), np.float32) if "paint" in TF else None
        parts.append(render_rgb(TF, a, min(r1, a + 256), Wpx, biome, water_h, NB, decals, e))
        if e is not None:                    # emission at 1/4 resolution (4 elmos per pixel), box filter
            n_, w_ = e.shape[0] // 4, Wpx // 4
            emis.append(e[:n_ * 4].reshape(n_, 4, w_, 4, 4).mean((1, 3)).astype(np.uint8))
    rgb = np.concatenate(parts, 0)
    return rgb, tiles_from_strip(rgb).tobytes(), (np.concatenate(emis, 0) if emis else None)


def _pool(n, job):
    """Worker pool that works on Linux (fork) and Windows/macOS (spawn: the job is sent once per worker)."""
    if n <= 1:
        return None
    method = os.environ.get("ATLASFORGE_MP") or ("fork" if "fork" in mp.get_all_start_methods() else "spawn")
    return mp.get_context(method).Pool(n, initializer=_init_worker, initargs=(job,))


def build_archive(name, hm, sym, starts, mexes, geos, biome, rng, outdir, desc, config=None, log=print,
                  preview=True, extra=None, tree_block=None, startboxes=None, extra_files=None, features=None,
                  random_trees=True, preview_marks=None, preview_start_colors=None, paint=None, workers=None, keep_clear=None):
    """Build <outdir>/<name>.sdz. Returns an info dict.
    config: ForgeConfig (author, badge); desc is used as given (call config.describe() before if wanted).
    paint: optional dict of 0..1 fields (heightmap resolution) for PAINT_LAYERS.
    extra_files: {archive path: str|bytes} e.g. map gadgets and their config.
    keep_clear: bool grid without random trees (e.g. carved ramps)."""
    cfg = config or ForgeConfig()
    nz, nx = hm.shape[0] - 1, hm.shape[1] - 1
    if not np.isfinite(hm).all():
        raise ValueError(f"heightmap contains {int((~np.isfinite(hm)).sum())} invalid values (NaN/inf)")
    if nx % 128 or nz % 128:
        raise ValueError("map size must be a multiple of 2 Spring units (128 heightmap squares)")
    ux, uz = nx // 64, nz // 64
    hmin = float(min(hm.min(), -1.0)) - 1
    hmax = float(hm.max()) + 1
    water_h = 0.0
    hm16 = np.clip(np.round((hm - hmin) / (hmax - hmin) * 65535), 0, 65535).astype(np.uint16)
    hm16 = watermark.embed(hm16, hmin, hmax, __version__, (extra or {}).get("template") or "procedural",
                           int((extra or {}).get("seed") or 0))                 # hidden Forge mark
    hmq = hm16.astype(np.float32) / 65535 * (hmax - hmin) + hmin          # continue with the quantised height

    trees = place_trees(hmq, sym, mexes, geos, starts, biome, rng, water_h, keep_clear) if random_trees else []
    if tree_block is not None:
        trees = [t for t in trees if not tree_block[min(nz, int(t[3] / SQ)), min(nx, int(t[1] / SQ))]]
    log(f"  {len(trees)} trees, {len(geos)} geovents")

    metal = np.zeros((nz // 2, nx // 2), np.uint8)                          # metal map (16 elmo cells)
    mi, mj = np.mgrid[0:nz // 2, 0:nx // 2]
    for m in mexes:
        metal[np.hypot(mi * 16 + 8 - m["z"], mj * 16 + 8 - m["x"]) < 40] = 255
    typemap = np.zeros((nz // 2, nx // 2), np.uint8)
    if biome.get("void"):                                                   # space: terrain type 255, impassable
        typemap[hmq[:-1:2, :-1:2][:nz // 2, :nx // 2] < 0] = 255

    Wpx, Hpx = nx * TEX_PER_SQ, nz * TEX_PER_SQ
    TF = build_texture_fields(hmq)
    has_lava = paint is not None and np.max(paint.get("lava", 0)) > 0
    if paint:
        z0 = np.zeros(hmq.shape, np.float32)
        TF["paint"] = np.dstack([np.clip(paint.get(k, z0), 0, 1).astype(np.float32) for k in PAINT_LAYERS])
        if has_lava:
            TF["crack"] = crack_field(hmq.shape[0], np.random.default_rng(zlib.crc32(name.encode()) & 0xFFFF))
    NB = NoiseBank(rng)
    decals = [(m["x"], m["z"], "mex") for m in mexes] + [(g[0], g[1], "geo") for g in geos]
    os.makedirs(outdir, exist_ok=True)
    fname = name.replace(" ", "_")
    smt_name = fname + ".smt"
    smt_path = os.path.join(outdir, smt_name + ".tmp")
    ntiles = (Wpx // TILE) * (Hpx // TILE)
    mini_rows, emis_rows = [], []
    job = (TF, Wpx, biome, water_h, NB, decals, Hpx)
    starts_ = list(range(0, Hpx, STRIP))
    nproc = min(len(starts_), os.cpu_count() or 1, workers or 4)
    pool = _pool(nproc, job)
    if pool is None:
        _init_worker(job)
    it = pool.imap(_render_strip, starts_) if pool else map(_render_strip, starts_)
    try:
        with open(smt_path, "wb") as f:
            f.write(smt_header(ntiles))
            for r0, (rgb, tiles, em) in zip(starts_, it):
                r1 = min(Hpx, r0 + STRIP)
                f.write(tiles)
                if em is not None:
                    emis_rows.append(em)
                if preview and r0 == (Hpx // 2 // STRIP) * STRIP:
                    Image.fromarray(rgb[:, Wpx // 2 - 512:Wpx // 2 + 512]).save(os.path.join(outdir, fname + "_detail.png"))
                mini_rows.append(np.asarray(Image.fromarray(rgb).resize((1024, max(1, (r1 - r0) * 1024 // Hpx)), Image.BOX)))
                log(f"  texture {r1}/{Hpx}")
    finally:
        if pool:
            pool.close(); pool.join()
    mini_clean = np.asarray(Image.fromarray(np.concatenate(mini_rows, 0)).resize((1024, 1024), Image.LANCZOS))
    badge = cfg.badge if cfg.badge != "none" else None
    mini_img = draw_badge(mini_clean, badge) if badge else mini_clean
    minimap = minimap_dxt(mini_img)
    assert len(minimap) == 699048

    feats = [("geovent", g[0], float(hmq[int(g[1] / SQ), int(g[0] / SQ)]), g[1], 0.0, 1.0) for g in geos]
    feats += [(f"treetype{t}", x, y, z, rot, 1.0) for (t, x, y, z, rot) in trees]
    for (fname_, fx, fz, frot) in (features or []):        # designed features (wrecks, hedge trees ...)
        fi, fj = min(nz, max(0, int(fz / SQ))), min(nx, max(0, int(fx / SQ)))
        feats.append((fname_, float(fx), float(hmq[fi, fj]), float(fz), float(frot), 1.0))
    smf_path = os.path.join(outdir, fname + ".smf.tmp")
    mapid = zlib.crc32(name.encode()) & 0x7FFFFFFF
    grass = grass_map(hmq, biome, rng, water_h, keep_clear, paint, mexes, geos)
    if grass is not None:
        log(f"  grass on {100 * (grass > 0).mean():.0f} % of the map")
    write_smf(smf_path, nx, nz, hmin, hmax, hm16, typemap, minimap, metal, smt_name, ntiles, feats, mapid,
              grass=grass)

    sdz = os.path.join(outdir, fname + ".sdz")
    with zipfile.ZipFile(sdz, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        emis_name = None
        if emis_rows and has_lava:
            emis_name = "light_emission.png"    # PNG: not flipped by the engine (unlike DDS)
            z.writestr("maps/" + emis_name, png_bytes(np.concatenate(emis_rows, 0)))
        sky_name = None
        if biome.get("skybox", True):
            from .sky import sky_jpg
            sky_name = "skybox.jpg"
            z.writestr("maps/" + sky_name, sky_jpg(biome, seed=mapid & 0xFFFF))
        shading_name = None
        if grass is not None:
            # grass blades = bladeColor x this texture x lighting: the ground colours around 1.0 keep the
            # blade colour but follow the ground's local variation
            gs = mini_clean.astype(np.float32)
            gs = np.clip(gs / (gs.reshape(-1, 3).mean(0) + 1e-3) * 0.92, 0, 1.25) / 1.25 * 255
            shading_name = "grass_shading.png"
            z.writestr("maps/" + shading_name, png_bytes(np.asarray(Image.fromarray(gs.astype(np.uint8)).resize((512, 512), Image.BOX))))
        z.writestr("mapinfo.lua", mapinfo_lua(name, desc, cfg.author, hmin, hmax, smt_name, starts, biome, water_h,
                                              fname + ".smf", minimap_tex="minimap_ingame.dds" if badge else None,
                                              emission_tex=emis_name, tool=TOOL_NAME, sky_box=sky_name,
                                              grass_shading=shading_name))
        if badge:
            # DDS is loaded vertically flipped (OpenGL convention), the SMF minimap is not: write upside down
            z.writestr("maps/minimap_ingame.dds", dds_bytes(np.ascontiguousarray(mini_clean[::-1]), "DXT1"))
        z.write(smf_path, f"maps/{fname}.smf")
        z.write(smt_path, f"maps/{smt_name}", compresslevel=1)
        z.writestr("maps/detailtex.bmp", detail_bmp(rng))
        for fn_, data_ in material_files(hmq, TF, biome, mexes, geos, rng, log).items():
            z.writestr("maps/" + fn_, data_)
        for fn_, data_ in (extra_files or {}).items():
            z.writestr(fn_, data_)
        z.writestr("mapconfig/map_metal_layout.lua", metal_layout_lua(mexes))
        z.writestr("mapconfig/map_startboxes.lua", startboxes or startboxes_lua(sym, starts))
    os.remove(smf_path); os.remove(smt_path)

    info = dict(name=name, file=os.path.basename(sdz), path=os.path.abspath(sdz), size=[ux, uz], **(extra or {}),
                mexes=len(mexes), geos=len(geos), trees=len(trees), hmin=round(hmin, 1), hmax=round(hmax, 1),
                bytes=os.path.getsize(sdz))
    if preview:
        info["preview"] = os.path.abspath(os.path.join(outdir, fname + "_preview.png"))
        make_preview(mini_img, mexes, geos, starts, sym, info["preview"], marks=preview_marks,
                     start_colors=preview_start_colors)
    log(f"  -> {sdz} ({info['bytes'] / 1e6:.1f} MB)")
    return info


def make_preview(mini, mexes, geos, starts, sym, path, marks=None, start_colors=None, size=768):
    """Minimap with mexes (blue), geovents (orange) and start points.
    marks: extra markers [(x, z, text, (r, g, b))]; start_colors: colour per start point
    (default: first half green = team 0, second half red = team 1)."""
    img = Image.fromarray(mini).resize((size, int(size * sym.H / sym.W)))
    d = ImageDraw.Draw(img)
    sx, sz = img.width / sym.W, img.height / sym.H
    for m in mexes:
        x, z = m["x"] * sx, m["z"] * sz
        r = 3 + m["metal"]
        d.ellipse([x - r, z - r, x + r, z + r], outline=(255, 255, 255), fill=(40, 200, 255))
    for g in geos:
        x, z = g[0] * sx, g[1] * sz
        d.rectangle([x - 5, z - 5, x + 5, z + 5], outline=(0, 0, 0), fill=(255, 120, 0))
    for k, (x, z) in enumerate(starts):
        x, z = x * sx, z * sz
        c = start_colors[k] if start_colors else ((60, 255, 60) if k < len(starts) // 2 else (255, 60, 60))
        d.ellipse([x - 9, z - 9, x + 9, z + 9], outline=(0, 0, 0), width=3, fill=c)
        if start_colors:
            d.text((x, z), str(k + 1), fill=(0, 0, 0), anchor="mm")
    for (x, z, label, c) in (marks or []):
        x, z = x * sx, z * sz
        d.regular_polygon((x, z, 14), 6, fill=c, outline=(0, 0, 0))
        d.text((x, z), label, fill=(0, 0, 0), anchor="mm")
    img.save(path)
