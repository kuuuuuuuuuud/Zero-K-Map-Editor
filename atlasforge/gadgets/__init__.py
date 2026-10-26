"""Optional map gadgets. Zero-K loads Lua gadgets from the map archive (LuaRules/gadgets.lua lists
LuaRules/Gadgets/ with VFS.ZIP_ONLY, which includes the map), so a map can ship its own game rules.

  lava cliffs   Raised ground that no movement class except spiders can reach (wall tops, massifs) gets a
                lava texture with glow and slowly damages ground units standing on it.
  lava tides    ZK's own lava (map_lava.lua, configured by mapconfig/lava_config.lua) rises and falls on
                a schedule; the tide warning gadget shows a countdown and marks the fords that flood.
  eruption      A volcano that erupts with the lava tide: crater effects, lava bombs with ground warnings.

All texts shown in game are English.
"""
import os

import numpy as np
from scipy import ndimage

from .. import SQ
from ..checks import unit_masks

HERE = os.path.dirname(os.path.abspath(__file__))
CELL = 32          # grid size of the damage area in elmos


def _lua(name):
    with open(os.path.join(HERE, name), encoding="utf8") as f:
        return f.read()


# ----------------------------------------------------------------------------- lava cliffs
def reach_union(hm, seeds):
    """Union of the areas reachable from the start points by every ground class except spiders."""
    reach = np.zeros(hm.shape, bool)
    for nm, m in unit_masks(hm).items():
        if nm == "spiders":
            continue
        lab, _ = ndimage.label(m)
        ids = {int(lab[int(z / SQ), int(x / SQ)]) for x, z in seeds} - {0}
        if ids:
            reach |= np.isin(lab, list(ids))
    return reach


def lava_cliff_mask(hm, seeds, min_rise=40.0, exclude=None):
    """Unreachable areas that lie higher than the reachable ground around them (cliffs, walls, massifs).
    Depressions (gorges, lakes) are left alone."""
    reach = reach_union(hm, seeds)
    un = ~reach & (hm > 1.0)
    if exclude is not None:
        un &= ~exclude
    lab, n = ndimage.label(un)
    out = np.zeros(hm.shape, bool)
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        sl = tuple(slice(max(0, s.start - 4), s.stop + 4) for s in sl)
        c = lab[sl] == k
        if c.sum() < 20:
            continue
        border = ndimage.binary_dilation(c, iterations=3) & reach[sl]
        if border.sum() == 0:
            continue
        if hm[sl][c].mean() - hm[sl][border].mean() > min_rise:
            out[sl] |= c
    return out


def paint_field(mask, sigma=1.2):
    """Bool mask -> soft 0..1 paint layer."""
    return np.clip(ndimage.gaussian_filter(mask.astype(np.float32), sigma) * 1.6 - 0.3, 0, 1)


def _rle_rows(cells):
    rows = []
    for r in cells:
        runs, cur, cnt = [], False, 0
        for v in r:
            if bool(v) == cur:
                cnt += 1
            else:
                runs.append(cnt); cur = not cur; cnt = 1
        runs.append(cnt)
        rows.append(",".join(map(str, runs)))
    return rows


def lava_cliff_files(mask, min_dps=15, pct_dps=0.025):
    """Gadget + data file. A 32-elmo cell counts when more than 60 % of it is lava cliff, so the foot of a
    wall is not included and units standing next to it take no damage.
    Damage per second: max(min_dps, pct_dps * max HP). Returns (files, number of damage cells)."""
    k = CELL // SQ
    nz, nx = (mask.shape[0] - 1) // k, (mask.shape[1] - 1) // k
    m = mask[:nz * k, :nx * k].reshape(nz, k, nx, k).mean((1, 3)) > 0.6
    if not m.any():
        return {}, 0
    body = ",\n".join(f'\t\t"{r}"' for r in _rle_rows(m))
    data = f"""-- Atlas Map Forge: lava cliffs (unreachable high ground).
-- rows: per row (z), run lengths alternating free/lava, starting with free. Cell = {CELL} elmos.
return {{
\tcell = {CELL},
\tnx = {nx},
\tnz = {nz},
\tminDps = {min_dps},
\tpctDps = {pct_dps},
\trows = {{
{body}
\t}},
}}
"""
    return {"mapconfig/atlas_lava_cliffs.lua": data,
            "LuaRules/Gadgets/atlas_lava_cliffs.lua": _lua("lua_lava_cliffs.lua")}, int(m.sum())


# ----------------------------------------------------------------------------- lava tides
def lava_config(high, calm_s=150, high_s=45, rise_speed=0.1, fall_speed=0.1, damage=120, title="lava tides"):
    """mapconfig/lava_config.lua for ZK's map_lava.lua: base level 1 (water surface), cycle
    calm -> rise to `high` -> hold -> fall. Entry order makes the game start calm (map_lava jumps to
    entry 2 at frame 0)."""
    return f"""-- Atlas Map Forge: {title}. ZK lava (LuaRules/Gadgets/map_lava.lua reads mapconfig/lava_config.lua).
-- {calm_s} s calm -> lava rises to {high} -> {high_s} s -> falls -> calm.
local conf = {{
\tlevel = 1,
\tdamage = {damage},
\tuVscale = 2.0,
\tcolorCorrection = {{1.1, 1.0, 0.88}},
\tplaneLightMult = 2,
\tcoastColor = {{2.2, 0.4, 0.0}},
\tcoastLightBoost = 0.7,
\tcoastWidth = 30.0,
\tfogColor = {{2.0, 0.31, 0.0}},
\tfogFactor = 0.07,
\tfogHeight = 20,
\tfogAbove = 0.18,
\ttideamplitude = 2,
\ttideperiod = 120,
\ttideRhym = {{
\t\t{{ target = {high}, speed = {rise_speed}, period = {high_s} }},
\t\t{{ target = 1, speed = {fall_speed}, period = {calm_s} }},
\t}},
}}
return conf
"""


def tide_files(fords, flood_level, warn_s=20):
    """Tide warning gadget. fords: [(x1, z1, x2, z2), ...] axis-aligned rectangles that flood."""
    fl = ",\n".join(f"\t\t{{ {x1:.0f}, {z1:.0f}, {x2:.0f}, {z2:.0f} }}" for x1, z1, x2, z2 in fords)
    data = f"""-- Atlas Map Forge: tide warning (reads the tides from mapconfig/lava_config.lua).
return {{
\tfloodLevel = {flood_level},
\twarnSeconds = {warn_s},
\tfords = {{
{fl}
\t}},
}}
"""
    return {"mapconfig/atlas_tide.lua": data, "LuaRules/Gadgets/atlas_tide_warning.lua": _lua("lua_tide_warning.lua")}


# ----------------------------------------------------------------------------- volcano
def eruption_files(center, crater_r, island_r, summit_h, flood, quads, bomb_every_s=1.1, bomb_radius=170,
                   bomb_damage=900, ring_share=0.18, ring_r=(3250, 3700), warn_s=20,
                   island_targets=None, ring_targets=None, target_spacing=0):
    """Eruption gadget. quads: causeway areas that flood, each 4 corner points [(x, z) x 4].
    island_targets / ring_targets: bomb spots on solid ground [(x, z)], island spots sorted by distance to
    the crater. Without them bombs fall anywhere in the island and ring radius."""

    def pts(name, lst):
        if not lst:
            return ""
        rows = [", ".join("{%d, %d}" % (x, z) for x, z in lst[i:i + 8]) for i in range(0, len(lst), 8)]
        return f"\t{name} = {{\n" + "".join(f"\t\t{r},\n" for r in rows) + "\t},\n"
    targets = pts("islandTargets", island_targets) + pts("ringTargets", ring_targets)
    q = ",\n".join("\t\t{ " + ", ".join(f"{{ {x:.0f}, {z:.0f} }}" for x, z in quad) + " }" for quad in quads)
    data = f"""-- Atlas Map Forge: volcano eruption settings (read by LuaRules/Gadgets/atlas_eruption.lua).
return {{
\tcenter = {{ {center[0]:.0f}, {center[1]:.0f} }},
\tcraterRadius = {crater_r:.0f},
\tislandRadius = {island_r:.0f},
\tsummitHeight = {summit_h:.0f},
\tfloodLevel = {flood},
\twarnSeconds = {warn_s},
\tbombEverySeconds = {bomb_every_s},
\tbombRadius = {bomb_radius},
\tbombDamage = {bomb_damage},
\tbombWarnFrames = 120,
\tringShare = {ring_share},
\tringRadius = {{ {ring_r[0]:.0f}, {ring_r[1]:.0f} }},
\ttargetSpacing = {target_spacing:.0f},
{targets}\tcauseways = {{
{q}
\t}},
}}
"""
    return {"mapconfig/atlas_eruption.lua": data, "LuaRules/Gadgets/atlas_eruption.lua": _lua("lua_eruption.lua")}


# ----------------------------------------------------------------------------- chicken defense
def chicken_zone_files(hm, protect, spacing=320):
    """Keep chicken roosts out of the player area. protect: list of dict(x, z, r) or dict(x0, z0, x1, z1).
    Candidate roost spots = flat land outside the protected areas."""
    from ..terrain import slope_deg
    W = (hm.shape[1] - 1) * SQ
    H = (hm.shape[0] - 1) * SQ
    sl = slope_deg(hm)

    def prot(x, z):
        for p in protect:
            if "r" in p and (x - p["x"]) ** 2 + (z - p["z"]) ** 2 < p["r"] ** 2:
                return True
            if "x0" in p and p["x0"] <= x <= p["x1"] and p["z0"] <= z <= p["z1"]:
                return True
        return False
    cands = []
    for z in np.arange(200, H - 200, spacing):
        for x in np.arange(200, W - 200, spacing):
            i, j = int(z / SQ), int(x / SQ)
            win = sl[max(0, i - 6):i + 7, max(0, j - 6):j + 7]
            if hm[i, j] > 5 and win.max() < 12 and not prot(x, z):
                cands.append((int(x), int(z)))

    def lua_p(p):
        if "r" in p:
            return "{x = %d, z = %d, r = %d}" % (p["x"], p["z"], p["r"])
        return "{x0 = %d, z0 = %d, x1 = %d, z1 = %d}" % (p["x0"], p["z0"], p["x1"], p["z1"])
    cfg = "-- Atlas Map Forge: chicken roost zones\nreturn {\n\tprotect = { " + ", ".join(lua_p(p) for p in protect)
    cfg += " },\n\tcandidates = {\n" + "".join("\t\t{%d, %d},\n" % c for c in cands) + "\t},\n}\n"
    return {"mapconfig/chicken_zones.lua": cfg, "LuaRules/Gadgets/map_chicken_zones.lua": _lua("lua_chicken_zones.lua")}
