"""Forge Editor new-project factory: a blank flat sand map.

A new editor project starts as a flat heightmap (``FLAT_ELMOS`` everywhere) with a
solid sand texture (``SAND_RGB``, hex ``#C2B280``). The texture is generated
programmatically - no DeepInfra call - and injected as ``Design.diffuse`` so the
build pipeline writes it into the SMT tiles and the minimap (``build_archive``
skips the procedural renderer when ``diffuse`` is set).
"""
import numpy as np
from PIL import Image

from . import SQ, TEX_PER_SQ
from .biomes import BIOMES
from .design import Design
from .surfaces import surface_extra_files, surface_key, surface_water
from .symmetry import Symmetry

SAND_RGB = (194, 178, 128)      # hex #C2B280
FLAT_ELMOS = 50.0


def _validate_dims(width, height):
    """Even Spring map units between 4 and 32, else a clear ValueError."""
    width, height = int(width), int(height)
    for key, v in (("width", width), ("height", height)):
        if v % 2:
            raise ValueError(f"{key}: must be even, got {v}")
        if not (4 <= v <= 32):
            raise ValueError(f"{key}: even values between 4 and 32, got {v}")
    return width, height


def flat_sand_design(width, height, seed=1, title="New Map", biome="desert", surface="none", log=print):
    """-> Design: flat 50-elmo terrain with a solid sand diffuse texture.

    ``surface`` selects the self-contained map surface (``none``, ``water``, ``lava``
    or ``void``) that is written into ``mapinfo.lua``; ``void`` also packs the
    ``LuaRules/Gadgets/void_death.lua`` gadget into the archive.
    """
    width, height = _validate_dims(width, height)
    nx, nz = width * 64, height * 64
    W, H = nx * SQ, nz * SQ

    hm = np.full((nz + 1, nx + 1), FLAT_ELMOS, dtype=np.float32)
    assert hm.shape == (height * 64 + 1, width * 64 + 1), hm.shape  # e.g. 16x4 -> (257, 1025)

    # Diffuse texture is (Hpx, Wpx, 3) = (nz * TEX_PER_SQ, nx * TEX_PER_SQ, 3).
    tex = np.empty((nz * TEX_PER_SQ, nx * TEX_PER_SQ, 3), dtype=np.uint8)
    tex[:] = SAND_RGB
    diffuse = Image.fromarray(tex, "RGB")

    b = dict(BIOMES[biome])
    sym = Symmetry("ew", W, H)
    starts = sym.starts()
    teams = [[starts[0]], [starts[1]]]
    surf = surface_key(surface)
    water = surface_water(surf)
    extra_files = surface_extra_files(surf)

    log(f"  new project: {width}x{height} flat sand (all cells {FLAT_ELMOS:g} elmo), surface={surf}")
    return Design(hm=hm, sym=sym, starts=starts, teams=teams, mexes=[], geos=[],
                  biome=b, title=title,
                  description=f"{width}x{height} flat sand editor map ({surf} surface).",
                  diffuse=diffuse, water=water, extra_files=extra_files,
                  template="editor", seed=seed,
                  values=dict(width=width, height=height, biome=biome, surface=surf))
