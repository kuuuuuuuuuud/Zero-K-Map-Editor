"""Private procedural-template pipeline, reusing Skirmish's resources and tank ramp carver."""
import numpy as np
from scipy import ndimage

from ..biomes import BIOMES
from ..design import Design
from ..noise import fbm, norm01
from ..procedural import LAYOUTS, _Carver, place_resources
from ..symmetry import Symmetry
from ..terrain import flatten_disc
from .base import Param
from .common import biome_param, size_param, sym_fields


def described(p, text):
    """Works with the current dataclass and the core's announced future Param.info field."""
    p.info = text
    return p


def common_params(biome):
    return (
        described(size_param((8, 10, 12, 14, 16, 18, 20), 12, adv_smallest=8),
                  "Sets the square map width in Spring map units, each equal to 512 elmos. Larger maps provide more expansion space and longer travel distances. For example, size 12 is a compact match while size 20 gives teams more room."),
        described(biome_param(biome),
                  "Changes terrain colours, vegetation, lighting and the sky. The terrain family and seed still determine the geography. For example, Arctic gives the same landforms a cold appearance."),
        described(Param("layout", "Teams face", "choice", "diag", choices=LAYOUTS,
                        help="Choose diagonal, north-south or east-west symmetric opponents"),
                  "Sets the opposing base orientation and the corresponding terrain symmetry. Both sides receive mirrored resources and equal starting terrain. For example, diag places opponents in the northwest and southeast."),
        described(Param("relief", "Relief", "float", 1.0, min=0.5, max=1.6, step=0.1,
                        adv_min=0.1, adv_max=3.0, help="Scales the elevation differences"),
                  "Multiplies the elevation differences, with 1.0 as the standard height scale. Higher terrain creates stronger high-ground positions and can require additional tank ramps. For example, 0.5 halves the relief without selecting a different seed."),
        described(Param("warp", "Terrain distortion", "float", 1.0, min=0.3, max=1.5, step=0.1,
                        adv_min=0.0, adv_max=3.0, help="Bends the generated landforms with large-scale noise"),
                  "Scales the displacement of the underlying terrain pattern. Higher values bend ridges, basins and region boundaries into more irregular shapes. For example, zero leaves an orderly underlying pattern while 1.0 uses normal distortion."),
    )


def fields(v, rng):
    n = v["size"] * 64 + 1
    zz, xx = np.mgrid[:n, :n].astype(np.float32) / (n - 1)
    mode = {"diag": "point", "ns": "ns", "ew": "ew"}[v["layout"]]
    macro, wx, wz, detail = sym_fields(mode,
        fbm((n, n), rng, base=v["size"] / 5 + 1, octaves=4),
        fbm((n, n), rng, base=3.2, octaves=3),
        fbm((n, n), rng, base=3.7, octaves=3),
        fbm((n, n), rng, base=v["size"] * 1.8, octaves=3))
    return xx, zz, xx + wx * 0.15 * v["warp"], zz + wz * 0.15 * v["warp"], norm01(macro), detail


def build(template, v, seed, terrain, log):
    rng = np.random.default_rng(seed)
    W = v["size"] * 512
    sym = Symmetry(v["layout"], W, W)
    h = terrain(v, rng, fields(v, rng)).astype(np.float32)
    h = sym.symmetrize(h, band=0.06 * W).astype(np.float32)
    h = ((h + sym.mirror_grid(h)) * 0.5).astype(np.float32)
    starts = sym.starts()
    target = max(55.0, float(h[int(starts[0][1] / 8), int(starts[0][0] / 8)]))
    for x, z in starts:
        flatten_disc(h, x, z, 330, 650, target=target)
    mexes, geos = place_resources(h, sym, starts, v["size"], rng, log)
    # The procedural resource helper emits each starting spot followed by its mirror.
    for m in mexes[:6]:
        m["fixed"] = True
    for m in mexes:
        flatten_disc(h, m["x"], m["z"], 45, 100)
    for x, z in geos:
        flatten_disc(h, x, z, 55, 110)
    carver = _Carver(h, water_ok=False)
    bad = carver.ensure(h, sym, starts, mexes, log)
    fixed_bad = [i for i in bad if mexes[i].get("fixed", False)]
    drop = {j for i in bad if not mexes[i].get("fixed", False) for j in (i, i + 1)}
    mexes = [m for i, m in enumerate(mexes) if i not in drop]
    for m in mexes:
        flatten_disc(h, m["x"], m["z"], 45, 100)
    h = ndimage.gaussian_filter((h + sym.mirror_grid(h)) * 0.5, 0.6).astype(np.float32)
    h = ((h + sym.mirror_grid(h)) * 0.5).astype(np.float32)
    clear = carver.mask | sym.mirror_grid(carver.mask)
    return Design(hm=h, sym=sym, starts=starts, teams=[[starts[0]], [starts[1]]],
                  mexes=mexes, geos=geos, biome=dict(BIOMES[v["biome"]]),
                  title=template.title, description=template.description,
                  keep_clear=clear, tree_block=clear,
                  notes=[f"Procedural terrain family: {template.id}; form: {v['form']}",
                         f"Unreachable expansion pairs removed after ramp carving: {len(drop) // 2}",
                         f"Protected opening spots: {sum(m.get('fixed', False) for m in mexes)}"],
                  notes_ok=not fixed_bad, rng_state=rng.bit_generator.state)
