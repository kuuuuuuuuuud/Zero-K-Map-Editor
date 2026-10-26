"""Reachability checks per Zero-K movement class, using the engine's slope test (terrain.move_slope).

Effective limits (movedef maxSlope x 1.5 in the engine): tanks and hovers 27 degrees real slope,
bots and amphibians 54 degrees. Water depth limit for tanks and bots: 22 elmos. Ships: water deeper than
15 elmos (the heavy BOAT5/UBOAT3 move classes; light ships need only 5).
"""
import numpy as np
from scipy import ndimage

from . import SQ
from .terrain import move_slope

CLASSES = ("tanks", "bots", "spiders", "amphibians", "hovers")
SHIP_DEPTH = 15.0
PROFILES = ("land", "naval")


def unit_masks(hm):
    """Bool grids: where each movement class can stand and drive."""
    sl = move_slope(hm)
    return {
        "tanks": (sl < 18) & (hm > -22),
        "bots": (sl < 36) & (hm > -16),
        "spiders": hm > -22,
        "amphibians": sl < 36,
        "hovers": (sl < 18) | (hm < 0),
        "ships": hm < -SHIP_DEPTH,
    }


def cell(p):
    return int(p[1] / SQ), int(p[0] / SQ)


def connected(mask, a, b):
    lab, _ = ndimage.label(mask)
    la, lb = lab[cell(a)], lab[cell(b)]
    return bool(la > 0 and la == lb)


def unreachable_mexes(hm, mexes, start, cls="tanks"):
    lab, _ = ndimage.label(unit_masks(hm)[cls])
    a = lab[cell(start)]
    return [m for m in mexes if lab[int(m["z"] / SQ), int(m["x"] / SQ)] != a]


def report(hm, team0, team1, mexes=(), gates=None, blocked=None, enemy="the enemy", movement_profile="land",
           naval_starts=None, others=()):
    """Plain-English check report.
    team0/team1: start points per team; gates: optional [(name, bool mask)] of choke areas;
    blocked: optional bool grid that no ground unit survives (e.g. lava); enemy: wording for team 1.
    movement_profile "land": ok = tanks and bots reach the enemy and every metal spot is reachable for tanks.
    movement_profile "naval": ok = ships connect the ports (naval_starts), hovers and amphibians connect the
    bases, every base reaches its port, amphibians reach every metal spot and ships every underwater one.
    others: start points of further teams (free-for-all maps): every team must reach every other.
    Returns (ok, lines)."""
    if movement_profile not in PROFILES:
        raise ValueError(f"unknown movement profile {movement_profile!r}, expected one of {PROFILES}")
    if movement_profile == "naval":
        return _report_naval(hm, team0, team1, mexes, gates, blocked, enemy, naval_starts)
    lines = []
    ok = True
    masks = unit_masks(hm)
    for cls in CLASSES:
        m = masks[cls] if blocked is None else masks[cls] & ~blocked
        reach = connected(m, team0[0], team1[0]) and all(connected(m, team0[0], t[0]) for t in others)
        own = all(connected(m, t[0], p) for t in (team0, team1, *others) for p in t[1:])
        text = f"{cls.capitalize():11s} can reach {enemy}: {'yes' if reach else 'NO'}"
        if not own:
            text += " (own bases are not connected!)"
        if gates:
            via = []
            for gname, gm in gates:
                other_gates = np.zeros(hm.shape, bool)
                for g2, gm2 in gates:
                    if g2 != gname:
                        other_gates |= gm2
                if connected(m & ~other_gates, team0[0], team1[0]):
                    via.append(gname)
            allg = np.zeros(hm.shape, bool)
            for _, gm in gates:
                allg |= gm
            sealed = not connected(m & ~allg, team0[0], team1[0])
            if reach:
                text += f", only through: {', '.join(via) or '-'}" if sealed else ", also outside the chokes"
        lines.append(text)
        if cls in ("tanks", "bots"):
            ok &= reach and own
    if len(mexes):
        tm = masks["tanks"] if blocked is None else masks["tanks"] & ~blocked
        lab, _ = ndimage.label(tm)
        a = lab[cell(team0[0])]
        bad = [m for m in mexes if lab[int(m["z"] / SQ), int(m["x"] / SQ)] != a]
        lines.append(f"Metal spots unreachable for tanks: {len(bad)} of {len(mexes)}")
        ok &= not bad
    return ok, lines


def _report_naval(hm, team0, team1, mexes, gates, blocked, enemy, naval_starts):
    masks = unit_masks(hm)
    if blocked is not None:
        masks = {k: m & ~blocked for k, m in masks.items()}
    lines, ok = [], True
    for cls in CLASSES:
        reach = connected(masks[cls], team0[0], team1[0])
        need = cls in ("amphibians", "hovers")
        text = f"{cls.capitalize():11s} can reach {enemy}: {'yes' if reach else 'NO'}"
        if not reach and not need:
            text += " (optional on naval maps)"
        lines.append(text)
        ok &= reach or not need
    ships = masks["ships"]
    inside = lambda p: 0 <= int(p[1] / SQ) < hm.shape[0] and 0 <= int(p[0] / SQ) < hm.shape[1]
    ports = naval_starts if naval_starts and len(naval_starts) >= 2 and naval_starts[0] and naval_starts[1] else None
    if ports is None:
        lines.append("Ships can reach the enemy: NO (no ports defined)")
        return False, lines
    p0, p1 = ports[0][0], ports[1][0]
    wet = all(inside(p) and ships[cell(p)] for p in (p0, p1))
    sail = wet and connected(ships, p0, p1)
    lines.append(f"Ships       can reach {enemy}: {'yes' if sail else 'NO'}" + ("" if wet else " (a port is not in deep water)"))
    ok &= sail
    amph = masks["amphibians"]
    access = all(connected(amph, base[0], port[0]) for base, port in ((team0, ports[0]), (team1, ports[1])))
    lines.append(f"Amphibian access from bases to ports: {'yes' if access else 'NO'}")
    ok &= access
    if len(mexes):
        lab, _ = ndimage.label(amph)
        a = lab[cell(team0[0])]
        bad = [m for m in mexes if lab[int(m["z"] / SQ), int(m["x"] / SQ)] != a or a == 0]
        lines.append(f"Metal spots unreachable for amphibian constructors: {len(bad)} of {len(mexes)}")
        ok &= not bad
        wet_m = [m for m in mexes if hm[int(m["z"] / SQ), int(m["x"] / SQ)] < -SHIP_DEPTH]
        if wet_m:
            slab, _ = ndimage.label(ships)
            s0 = slab[cell(p0)]
            bad_s = [m for m in wet_m if slab[int(m["z"] / SQ), int(m["x"] / SQ)] != s0 or s0 == 0]
            lines.append(f"Underwater metal spots unreachable for ships: {len(bad_s)} of {len(wet_m)}")
            ok &= not bad_s
    return ok, lines
