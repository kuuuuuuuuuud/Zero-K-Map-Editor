"""Shared helpers for templates: base terrain, flattening, D4 symmetry, start box files, common params."""
import math

import numpy as np

from .. import SQ
from ..biomes import BIOMES
from ..noise import fbm, ridged, smoothstep
from ..symmetry import seam_blend
from ..terrain import flatten_disc, grid
from .base import Param

BIOME_CHOICES = tuple(sorted(BIOMES))
H_LOW = 100.0


def size_param(choices, default, adv_smallest=4):
    """adv_smallest: smallest size the template can still build in advanced mode."""
    return Param("size", "Map size", "choice", default, choices=tuple(choices),
                 adv_choices=tuple(range(adv_smallest, 33, 2)), group="Map",
                 help="Width and height in Spring map units (8 = small 1v1, 16 = 2v2, 20 = large team game)",
                 info="Width and height of the map in Spring map units; one unit is 512 elmos (a small tank is "
                      "about 30 elmos long). 8x8 suits a fast 1v1, 12-16 a 2v2 or 3v3, 20 and more large team games. "
                      "Bigger maps take longer to build, need more metal spots to stay interesting and make "
                      "travel times (and raids) longer.")


def general_params():
    """Settings every template has (applied by forge.make after the template)."""
    return (
        Param("mex_count", "Metal spots", "int", 0, min=0, max=40, step=1, adv_max=120, group="Resources",
              help="Metal spots per side (per player in free-for-all); 0 = what the template picks for this size",
              info="How many metal spots each side gets (each player on free-for-all maps, each quarter on "
                   "four-way maps, the whole map on co-op maps), base spots included. 0 keeps the template's own number, which grows with "
                   "the map size. More spots mean a faster economy and more places to fight over; fewer "
                   "spots make every expansion count. Spots are added and removed in mirrored sets so "
                   "every side stays equal; spots inside the bases are never removed, and new ones only go "
                   "on flat ground your builders can reach."),
        Param("metal", "Metal per spot", "float", 1.0, min=0.5, max=2.0, step=0.1, adv_min=0.1, adv_max=5.0,
              group="Resources", help="Multiplies the value of every metal spot",
              info="Multiplies the metal income of every spot. 1.0 is the template's normal value (a normal "
                   "spot gives about 2 metal per second with a mex on it). 0.5 halves the economy, so games "
                   "are slower and smaller; 2.0 doubles it, so big units and superweapons come much earlier."),
        Param("geos", "Geothermal vents", "choice", "default", choices=("default", 0, 1, 2, 3),
              adv_choices=("default", 0, 1, 2, 3, 4, 5, 6, 8), group="Resources",
              help="Geothermal vents per side (per player in free-for-all); default = what the template picks",
              info="Geothermal vents per side. A geothermal plant on a vent gives a lot of energy (25 E/s, "
                   "the advanced one 100 E/s) but explodes hard when destroyed. 'default' keeps the "
                   "template's vents; 0 removes them all. New vents are placed in mirrored sets on flat, "
                   "reachable ground, preferably out in the field where they are worth fighting over."),
        Param("wind", "Wind", "choice", "biome", choices=("biome", "calm", "low", "medium", "high", "storm"),
              group="Resources", help="Wind strength for wind generators; biome = the biome's usual wind",
              info="Wind speed range of the map, which sets how much energy wind generators make (they "
                   "make between the minimum and maximum, changing over time). calm 0-5, low 2-12, medium "
                   "5-20, high 10-28, storm 18-35. 'biome' uses the biome's own range (e.g. moon has "
                   "almost no wind). Higher wind makes cheap wind generators the best energy source; low "
                   "wind pushes players to solar panels and geothermal plants."),
        Param("tidal", "Tidal strength", "int", 12, min=0, max=25, step=1, adv_max=50, group="Resources",
              help="Energy of tidal generators in water",
              info="Energy per second that a tidal generator in water makes. Only matters on maps with "
                   "water deep enough to build tidals. 12 is the usual Zero-K value; 0 makes tidals useless, "
                   "20 and more makes the sea the best place for energy."),
        Param("sun", "Time of day", "choice", "biome", choices=("biome", "morning", "noon", "afternoon", "evening"),
              group="Map", help="Where the sun stands: light direction, shadows and sun colour",
              info="Sets the sun for the whole map: the direction light and shadows come from in game, the "
                   "shading baked into the ground texture and the sun in the sky. morning: low sun in the "
                   "east, warm light. noon: high sun, short shadows, the clearest view. afternoon: sun in "
                   "the south-west. evening: very low sun in the west, long shadows and orange light. "
                   "'biome' uses the biome's usual sun (high, from the north-west). Purely visual, no "
                   "effect on the game."),
        Param("sky", "Sky", "choice", "painted", choices=("painted", "engine"), group="Map",
              help="painted: the map's own sky picture; engine: Zero-K's default sky",
              info="painted: the map carries its own sky picture made for the biome - colours, clouds, the "
                   "sun at the right place, stars on the moon - and the horizon matches the fog, so the "
                   "edge of the map fades into the sky. engine: no sky picture, Zero-K draws its plain "
                   "default sky in the biome's colours (a little smaller map file). Purely visual."),
        Param("grass", "Grass", "float", 0.0, min=0.0, max=2.0, step=0.1, adv_max=4.0, group="Terrain",
              help="Engine grass on flat ground (biomes with grass only)",
              info="Grass blades drawn by the engine on gentle ground: patches of meadow in temperate, "
                   "autumn and jungle maps, reeds in swamps, sparse tufts in deserts and the arctic. Grass is "
                   "only decoration: it does not block units, shots or sight. 0 removes it, 2.0 doubles the "
                   "covered area. Players can turn grass off in their graphics settings; biomes without "
                   "grass (moon, volcanic, ashland, industrial) stay bare."),
        Param("trees", "Trees", "float", 0.4, min=0.0, max=2.0, step=0.1, adv_max=5.0, group="Terrain",
              help="Tree density (biomes without trees stay bare)",
              info="Density of trees on grass and forest ground. Trees block line of sight a little, can be "
                   "reclaimed for energy and burn when hit. 0 removes them, 2.0 gives dense forests. "
                   "Biomes without trees (desert, moon, alien) stay bare. Many trees cost frame rate on "
                   "large maps."),
        Param("rocks", "Rocks", "float", 0.0, min=0.0, max=2.0, step=0.1, adv_max=6.0, group="Terrain",
              help="Rock clusters with reclaimable metal (glowing crystals on alien and moon maps)",
              info="Clusters of rocks (glowing crystals on alien and moon maps) that hold metal. Constructors "
                   "can reclaim them for a quick metal boost early in the game. They are placed in mirrored "
                   "sets away from bases, metal spots and chokes, so every side gets the same amount; the "
                   "check report shows the total reclaim metal. 0 = none."),
        Param("wrecks", "Wrecks", "float", 0.0, min=0.0, max=2.0, step=0.1, adv_max=6.0, group="Terrain",
              help="Battlefield wrecks of Zero-K units between the bases (reclaimable metal)",
              info="Wrecks of Zero-K units from an old battle, mostly between the bases. Each wreck holds "
                   "about 40 % of the unit's cost in metal, so they reward early scouting and reclaim. "
                   "Large wrecks also block paths a little and give cover. Placed in mirrored sets; 0 = none."),
        Param("erosion", "Erosion", "float", 0.6, min=0.0, max=1.5, step=0.1, adv_max=4.0, group="Terrain",
              help="Rain-carved gullies and valleys on natural slopes; bases, metal spots, chokes and walls "
                   "stay as designed",
              info="Simulates rain running down the slopes for a natural look: gullies, small valleys and "
                   "soft deposits at the foot of hills. Bases, metal spots, chokes, ramps and walls are "
                   "protected. If erosion would cut off a route, it is lowered automatically (the check "
                   "report says so). 0 gives the clean designed shapes, 1.5 a strongly weathered look."),
    )


def biome_param(default):
    return Param("biome", "Biome", "choice", default, choices=BIOME_CHOICES, group="Map",
                 help="Colours, sky, light and trees",
                 info="The look of the map: ground colours and textures, sky, sun, water colour, trees, grass "
                      "and the usual wind. It does not change the shape of the terrain. jungle: dense forest "
                      "and tall grass; swamp: murky water, mud puddles and reeds; industrial: steel plates and "
                      "concrete, no trees. Desert, moon, alien, volcanic and ashland have no trees, and the "
                      "moon has almost no wind.")


def sym_fields(mode, *fields):
    """Noise fields made symmetric with a seamless blend (see symmetry.seam_blend)."""
    out = tuple(seam_blend(f, mode).astype(np.float32) for f in fields)
    return out if len(out) > 1 else out[0]


def base_terrain(n, rng, calm_r, center_x, sym=None):
    """Gentle ground at about H_LOW with hills further than calm_r from the vertical centre line.
    sym: symmetry of the map ("ew", "ns", "point", "d4") - the noise is made symmetric before anything is
    built on it, so the final mirror copy has no seam.
    Returns h, xx, zz, low (normalised fbm), en (edge noise -1..1)."""
    xx, zz = grid(n)
    low = fbm((n, n), rng, base=5, octaves=6); low = (low - low.mean()) / (low.std() + 1e-6)
    hills = ridged((n, n), rng, base=6) ** 2.6
    en = fbm((n, n), rng, base=22, octaves=3); en /= np.abs(en).max() + 1e-6
    if sym:
        low, hills, en = sym_fields(sym, low, hills, en)
    calm = smoothstep(calm_r, calm_r + 900, np.abs(xx - center_x))
    h = (H_LOW + 14 * low + 70 * hills * calm).astype(np.float32)
    return h, xx, zz, low, en


def flatten_all(hm, starts, mexes, geos, start_r=(330, 650)):
    for p in starts:
        flatten_disc(hm, p[0], p[1], start_r[0], start_r[1])
    for m in mexes:
        flatten_disc(hm, m["x"], m["z"], 45, 100)
    for g in geos:
        flatten_disc(hm, g[0], g[1], 55, 110)


# ----------------------------------------------------------------------------- D4 (four bases)
def d4(h):
    """Copy the NW quadrant exactly to NE, SW, SE (square grid, odd size)."""
    n = h.shape[0]
    half = n // 2
    h[:, half + 1:] = h[:, :half][:, ::-1][:, : n - half - 1]
    h[half + 1:, :] = h[:half, :][::-1, :][: n - half - 1, :]
    return h


def d4_points(pts, W):
    """(x, z, ...) in the NW quadrant -> all mirror images, duplicates on the axes removed."""
    out, seen = [], set()
    for p in pts:
        x, z, rest = p[0], p[1], tuple(p[2:])
        for mx in (x, W - x):
            for mz in (z, W - z):
                key = (round(mx), round(mz))
                if key in seen:
                    continue
                seen.add(key)
                out.append((mx, mz) + rest)
    return out


def corners(p, W):
    """NW start point -> (NW, NE, SW, SE)"""
    x, z = p
    return [(x, z), (W - x, z), (x, W - z), (W - x, W - z)]


def _q(p, half, W):
    return "{ {%d, %d}, {%d, %d}, {%d, %d}, {%d, %d} }" % (
        max(0, p[0] - half), max(0, p[1] - half), min(W, p[0] + half), max(0, p[1] - half),
        min(W, p[0] + half), min(W, p[1] + half), max(0, p[0] - half), min(W, p[1] + half))


def _sp(ps):
    return ", ".join("{%d, %d}" % (round(x), round(z)) for x, z in ps)


def four_base_boxes(team0, team1, names0, names1, W, half=900):
    """2 teams with two bases each, or one base per team when 3-4 teams play (FFA).
    team0/team1: two start points each; names: (long, short) per base."""
    a, b = team0
    c, d = team1
    return f"""-- Atlas Map Forge: 2 teams -> two bases each; 3-4 teams -> one base per team (FFA)
if GetTeamCount and GetTeamCount() <= 2 then
\treturn {{
\t\t[0] = {{ nameLong = "{names0[0]}", nameShort = "{names0[1]}", startpoints = {{ {_sp([a, b])} }}, boxes = {{ {_q(a, half, W)}, {_q(b, half, W)} }} }},
\t\t[1] = {{ nameLong = "{names1[0]}", nameShort = "{names1[1]}", startpoints = {{ {_sp([c, d])} }}, boxes = {{ {_q(c, half, W)}, {_q(d, half, W)} }} }},
\t}}
end
return {{
\t[0] = {{ nameLong = "Base 1", nameShort = "1", startpoints = {{ {_sp([a])} }}, boxes = {{ {_q(a, half, W)} }} }},
\t[1] = {{ nameLong = "Base 2", nameShort = "2", startpoints = {{ {_sp([c])} }}, boxes = {{ {_q(c, half, W)} }} }},
\t[2] = {{ nameLong = "Base 3", nameShort = "3", startpoints = {{ {_sp([b])} }}, boxes = {{ {_q(b, half, W)} }} }},
\t[3] = {{ nameLong = "Base 4", nameShort = "4", startpoints = {{ {_sp([d])} }}, boxes = {{ {_q(d, half, W)} }} }},
}}
"""


def coop_boxes(player_box, enemy_box, players):
    """Co-op (chicken) maps: players in one box, the chicken side in another."""
    f = lambda pts: ", ".join("{%d, %d}" % (round(x), round(z)) for x, z in pts)
    q = lambda b: "{ {%d, %d}, {%d, %d}, {%d, %d}, {%d, %d} }" % (b[0], b[1], b[2], b[1], b[2], b[3], b[0], b[3])
    cx, cz = (enemy_box[0] + enemy_box[2]) / 2, (enemy_box[1] + enemy_box[3]) / 2
    return f"""return {{
\t[0] = {{ nameLong = "Players", nameShort = "P", startpoints = {{ {f(players)} }}, boxes = {{ {q(player_box)} }} }},
\t[1] = {{ nameLong = "Chickens", nameShort = "C", startpoints = {{ {{{cx:.0f}, {cz:.0f}}} }}, boxes = {{ {q(enemy_box)} }} }},
}}
"""


def polar(c, r, ang_deg):
    a = math.radians(ang_deg)
    return c + r * math.cos(a), c + r * math.sin(a)


def disc_mask(xx, zz, x, z, r):
    return np.hypot(xx - x, zz - z) < r


def cell(p):
    return int(p[1] / SQ), int(p[0] / SQ)


def ffa_boxes(sym, starts, r_in, r_out, half_deg=None):
    """Free-for-all start boxes: one wedge-shaped box around each player's start (RotSymmetry).
    r_in/r_out: radii of the box (elmos from the centre); half_deg: half opening angle (default 40 % of a
    sector). Player k is ally team k."""
    half = half_deg if half_deg is not None else 0.4 * 180.0 / sym.n
    W, H = sym.W, sym.H
    out = ["-- Atlas Map Forge: free-for-all, one start box per player", "return {"]
    for k, (sx, sz) in enumerate(starts):
        pts = []
        for r, a0, a1 in ((r_out, -half, half), (r_in, half, -half)):
            for t in np.linspace(a0, a1, 5):
                x, z = sym.polar(r, t, k)
                pts.append((min(W, max(0, x)), min(H, max(0, z))))
        poly = ", ".join("{%d, %d}" % (round(x), round(z)) for x, z in pts)
        out.append(f'\t[{k}] = {{ nameLong = "Base {k + 1}", nameShort = "{k + 1}", '
                   f'startpoints = {{ {{{sx:.0f}, {sz:.0f}}} }}, boxes = {{ {{ {poly} }} }} }},')
    out.append("}")
    return "\n".join(out) + "\n"
