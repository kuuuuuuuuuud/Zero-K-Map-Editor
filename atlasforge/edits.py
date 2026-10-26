"""Manual edits of a finished design (editor stage A): metal spots, geovents and start points.

A map is (template, settings, seed) plus a list of edits that is applied to the finished Design. The terrain
is not recomputed, so forge.make() stays deterministic and undo/redo is just a shorter list.

Edit entries (one per user action, positions in elmos, address the object the user clicked):
    {"op": "move_mex",  "from": [x, z], "to": [x, z]}
    {"op": "add_mex",   "at": [x, z], "metal": 2.0}
    {"op": "del_mex",   "at": [x, z]}
    {"op": "set_metal", "at": [x, z], "metal": 3.0}
    {"op": "move_geo" | "add_geo" | "del_geo", ...}        (as for mexes, no metal)
    {"op": "move_start", "from": [x, z], "to": [x, z]}    (the number of players comes from the template)
    {"op": "set_box", "team": k, "poly": i, "points": [[x, z], ...]}   (polygon i of team k's start box, 3+ points)

Objects are found by position (nearest within TOL elmos), not by index, so edits stay meaningful after the
settings change. With symmetry on, an edit acts on the whole orbit of the clicked object (mirror image, or the
N rotations of a free-for-all map). Edits that cannot be applied are returned as problems, never raised.
"""
import dataclasses
import math

from .symmetry import RotSymmetry, match_orbit, orbit, orbit_degenerate

TOL = 24.0            # elmos: how far from an object a click may be to address it
MIN_GAP = 40.0        # elmos: closest allowed distance between two metal spots / geovents

OPS = ("move_mex", "add_mex", "del_mex", "set_metal", "move_geo", "add_geo", "del_geo", "move_start", "set_box")


def copy_design(d):
    """Cheap copy for editing: the heightmap and masks are shared, only the editable lists are copied."""
    return dataclasses.replace(
        d, mexes=[dict(m) for m in d.mexes], geos=[tuple(g) for g in d.geos],
        starts=[tuple(p) for p in d.starts], teams=[[tuple(p) for p in t] for t in d.teams], notes=list(d.notes))


def side_of(sym, x, z):
    """Side (or player index on free-for-all maps) a spot belongs to."""
    if isinstance(sym, RotSymmetry):
        return sym.sector(x, z)
    return 0 if sym.side(x, z) < 0 else 1


def _pt(v, name):
    if not isinstance(v, (list, tuple)) or len(v) != 2 or not all(
            isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in v):
        raise ValueError(f"{name}: expected [x, z]")
    return float(v[0]), float(v[1])


def _nearest(points, p, tol=TOL, skip=()):
    best, bd = None, tol
    for i, q in enumerate(points):
        if i in skip:
            continue
        dd = math.hypot(q[0] - p[0], q[1] - p[1])
        if dd <= bd:
            best, bd = i, dd
    return best


def _inside(sym, p):
    return 0 <= p[0] <= sym.W and 0 <= p[1] <= sym.H


def _targets(sym, p, on):
    """Positions an edit at p touches: the whole orbit (symmetry on) or only p."""
    return orbit(sym, p[0], p[1]) if on else [p]


def _collides(points, others_skip, spots):
    """Does any of spots come closer than MIN_GAP to a point of points (ignoring indices in others_skip)?"""
    for s in spots:
        for i, q in enumerate(points):
            if i not in others_skip and math.hypot(q[0] - s[0], q[1] - s[1]) < MIN_GAP:
                return True
    for i, s in enumerate(spots):                           # the orbit points against each other
        if any(math.hypot(t[0] - s[0], t[1] - s[1]) < MIN_GAP for t in spots[i + 1:]):
            return True
    return False


def _orbit_ok(sym, p, on):
    if on and orbit_degenerate(sym, p[0], p[1]):
        return "on the symmetry axis or at the centre: it has no mirror image (turn symmetry off to place it there)"
    return None


def _matches(sym, ref, points, on):
    """Indices (original first) of the objects belonging to ref's orbit. The first entry must exist."""
    if not on:
        i = _nearest(points, ref)
        return [] if i is None else [i]
    hits = match_orbit(sym, ref, points, tol=TOL)
    if hits[0] is None:
        return []
    out = []
    for h in hits:
        if h is not None and h not in out:
            out.append(h)
    return out


def apply_edits(design, edits, symmetry=True):
    """-> (edited copy of design, problems). problems: [{"index", "edit", "reason"}] for edits not applied
    (object not found = orphaned, or the result would break the map). The input design is not modified."""
    d = copy_design(design)
    sym = d.sym
    problems = []

    def fail(i, e, why):
        problems.append(dict(index=i, edit=e, reason=why))

    for i, e in enumerate(edits or []):
        try:
            _apply_one(d, sym, e, symmetry, lambda why, i=i, e=e: fail(i, e, why))
        except ValueError as ex:
            fail(i, e, str(ex))
    return d, problems


def _apply_one(d, sym, e, on, fail):
    op = e.get("op") if isinstance(e, dict) else None
    if op not in OPS:
        return fail("unknown edit")
    if op == "set_box":
        return _set_box(d, sym, e, on, fail)
    kind = op.split("_")[1] if op != "set_metal" else "mex"
    verb = op.split("_")[0] if op != "set_metal" else "set"
    if kind == "mex":
        pts = d.mexes
    elif kind == "geo":
        pts = d.geos
    else:
        pts = d.starts
    xy = [(p["x"], p["z"]) for p in pts] if kind == "mex" else pts

    if verb == "add":
        at = _pt(e.get("at"), "at")
        spots = _targets(sym, at, on)
        if not all(_inside(sym, s) for s in spots):
            return fail("outside the map")
        why = _orbit_ok(sym, at, on)
        if why:
            return fail(why)
        if _collides(list(xy) + [(g[0], g[1]) for g in d.geos if kind == "mex"] +
                     [(m["x"], m["z"]) for m in d.mexes if kind == "geo"], (), spots):
            return fail("too close to another metal spot or geovent")
        for s in spots:
            if kind == "mex":
                m = float(e.get("metal", 2.0))
                d.mexes.append(dict(x=float(s[0]), z=float(s[1]), metal=m, side=side_of(sym, *s)))
            else:
                d.geos.append((float(s[0]), float(s[1])))
        return None

    src = _pt(e.get("at" if verb in ("del", "set") else "from"), "at" if verb in ("del", "set") else "from")
    idx0 = _nearest(xy, src)
    if idx0 is None:
        return fail("nothing there (the map changed since this edit was made)")
    ref = xy[idx0]
    hit = _matches(sym, ref, xy, on)
    if not hit:
        return fail("nothing there (the map changed since this edit was made)")

    if verb == "set":
        m = float(e.get("metal", 0))
        if not m > 0:
            return fail("metal must be positive")
        for h in hit:
            d.mexes[h]["metal"] = m
        return None

    if verb == "del":
        if kind == "start":
            return fail("start points cannot be deleted")
        for h in sorted(hit, reverse=True):
            del (d.mexes if kind == "mex" else d.geos)[h]
        return None

    # move
    to = _pt(e.get("to"), "to")
    if on:
        why = _orbit_ok(sym, to, on) or (orbit_degenerate(sym, ref[0], ref[1]) and _orbit_ok(sym, ref, on))
        if why:
            return fail(why)
    orb_to = _targets(sym, to, on)
    if on and len(hit) > 1:                                   # keep each partner paired with its own image
        pairs = match_orbit(sym, ref, xy, tol=TOL)
        moves = [(h, orb_to[k]) for k, h in enumerate(pairs) if h is not None]
    else:
        moves = [(hit[0], to)]
    if not all(_inside(sym, t) for _, t in moves):
        return fail("outside the map")
    if kind != "start":
        skip = {h for h, _ in moves}
        others = [p for j, p in enumerate(xy) if j not in skip]
        extra = [(g[0], g[1]) for g in d.geos] if kind == "mex" else [(m["x"], m["z"]) for m in d.mexes]
        if _collides(others + extra, (), [t for _, t in moves]):
            return fail("too close to another metal spot or geovent")
    if kind == "mex":
        for h, t in moves:
            d.mexes[h].update(x=float(t[0]), z=float(t[1]), side=side_of(sym, *t))
    elif kind == "geo":
        for h, t in moves:
            d.geos[h] = (float(t[0]), float(t[1]))
    else:
        for h, t in moves:
            old, new = d.starts[h], (float(t[0]), float(t[1]))
            d.starts[h] = new
            for team in d.teams:
                for j, q in enumerate(team):
                    if tuple(q) == tuple(old):
                        team[j] = new
    return None


def _set_box(d, sym, e, on, fail):
    """Replace one polygon of a team's start box. With symmetry on, the same polygon is mirrored (rotated) onto the
    team whose start point is the image of this team's start point, so each team keeps its own box."""
    from .app.luatable import startboxes
    from .formats import startboxes_lua, startboxes_to_lua

    team, pi = e.get("team"), e.get("poly")
    if any(not isinstance(v, int) or isinstance(v, bool) for v in (team, pi)):
        raise ValueError("team and poly: integers expected")
    pts = e.get("points")
    if not isinstance(pts, list) or len(pts) < 3:
        raise ValueError("points: at least 3 [x, z] points")
    poly = [_pt(p, "points") for p in pts]

    boxes = startboxes(d.startboxes if d.startboxes is not None else startboxes_lua(sym, d.starts))
    by_team = {b["team"]: b for b in boxes}
    if team not in by_team or not 0 <= pi < len(by_team[team]["polygons"]):
        return fail("start box not found")

    updates = [(team, poly)]
    if on:
        owners = [b for b in boxes if b["startpoints"]]              # teams that have a start point to mirror
        src = by_team[team]["startpoints"]
        if not src:
            return fail("start box not found")
        s = tuple(src[0])
        hits = match_orbit(sym, s, [tuple(b["startpoints"][0]) for b in owners], tol=TOL)
        if hits[0] is None:
            return fail("start box not found")
        for j, h in enumerate(hits):
            if j == 0 or h is None:
                continue
            t = owners[h]["team"]
            if not 0 <= pi < len(by_team[t]["polygons"]):
                return fail("start box not found")
            image = [orbit(sym, p[0], p[1])[j] for p in poly]
            updates.append((t, image))
    for _, q in updates:
        if not all(_inside(sym, p) for p in q):
            return fail("outside the map")

    for t, q in updates:
        by_team[t]["polygons"][pi] = [[float(p[0]), float(p[1])] for p in q]
    d.startboxes = startboxes_to_lua(boxes)
    return None


# ----------------------------------------------------------------------------- live checks
STEEP = 30.0          # degrees: a metal spot or start point on ground steeper than this is flagged
START_MEX_GAP = 120.0  # elmos: a metal spot closer than this to a start point sits inside the commander
BOX_MIN_EDGE = 300.0   # elmos: a start box edge shorter than this is flagged as very small


def _ground(d, x, z):
    """(height, slope) of the heightmap at a spot in elmos."""
    from . import SQ
    h = d.hm
    ix = min(max(int(round(x / SQ)), 0), h.shape[1] - 1)
    iz = min(max(int(round(z / SQ)), 0), h.shape[0] - 1)
    return float(h[iz, ix]), iz, ix


def editor_checks(d, symmetry=True):
    """Checks that only matter once things are moved by hand. -> [{"level": "warn"|"error", "text", "x", "z"}]
    Reachability and the template's own checks come from forge.check()."""
    from .terrain import slope_deg
    slope = slope_deg(d.hm)
    out = []

    def add(level, text, p):
        out.append(dict(level=level, text=text, x=float(p[0]), z=float(p[1])))

    spots = [("Metal spot", (m["x"], m["z"])) for m in d.mexes] + [("Geovent", (g[0], g[1])) for g in d.geos] \
        + [("Start point", (p[0], p[1])) for p in d.starts]
    for what, p in spots:
        h, iz, ix = _ground(d, *p)
        if what != "Start point" or d.movement_profile != "naval":
            if h < 0 and what == "Metal spot":
                pass                                           # underwater metal is allowed on every map (reachability: checks.report)
            elif h < 0 and not (d.blocked is not None and d.blocked[iz, ix]):
                add("error", f"{what} is under water", p)
            elif slope[iz, ix] > STEEP:
                add("warn", f"{what} is on very steep ground", p)
        if what == "Start point" and d.blocked is not None and d.blocked[iz, ix]:
            add("error", "Start point is on ground no unit can stand on", p)
    for m in d.mexes:
        for s in d.starts:
            if math.hypot(m["x"] - s[0], m["z"] - s[1]) < START_MEX_GAP:
                add("warn", "Metal spot is almost on a start point", (m["x"], m["z"]))
                break
    boxes = _start_boxes(d)
    polys = [(b["team"], poly) for b in boxes for poly in b["polygons"]]
    for s in d.starts:
        owner = _box_owner(boxes, s)                           # None: no team has a start point to match
        own = [poly for team, poly in polys if owner is None or team == owner]
        if polys and not any(_in_poly(s, poly) for poly in own):
            add("error", "Start point is outside its start box", s)
    for i, (team, poly) in enumerate(polys):
        if any(not (0 <= x <= d.sym.W and 0 <= z <= d.sym.H) for x, z in poly):
            add("error", "Start box leaves the map", _centre(poly))
        if any(math.hypot(q[0] - p[0], q[1] - p[1]) < BOX_MIN_EDGE for p, q in _edges(poly)):
            add("warn", "Start box is very small", _centre(poly))
        for other_team, other in polys[i + 1:]:
            if other_team != team and _polys_overlap(poly, other):
                add("error", "Start boxes overlap", _centre(poly))
    totals = {}
    for m in d.mexes:
        totals[m["side"]] = totals.get(m["side"], 0.0) + m["metal"]
    if len(totals) > 1 and max(totals.values()) - min(totals.values()) > 0.05:
        label = "player" if isinstance(d.sym, RotSymmetry) else "side"
        add("warn", f"Metal is not equal for every {label} (" + ", ".join(
            f"{k}: {v:.1f}" for k, v in sorted(totals.items())) + ")" + ("" if symmetry else " - symmetry is off"),
            (d.sym.W / 2, d.sym.H / 2))
    return out


def _in_poly(p, poly):
    x, z, inside = p[0], p[1], False
    for (x1, z1), (x2, z2) in zip(poly, poly[1:] + poly[:1]):
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            inside = not inside
    return inside


def _start_boxes(d):
    """Team boxes of the design: its own map_startboxes.lua, or the ones the symmetry layout generates. [] if unreadable."""
    from .app.luatable import startboxes
    from .formats import startboxes_lua
    try:
        return startboxes(d.startboxes if d.startboxes is not None else startboxes_lua(d.sym, d.starts))
    except Exception:
        return []


def _box_owner(boxes, p):
    """Team whose start point is nearest to p (the start point belongs to that team), or None."""
    best = None
    for b in boxes:
        for s in b["startpoints"]:
            dist = math.hypot(s[0] - p[0], s[1] - p[1])
            if best is None or dist < best[0]:
                best = (dist, b["team"])
    return None if best is None else best[1]


def _edges(poly):
    return list(zip(poly, poly[1:] + poly[:1]))


def _centre(poly):
    return (sum(x for x, _ in poly) / len(poly), sum(z for _, z in poly) / len(poly))


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _polys_overlap(p, q):
    """Two polygons share an area or touch edge to edge (proper crossing) or contain a corner of each other."""
    for a, b in _edges(p):
        for c, d in _edges(q):
            if _orient(a, b, c) * _orient(a, b, d) < 0 and _orient(c, d, a) * _orient(c, d, b) < 0:
                return True
    return any(_in_poly(v, q) for v in p) or any(_in_poly(v, p) for v in q)
