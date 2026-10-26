"""AI custom map pipeline: DeepInfra prompt -> playable heightmap + diffuse texture -> .sdz.

This is the ``ai_custom`` mode of Atlas Map Forge. It turns a free-text prompt
into a complete, buildable map without a parametric template:

    from atlasforge.ai.pipeline import generate
    info = generate("AI Canyon", "a long narrow canyon with two fortresses", size=(16, 4))

The generated heightmap is denoised and selectively slope-clamped
(``ai.postprocess``) so SDXL artifacts (pixel spikes, near-vertical
micro-cliffs) are removed while real terrain (fortresses, cliffs, 30-75 deg
slopes) is preserved.  Bases are raised above the water line and metal spots
are placed on flat, dry ground.  The result is fed into
``forge.build`` together with the generated texture as the map's diffuse layer
(``build_archive(..., diffuse=...)``), which skips the procedural renderer.

Surface types (``surface_type``) control the mapinfo.lua water table:

* ``none``  - no water plane (``voidwater = true``, water level below terrain).
* ``water`` - a real blue water plane at ``waterlevel`` (default 0).
* ``lava``  - a deadly (``water.damage = 100``) orange "water" plane.
* ``void``  - a bottomless abyss plus a gadget that kills units that fall in.
"""

import os
from pathlib import Path

import numpy as np
from PIL import Image

from .. import SQ
from ..biomes import BIOMES
from ..config import ForgeConfig
from ..design import Design
from ..procedural import place_resources
from ..symmetry import Symmetry
from ..templates.common import flatten_all
from ..terrain import flatten_disc
from .generator import DeepInfraGenerator, TEXTURE_NEGATIVE, TEXTURE_POSITIVE, _log_prompt
from .postprocess import denoise, mirror_quadrant, selective_slope_clamp

SURFACES = ("none", "water", "lava", "void")

# Phase 3.5 preview export folder: grayscale heightmaps before/after the
# denoise + selective slope-clamp pass, for human visual review.
PREVIEW_DIR = Path(os.environ.get("AI_PREVIEW_DIR", "") or (Path.home() / "Documents" / "_ai_previews"))

# Minimal synced gadget for "void" maps: destroys units that fall below the
# void floor (the map has no water plane, so a unit can otherwise fall forever).
VOID_GADGET = """-- void_death.lua: kills units that fall below the void floor (bottomless abyss maps).
if (not gadgetHandler:IsSyncedCode()) then
    return
end

local VOID_Y = -60.0   -- elmos below sea level; anything lower is destroyed
local CHECK_EVERY = 15 -- frames between sweeps

function gadget:GetInfo()
    return {
        name      = "Void Death",
        desc      = "Destroys units that fall below the void floor.",
        author    = "Atlas Map Forge",
        date      = "2026",
        license   = "GPL v2+",
        layer     = 0,
        enabled   = true,
    }
end

function gadget:GameFrame(n)
    if n % CHECK_EVERY ~= 0 then
        return
    end
    for _, unitID in ipairs(Spring.GetAllUnits()) do
        local _, y = Spring.GetUnitPosition(unitID)
        if y and y < VOID_Y then
            Spring.DestroyUnit(unitID, false, true)
        end
    end
end
"""


def _heightmap_png(hm, path, lo, hi):
    """Write ``hm`` (float32 elmos) as an 8-bit grayscale PNG using [lo, hi]."""
    hm = np.asarray(hm, dtype=np.float32)
    span = max(float(hi) - float(lo), 1e-6)
    norm = np.clip((hm - float(lo)) / span, 0.0, 1.0)
    arr = (norm * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(arr, mode="L").save(path, "PNG")


def _save_heightmap_pair(hm_before, hm_after, ux, uz, seed, prompt, log):
    """Save before/after Phase 3.5 heightmap previews into ``PREVIEW_DIR``.

    Both images share the 1-99 percentile range of the *raw* heightmap so the
    before/after pair is directly comparable.  A filesystem failure only emits
    a warning: previews are a diagnostic aid, never a build blocker.
    """
    lo = float(np.percentile(hm_before, 1))
    hi = float(np.percentile(hm_before, 99))
    tag = "".join(c if c.isalnum() else "_" for c in prompt.strip().lower())[:24].strip("_") or "map"
    stem = f"hm_{tag}_{ux}x{uz}_seed{seed}"
    try:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        before = PREVIEW_DIR / f"{stem}_before.png"
        after = PREVIEW_DIR / f"{stem}_after.png"
        _heightmap_png(hm_before, before, lo, hi)
        _heightmap_png(hm_after, after, lo, hi)
        log(f"  heightmap previews: {before}")
        log(f"                      {after}")
        return before, after
    except OSError as exc:
        log(f"  WARNING: could not write heightmap previews: {exc}")
        return None, None


def _surface(surface_type, waterlevel, biome):
    """Mapinfo.lua water override for a surface type."""
    if surface_type not in SURFACES:
        raise ValueError(f"unknown surface_type {surface_type!r}, expected one of {SURFACES}")
    if surface_type == "water":
        return dict(voidwater=False, waterlevel=float(waterlevel), damage=0.0,
                    base=biome["water_base"], min=biome["water_min"], surf=biome["water_surf"],
                    plane=biome["water_min"])
    if surface_type == "lava":
        return dict(voidwater=True, waterlevel=float(waterlevel), damage=100.0,
                    base=(0.45, 0.15, 0.05), min=(0.25, 0.06, 0.0), surf=(1.0, 0.45, 0.1),
                    plane=(0.9, 0.3, 0.05))
    # none / void: no water plane, water level far below the terrain
    return dict(voidwater=True, waterlevel=-1000.0, damage=0.0,
                base=biome["water_base"], min=biome["water_min"], surf=biome["water_surf"],
                plane=None)


def design(prompt, size=(16, 4), seed=1, biome="temperate", log=print, model=None, gen=None,
           surface_type="none", smooth=3, max_slope=30.0, waterlevel=0.0):
    """Turn a prompt into a Design (AI heightmap + diffuse texture, symmetric resources)."""
    ux, uz = int(size[0]), int(size[1])
    if ux % 2 or uz % 2:
        raise ValueError(f"map size must be even, got {ux}x{uz} (e.g. use 16x4)")
    if not (4 <= ux <= 32 and 4 <= uz <= 32):
        raise ValueError("size: even values between 4 and 32")
    if biome not in BIOMES:
        raise ValueError(f"unknown biome {biome!r}, expected one of {sorted(BIOMES)}")
    if surface_type not in SURFACES:
        raise ValueError(f"unknown surface_type {surface_type!r}, expected one of {SURFACES}")

    gen = gen or DeepInfraGenerator(model=model, log=log)
    hm, tex = gen.generate_terrain(prompt, size=(ux, uz))
    hm_raw = hm.astype(np.float32).copy()                   # before Phase 3.5
    min_before, max_before = float(np.min(hm_raw)), float(np.max(hm_raw))
    mean_before = float(np.mean(hm_raw))

    # Phase 3.5 terrain-quality pass: remove SDXL noise, preserve real terrain.
    std_before = float(np.std(hm))
    hm, pct_smooth = denoise(hm, roughness_threshold=8.0, sigma=1.5)
    hm, n_clamped = selective_slope_clamp(hm, cell_size=SQ, max_slope_deg=75.0)
    std_after = float(np.std(hm))
    min_after, max_after = float(np.min(hm)), float(np.max(hm))
    mean_after = float(np.mean(hm))
    log(f"  denoise: smoothed {pct_smooth:.1f}% of cells (3x3 std-dev > 8 elmo)")
    log(f"  slope clamp: {n_clamped} near-vertical (>75 deg) micro-cliff edges clamped")
    log(f"  heightmap std-dev {std_before:.1f} -> {std_after:.1f} elmo "
        f"(ratio {std_after / max(std_before, 1e-6):.3f})")
    _save_heightmap_pair(hm_raw, hm, ux, uz, seed, prompt, log)

    nx, nz = ux * 64, uz * 64
    W, H = nx * SQ, nz * SQ
    sym = Symmetry("ew", W, H)
    starts = sym.starts()                                   # two bases on the short (west/east) edges
    rng = np.random.default_rng(seed)

    wet = surface_type in ("water", "lava")
    target = max(45.0, float(waterlevel) + 35.0) if wet else 45.0
    for (x, z) in starts:                                   # raise bases above the water line first
        flatten_disc(hm, x, z, 330, 650, target=target)

    mexes, geos = place_resources(hm, sym, starts, min(ux, uz), rng, log,
                                  max_slope_deg=max_slope,
                                  waterlevel=float(waterlevel) if wet else None)
    flatten_all(hm, starts, mexes, geos)                    # buildable bases and mexes
    hm = hm.astype(np.float32)

    surface = _surface(surface_type, waterlevel, BIOMES[biome])
    extra_files = {}
    if surface_type == "void":
        extra_files["LuaRules/Gadgets/void_death.lua"] = VOID_GADGET

    desc = (f"{ux}x{uz} AI-generated {biome} map ({prompt.strip()[:120]}), surface={surface_type}. "
            "1v1 to teams; terrain comes from a text prompt, not a symmetric template.")
    return Design(hm=hm, sym=sym, starts=starts, teams=[[starts[0]], [starts[1]]], mexes=mexes, geos=geos,
                  biome=BIOMES[biome], title="AI Map", description=desc, diffuse=tex, template="ai_custom",
                  seed=seed, values=dict(prompt=prompt, size=[ux, uz], biome=biome,
                                         surface_type=surface_type, smooth=smooth, max_slope=max_slope,
                                         std_before=std_before, std_after=std_after,
                                         pct_smoothed=pct_smooth, n_clamped=n_clamped,
                                         min_before=min_before, max_before=max_before,
                                         min_after=min_after, max_after=max_after,
                                         mean_before=mean_before, mean_after=mean_after),
                  water=surface, extra_files=extra_files)


def generate(title, prompt, size=(16, 4), seed=1, biome="temperate", outdir=".", config=None, version=1,
             log=print, preview=True, model=None, surface_type="none", smooth=3, max_slope=30.0,
             waterlevel=0.0):
    """Build <outdir>/'Forge <title> v<version>'.sdz from a prompt. Returns the info dict."""
    from .. import forge
    cfg = config or ForgeConfig()
    name = cfg.map_name(title, version)
    log(f"[{name}] {size[0]}x{size[1]} ai_custom/{biome} surface={surface_type} seed={seed}")
    log(f"  prompt: {prompt.strip()}")
    d = design(prompt, size=size, seed=seed, biome=biome, log=log, model=model,
               surface_type=surface_type, smooth=smooth, max_slope=max_slope, waterlevel=waterlevel)
    d.title = title
    return forge.build(d, outdir=outdir, config=cfg, title=title, version=version, log=log, preview=preview)


# --------------------------------------------------------------------------- Phase 3.7: twin plateau
def _solid_texture(hm, biome, ux, uz):
    """Solid biome fallback texture, tinted by height so the minimap stays readable.

    Offline and deterministic; never calls the API.  The heightmap is already
    symmetric, so the texture inherits the same symmetry.
    """
    from scipy import ndimage
    nx, nz = ux * 64, uz * 64
    lo = np.asarray(biome["low"], np.float32) / 255.0
    hi = np.asarray(biome["high"], np.float32) / 255.0
    h = np.asarray(hm, np.float32)
    t = np.clip((h - h.min()) / (h.max() - h.min() + 1e-6), 0.0, 1.0)
    t = ndimage.gaussian_filter(t, sigma=6.0)
    rgb = lo[None, None, :] + t[..., None] * (hi - lo)[None, None, :]
    arr = (np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    return Image.fromarray(arr, "RGB").resize((nx * SQ, nz * SQ), Image.LANCZOS)


def design_plateau(prompt, size=(16, 4), seed=1, biome="temperate", log=print, model=None, gen=None,
                   surface_type="none", ai_texture=True, waterlevel=0.0):
    """Turn a procedural twin-plateau heightmap into a Design (AI or solid texture).

    The heightmap is built from the top-left quadrant and made exactly E-W and
    N-S symmetric via ``mirror_quadrant``.  Metal (7 per side) and geovents
    (4 per side) come from the symmetric plateau layout; start discs and
    resource discs are flattened for buildability.  The diffuse texture is an
    AI image (mirrored to match the terrain) or a solid biome fallback.
    """
    ux, uz = int(size[0]), int(size[1])
    if ux % 2 or uz % 2:
        raise ValueError(f"map size must be even, got {ux}x{uz} (e.g. use 16x4)")
    if not (4 <= ux <= 32 and 4 <= uz <= 32):
        raise ValueError("size: even values between 4 and 32")
    if biome not in BIOMES:
        raise ValueError(f"unknown biome {biome!r}, expected one of {sorted(BIOMES)}")
    if surface_type not in SURFACES:
        raise ValueError(f"unknown surface_type {surface_type!r}, expected one of {SURFACES}")

    from ..templates.custom_plateau import plateau_geos, plateau_heightmap, plateau_mexes

    hm = plateau_heightmap(ux, uz, seed, log)
    assert np.array_equal(hm, hm[:, ::-1]), "E-W symmetry broken"
    assert np.array_equal(hm, hm[::-1, :]), "N-S symmetry broken"
    log("  symmetry: exact E-W and N-S mirror (mirror_quadrant, top-left quadrant)")

    nx, nz = ux * 64, uz * 64
    W, H = nx * SQ, nz * SQ
    sym = Symmetry("ew", W, H)
    starts = sym.starts()
    for (x, z) in starts:                                # flat fortress floors
        flatten_disc(hm, x, z, 330, 650, target=260.0)

    mexes = plateau_mexes(sym)
    geos = plateau_geos(sym)
    log(f"  resources: {len(mexes)} metal spots, {len(geos)} geovents (E-W + N-S symmetric)")
    flatten_all(hm, starts, mexes, geos)
    hm = hm.astype(np.float32)

    gen = gen or DeepInfraGenerator(model=model, log=log)
    if ai_texture:
        tex_pos = TEXTURE_POSITIVE.format(prompt=prompt or f"{biome} satellite terrain")
        _log_prompt("texture", tex_pos, TEXTURE_NEGATIVE)
        log(f"  texture prompt: {tex_pos}")
        tex = gen.generate_image(tex_pos, 1024, 1024, negative=TEXTURE_NEGATIVE)
        tex = tex.convert("RGB").resize((nx * SQ, nz * SQ), Image.LANCZOS)
        arr, _ = mirror_quadrant(np.asarray(tex, dtype=np.uint8), "ew_ns")
        tex = Image.fromarray(arr, "RGB")
    else:
        tex = _solid_texture(hm, BIOMES[biome], ux, uz)
        log("  texture: solid biome fallback (--no-ai-texture)")

    surface = _surface(surface_type, waterlevel, BIOMES[biome])
    extra_files = {}
    if surface_type == "void":
        extra_files["LuaRules/Gadgets/void_death.lua"] = VOID_GADGET

    desc = (f"{ux}x{uz} twin-plateau {biome} map ({surface_type} surface). "
            "1v1 fortress map; terrain is exactly mirrored E-W and N-S.")
    return Design(hm=hm, sym=sym, starts=starts, teams=[[starts[0]], [starts[1]]], mexes=mexes,
                  geos=geos, biome=BIOMES[biome], title="AI Map", description=desc, diffuse=tex,
                  template="custom_plateau", seed=seed,
                  values=dict(prompt=prompt, size=[ux, uz], biome=biome, surface_type=surface_type,
                              ai_texture=ai_texture, min_height=float(hm.min()),
                              max_height=float(hm.max())),
                  water=surface, extra_files=extra_files)


def generate_plateau(title, prompt, size=(16, 4), seed=1, biome="temperate", outdir=".", config=None,
                     version=1, log=print, preview=True, model=None, surface_type="none",
                     ai_texture=True, waterlevel=0.0):
    """Build <outdir>/'Forge <title> v<version>'.sdz from the twin-plateau template."""
    from .. import forge
    cfg = config or ForgeConfig()
    name = cfg.map_name(title, version)
    log(f"[{name}] {size[0]}x{size[1]} custom_plateau/{biome} surface={surface_type} seed={seed} "
        f"ai_texture={ai_texture}")
    if prompt:
        log(f"  texture prompt: {prompt.strip()}")
    d = design_plateau(prompt, size=size, seed=seed, biome=biome, log=log, model=model,
                       surface_type=surface_type, ai_texture=ai_texture, waterlevel=waterlevel)
    d.title = title
    return forge.build(d, outdir=outdir, config=cfg, title=title, version=version, log=log,
                       preview=preview)
