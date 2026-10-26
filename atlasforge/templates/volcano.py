"""Volcano (Ember Atoll): a volcano island in a sea of lava, ringed by an island chain with four bases.
The volcano erupts on a schedule: lava bombs rain down (ground warnings) and the rising lava floods every
causeway, cutting the map into pieces for a while. 20x20, 2v2 or 4-player FFA, 180 degree symmetric."""
import math

import numpy as np
from scipy import ndimage

from .. import SQ
from ..biomes import BIOMES
from ..design import Design
from ..gadgets import eruption_files, lava_cliff_files, lava_cliff_mask, lava_config, paint_field
from ..noise import fbm, smoothstep
from ..symmetry import Symmetry, mirror_pairs, mirror_point
from ..terrain import grid, pit, plateau, road_polyline, smooth_profile
from .base import Param, Template
from .common import flatten_all, four_base_boxes, polar, sym_fields

SIZE = 20
SEA = -60.0            # floor of the lava sea
LAND = 170.0           # island ring
CAUSE_H = 25.0         # causeways (flooded during eruptions)
FLOOD = 46             # lava level during an eruption
RR, RW = 3950.0, 480.0               # island ring: radius, half width
ISLAND_R = 2350.0                    # volcano island
SUMMIT_R0, SUMMIT_R1 = 380.0, 720.0  # crater / summit ring
BREACH_ANG = (-45.0, 135.0)          # lava straits through the ring (NE, SW)
BREACH_HW = 270.0
OUTER_ANG = (-135.0, 45.0)           # outer islands NW, SE
OUTER_R, OUTER_RAD = 5850.0, 820.0
CAUSE_ANGLES = [22.5 + 45 * k for k in range(8)]


def _ang_dist(th, a_deg):
    return np.abs(np.angle(np.exp(1j * (th - math.radians(a_deg)))))


def _ramp_len(dh):
    return max(420.0, dh / math.tan(math.radians(15.0)))      # about 15 degrees real (tank limit 27)


def _causeway(h, p0, p1, h0, h1):
    """Causeway between two land points: ramp down to CAUSE_H, flat across the lava, ramp up.
    Returns the ends of the part that floods."""
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    s = np.linspace(0, L, max(200, int(L / 4)))
    r0, r1 = _ramp_len(h0 - CAUSE_H), _ramp_len(h1 - CAUSE_H)
    prof = np.maximum(smooth_profile(s, r0, h0, CAUSE_H, 220), smooth_profile(L - s, r1, h1, CAUSE_H, 220))
    pts = p0[None] + s[:, None] * ((p1 - p0) / L)[None]
    road_polyline(h, pts, prof, 150, down_deg=50, up_deg=30, influence=700, blend=140)
    wet = np.nonzero(prof < FLOOD + 4)[0]
    return pts[wet[0]], pts[wet[-1]]


class Volcano(Template):
    id = "volcano"
    title = "Volcano"
    modes = ("team", "ffa")
    tags = ("land", "twist")
    players = "2v2 or 4-player FFA"
    description = ("A volcano island in a sea of lava, ringed by islands with four bases (20x20). Every few minutes "
                   "the volcano erupts: lava bombs rain on the slopes and the rising lava floods every causeway.")
    infos = {
        "calm_seconds": "Seconds between two eruptions. During the calm all causeways are open and lava bombs stop. Short calm periods make the map hectic; long ones give time to expand.",
        "flood_seconds": "How long each eruption lasts, in seconds. During an eruption the lava rises over the causeways (units on them take heavy damage) and lava bombs rain on the volcano and the ring.",
        "bomb_damage": "Damage of one lava bomb at the centre of the impact; at the edge it is a quarter. 900 kills small raiders and hurts tanks; 2000 and more destroys most buildings that are not shielded.",
        "bomb_radius": "Size of one lava bomb impact in elmos. Bombs only fall on solid ground on the volcano island and the ring of islands, never on the bases. The danger layer of the preview shows where they can land.",
        "bomb_rate": "How many lava bombs fall per second during an eruption, over the whole map. Higher values make the volcano and the ring very dangerous while it erupts.",
        "outer_islands": "Adds two rich islands in the corners, each linked by a causeway that floods during eruptions. They are worth taking but hard to hold.",
    }
    params = (
        Param("calm_seconds", "Calm between eruptions (s)", "int", 170, min=90, max=360, step=10, adv_min=10, adv_max=1800),
        Param("flood_seconds", "Eruption length (s)", "int", 40, min=20, max=90, step=5, adv_min=5, adv_max=900,
              help="How long the causeways stay flooded"),
        Param("bomb_damage", "Lava bomb damage", "int", 900, min=200, max=2000, step=50, adv_min=0, adv_max=20000,
              help="Damage at the centre of an impact (a quarter of it at the edge)"),
        Param("bomb_radius", "Lava bomb size", "int", 320, min=150, max=500, step=10, adv_min=50, adv_max=1500,
              help="Impact radius in elmos. Bombs only hit solid ground on the volcano island and the ring"),
        Param("bomb_rate", "Lava bombs per second", "float", 0.9, min=0.2, max=2.5, step=0.1, adv_min=0.05, adv_max=10.0),
        Param("outer_islands", "Outer islands", "bool", True,
              help="Two rich islands in the corners, each linked by a causeway"),
    )

    def make(self, v, seed, log=print):
        n = SIZE * 64 + 1
        W = (n - 1) * SQ
        C = W / 2
        P = lambda r, a: polar(C, r, a)
        rng = np.random.default_rng(seed)
        xx, zz = grid(n)
        r = np.hypot(xx - C, zz - C)
        th = np.arctan2(zz - C, xx - C)
        fb = fbm((n, n), rng, base=7, octaves=6); fb = (fb - fb.mean()) / (fb.std() + 1e-6)
        fs = fbm((n, n), rng, base=26, octaves=4); fs = (fs - fs.mean()) / (fs.std() + 1e-6)
        en = fbm((n, n), rng, base=30, octaves=3); en /= np.abs(en).max() + 1e-6
        fb, fs, en = sym_fields("point", fb, fs, en)                    # seamless 180 degree symmetry

        h = np.full((n, n), SEA, np.float32) + 6 * fs
        ring = np.abs(r - RR) - RW
        for a in BREACH_ANG:
            ring = np.maximum(ring, BREACH_HW - _ang_dist(th, a) * r)
        plateau(h, ring, LAND + 22 * fb + 8 * fs, side_deg=52, noise=en, amp=40, round_=40, toe=12)
        outer = OUTER_ANG if v["outer_islands"] else ()
        for a in outer:
            ox, oz = P(OUTER_R, a)
            plateau(h, np.hypot(xx - ox, zz - oz) - OUTER_RAD, LAND - 10 + 18 * fb, side_deg=50, noise=en, amp=60,
                    round_=40, toe=12)
        for a in (-60.0, -30.0, -45.0, -52.0, -38.0):        # basalt columns in the lava sea (NE, SW)
            for _ in range(2):
                px, pz = P(rng.uniform(4600, 6600), a + rng.uniform(-6, 6))
                plateau(h, np.hypot(xx - px, zz - pz) - rng.uniform(70, 160), rng.uniform(200, 340), side_deg=80,
                        noise=en, amp=20, round_=10, toe=4)
        t = np.clip(1 - r / ISLAND_R, 0, 1)                   # concave cone with radial ribs
        cone = LAND + 30 + 640 * t ** 1.5 + 20 * np.sin(th * 12 + 1.5 * fs) * t * (1 - t) * 4 + 14 * fb * t
        island = r - ISLAND_R + 60 * en
        cone = np.where(island < 0, cone, SEA)
        plateau(h, island, LAND + 30 + 14 * fb, side_deg=50, round_=40, toe=12)
        h = np.maximum(h, cone).astype(np.float32)
        summit_h = float(LAND + 30 + 640 * (1 - SUMMIT_R1 / ISLAND_R) ** 1.5)
        ws = 1 - smoothstep(SUMMIT_R1 - 40, SUMMIT_R1 + 220, r)
        h = h + (summit_h + 6 * fs - h) * ws * (r > SUMMIT_R0 - 60)
        pit(h, r - SUMMIT_R0 + 25 * en, summit_h - 150 + 8 * fs, side_deg=70, round_=20, toe=6)

        hs = ndimage.gaussian_filter(h, 3)
        hat = lambda x, z: float(hs[int(z / SQ), int(x / SQ)])
        wet = []
        for a in CAUSE_ANGLES:                                 # 8 causeways to the volcano
            ua = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
            shore_i = np.array(P(ISLAND_R + 80, a)); shore_o = np.array(P(RR - RW + 60, a))
            L0 = 600.0
            for _ in range(4):                                 # ramp length fitted to the cone height
                L0 = _ramp_len(hat(*(shore_i - ua * L0)) - CAUSE_H)
            p0 = shore_i - ua * L0; p1 = shore_o + ua * _ramp_len(hat(*P(RR, a)) - CAUSE_H)
            wet.append(_causeway(h, p0, p1, hat(*p0), hat(*p1)))
        for a in BREACH_ANG:                                   # across the lava straits
            ext = BREACH_HW + 80
            tdir = np.array([-math.sin(math.radians(a)), math.cos(math.radians(a))])
            mid = np.array(P(RR, a))
            dh = hat(*P(RR, a + 20)) - CAUSE_H
            p0 = mid - tdir * (ext + _ramp_len(dh)); p1 = mid + tdir * (ext + _ramp_len(dh))
            wet.append(_causeway(h, p0, p1, hat(*p0), hat(*p1)))
        for a in outer:                                        # to the outer islands
            ua = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
            shore_r = np.array(P(RR + RW - 60, a)); shore_o = np.array(P(OUTER_R - OUTER_RAD + 60, a))
            p0 = shore_r - ua * _ramp_len(hat(*P(RR, a)) - CAUSE_H)
            p1 = shore_o + ua * _ramp_len(hat(*P(OUTER_R, a)) - CAUSE_H)
            wet.append(_causeway(h, p0, p1, hat(*p0), hat(*p1)))
        h = 0.5 * (h + h[::-1, ::-1])

        starts = [P(RR, 180), P(RR, 270), P(RR, 0), P(RR, 90)]   # W, N (team 0), E, S (team 1)
        west = []
        m = lambda x, z, val: west.append((x, z, val))
        for a in (180, 270):
            for da, dr in ((-7, 220), (7, 220), (0, -330)):
                m(*P(RR + dr, a + da), 2.0)
            for da in (-26, 26):
                m(*P(RR + 60, a + da), 2.2)
        m(*P(RR, -45 - 22), 2.6)
        m(*P(RR, 135 + 22), 2.6)
        for a in (180, 225, 270, 315):
            m(*P(1550, a), 2.6)
        for a in (225, 315):
            m(*P(560, a), 4.0)
        geos = [P(1050, 225), P(1050, 315)]
        if v["outer_islands"]:
            ox, oz = P(OUTER_R, -135)
            for da in (0, 120, 240):
                aa = math.radians(da + 20)
                m(ox + 420 * math.cos(aa), oz + 420 * math.sin(aa), 3.2)
            geos.append((ox, oz))
        sym = Symmetry("diag", W, W)
        mexes = mirror_pairs(west, sym)
        geos = geos + [sym.mirror(*g) for g in geos]
        flatten_all(h, starts, mexes, geos)
        h = mirror_point(h).astype(np.float32)

        # checks during an eruption (everything below the flood level is lava)
        from ..checks import unit_masks
        ix = lambda p: (int(p[1] / SQ), int(p[0] / SQ))
        lab, _ = ndimage.label(unit_masks(h)["tanks"] & (h > FLOOD + 2))
        w_, n_, e_, s_ = starts
        halves = lab[ix(w_)] == lab[ix(n_)] and lab[ix(e_)] == lab[ix(s_)] and lab[ix(w_)] > 0
        split = lab[ix(w_)] != lab[ix(e_)]
        volc = lab[ix((C + 1500, C))] not in (lab[ix(w_)], lab[ix(e_)])
        notes = [f"During an eruption each team keeps its half of the ring: {'yes' if halves else 'NO'}",
                 f"During an eruption the teams are cut apart: {'yes' if split else 'NO'}",
                 f"During an eruption the volcano island is cut off: {'yes' if volc else 'NO'}"]

        crater = (r < SUMMIT_R0 - 40) & (h < summit_h - 60)
        hazard = lava_cliff_mask(h, starts) | crater
        files, _ = lava_cliff_files(hazard)
        files["mapconfig/lava_config.lua"] = lava_config(FLOOD, calm_s=v["calm_seconds"], high_s=v["flood_seconds"],
                                                         rise_speed=0.1, fall_speed=0.08, damage=160,
                                                         title="volcano eruptions")
        quads = []
        for a0, a1 in wet:
            d = a1 - a0; u = d / np.linalg.norm(d); nrm = np.array([-u[1], u[0]])
            quads.append([tuple(a0 + nrm * 175), tuple(a1 + nrm * 175), tuple(a1 - nrm * 175), tuple(a0 - nrm * 175)])
        # lava bomb spots: solid ground above the flood line, never lava, crater or lava cliffs
        SP = 200.0
        solid = (h > FLOOD + 40) & ~ndimage.binary_dilation(hazard | crater | (h < FLOOD + 10), iterations=12)
        isl, rng_t = [], []
        for zc in np.arange(SP / 2, W, SP):
            for xc in np.arange(SP / 2, W, SP):
                rc = math.hypot(xc - C, zc - C)
                if not solid[int(zc / SQ), int(xc / SQ)] or rc < SUMMIT_R0 + 120:
                    continue
                if min(math.hypot(xc - sx, zc - sz) for sx, sz in starts) < 450:
                    continue                                   # spare the commanders' start spots
                (isl if rc < ISLAND_R else rng_t).append((rc, xc, zc))
        isl.sort()
        island_t = [(x, z) for _, x, z in isl]
        ring_t = [(x, z) for rc, x, z in rng_t if abs(rc - RR) < RW]
        zone = np.zeros(h.shape, bool)
        R_cells = int(v["bomb_radius"] / SQ)
        for x, z in island_t + ring_t:
            i, j = int(z / SQ), int(x / SQ)
            zone[max(0, i - R_cells):i + R_cells + 1, max(0, j - R_cells):j + R_cells + 1] = True
        zone = ndimage.binary_opening(zone, iterations=3) & (h > FLOOD)
        files.update(eruption_files((C, C), SUMMIT_R0, ISLAND_R - 250, summit_h, FLOOD, quads,
                                    bomb_every_s=round(1.0 / v["bomb_rate"], 3), bomb_damage=v["bomb_damage"],
                                    bomb_radius=v["bomb_radius"], ring_r=(RR - RW + 100, RR - 150),
                                    island_targets=island_t, ring_targets=ring_t, target_spacing=SP * 0.5))
        notes.append(f"Lava bomb spots on solid ground: {len(island_t)} on the volcano, {len(ring_t)} on the ring")
        # paint: lava sea, lava cliffs, crater lake, flood line, cooled lava streams on the flanks
        sea = 1 - smoothstep(-10, 4, h)
        under = (1 - smoothstep(FLOOD - 3, FLOOD + 6, h)) * (1 - sea)
        wob = fbm(h.shape, np.random.default_rng(seed + 5), base=9, octaves=4); wob = (wob - wob.mean()) / (wob.std() + 1e-6)
        streams = smoothstep(0.72, 0.9, np.sin(th * 9 + 0.0012 * r + 0.9 * wob)) * (1 - smoothstep(SUMMIT_R1 + 200, ISLAND_R - 150, r))
        ash = (1 - smoothstep(SUMMIT_R1, ISLAND_R - 200, r)) * 0.55
        flank = np.clip(np.maximum(streams * (0.6 + 0.4 * (1 - r / ISLAND_R)), ash), 0, 1) * (h > FLOOD + 10)
        paint = dict(lava=np.maximum(paint_field(hazard), sea).astype(np.float32),
                     scorch=np.maximum(under, flank).astype(np.float32),
                     molten=paint_field(crater, 1.5).astype(np.float32))
        biome = dict(BIOMES["ashland"]); biome["water_damage"] = 0
        team0, team1 = [w_, n_], [e_, s_]
        desc = ("Volcano: a volcano island in a sea of lava, ringed by islands. Every few minutes the volcano erupts: "
                "lava bombs rain on the slopes and the rising lava floods every causeway. 2v2 or 4-player FFA.")
        return Design(hm=h, sym=sym, starts=starts, teams=[team0, team1], mexes=mexes, geos=geos, biome=biome,
                      title="Volcano", description=desc,
                      startboxes=four_base_boxes(team0, team1, ("West", "W"), ("East", "E"), W, half=950),
                      paint=paint, extra_files=files, random_trees=False, notes=notes,
                      notes_ok=bool(halves and split and volc and island_t), hazard=hazard, blocked=h < 1,
                      event_zone=zone, event_label="lava bombs",
                      start_colors=[(60, 255, 60), (60, 255, 60), (255, 70, 70), (255, 70, 70)])
