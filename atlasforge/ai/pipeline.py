"""AI custom map pipeline: DeepInfra prompt -> heightmap + diffuse texture -> .sdz.

This is the ``ai_custom`` mode of Atlas Map Forge. It turns a free-text prompt
into a complete, buildable map without a parametric template:

    from atlasforge.ai.pipeline import generate
    info = generate("AI Canyon", "a long narrow canyon with two fortresses", size=(16, 4))

The generated heightmap is flattened under the start points and metal spots (so
bases are buildable), then fed into ``forge.build`` together with the generated
texture as the map's diffuse layer (``build_archive(..., diffuse=...)``), which
skips the procedural texture renderer.
"""

import numpy as np

from .. import SQ
from ..biomes import BIOMES
from ..config import ForgeConfig
from ..design import Design
from ..procedural import place_resources
from ..symmetry import Symmetry
from ..templates.common import flatten_all
from .generator import DeepInfraGenerator


def design(prompt, size=(16, 4), seed=1, biome="temperate", log=print, model=None, gen=None):
    """Turn a prompt into a Design (AI heightmap + diffuse texture, symmetric resources)."""
    ux, uz = int(size[0]), int(size[1])
    if ux % 2 or uz % 2:
        raise ValueError(f"map size must be even, got {ux}x{uz} (e.g. use 16x4)")
    if not (4 <= ux <= 32 and 4 <= uz <= 32):
        raise ValueError("size: even values between 4 and 32")
    if biome not in BIOMES:
        raise ValueError(f"unknown biome {biome!r}, expected one of {sorted(BIOMES)}")

    gen = gen or DeepInfraGenerator(model=model, log=log)
    hm, tex = gen.generate_terrain(prompt, size=(ux, uz))

    nx, nz = ux * 64, uz * 64
    W, H = nx * SQ, nz * SQ
    sym = Symmetry("ew", W, H)
    starts = sym.starts()                                   # two bases on the short (west/east) edges
    rng = np.random.default_rng(seed)
    mexes, geos = place_resources(hm, sym, starts, min(ux, uz), rng, log)
    flatten_all(hm, starts, mexes, geos)                    # buildable bases and mexes
    hm = hm.astype(np.float32)

    desc = (f"{ux}x{uz} AI-generated {biome} map ({prompt.strip()[:120]}). 1v1 to teams; "
            "terrain comes from a text prompt, not a symmetric template.")
    return Design(hm=hm, sym=sym, starts=starts, teams=[[starts[0]], [starts[1]]], mexes=mexes, geos=geos,
                  biome=BIOMES[biome], title="AI Map", description=desc, diffuse=tex, template="ai_custom",
                  seed=seed, values=dict(prompt=prompt, size=[ux, uz], biome=biome))


def generate(title, prompt, size=(16, 4), seed=1, biome="temperate", outdir=".", config=None, version=1,
             log=print, preview=True, model=None):
    """Build <outdir>/'Forge <title> v<version>'.sdz from a prompt. Returns the info dict."""
    from .. import forge
    cfg = config or ForgeConfig()
    name = cfg.map_name(title, version)
    log(f"[{name}] {size[0]}x{size[1]} ai_custom/{biome} seed={seed}")
    log(f"  prompt: {prompt.strip()}")
    d = design(prompt, size=size, seed=seed, biome=biome, log=log, model=model)
    d.title = title
    return forge.build(d, outdir=outdir, config=cfg, title=title, version=version, log=log, preview=preview)
