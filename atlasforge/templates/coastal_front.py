"""Coastal Front: an uninterrupted mainland front beside a shared coastal sea."""
import numpy as np
from scipy import ndimage

from ..checks import connected, unit_masks
from ..terrain import plateau
from .base import Param, Template
from ._naval import finish, naval_params, sea


class CoastalFrontTemplate(Template):
    id = "coastal_front"
    title = "Coastal Front"
    modes = ("1v1", "team")
    tags = ("land", "sea")
    players = "1v1 to 4v4"
    description = ("A continuous mainland front runs beside a broad coastal sea. "
                   "Fight across land, raid the shoreline with ships, or land amphibious forces behind the front.")
    infos = {
        "land_share": "How far the mainland reaches from each side's back edge before the beach, as a fraction of the map depth. More mainland means a bigger land war and a narrower sea; less mainland makes the sea the main battlefield.",
        "headlands": "Size of the capes that reach into the sea, as a fraction of the map width. Headlands give cover for coastal defences and natural landing spots; 0 gives a straight coastline.",
    }
    params = naval_params() + (
        Param("land_share", "Mainland depth", "float", 0.44, min=0.38, max=0.58, step=0.02,
              adv_min=0.25, adv_max=0.72, help="Fraction of map depth occupied by the mainland before its beach"),
        Param("headlands", "Headland reach", "float", 0.035, min=0.0, max=0.06, step=0.005,
              adv_max=0.12, help="Symmetric coastal headlands as a fraction of map width"),
    )

    def make(self, v, seed, log=print):
        h, xx, zz, edge, rng, W = sea(v, seed)
        # A continental shore keeps broad bays rather than small ripples in the
        # shoreline noise; filter before elevation so shallow banks stay smooth too.
        h = ndimage.gaussian_filter(h, 32)
        edge = ndimage.gaussian_filter(edge, 32)
        shoreline = W * (v["land_share"] + v["headlands"] * np.cos(4 * np.pi * xx / W))
        plateau(h, zz - shoreline, 100 + 18 * edge, side_deg=v["beach_slope"],
                noise=edge, amp=v["coast_noise"], round_=96, toe=48)
        # A broad submerged shelf supports expansion even with a deep sea and a shallow beach.
        # Leave the outer edge and the approach to the shore at the requested full sea depth.
        shelf_axis = W * (0.83 + 0.018 * np.cos(2 * np.pi * xx / W))
        plateau(h, np.abs(zz - shelf_axis) - 0.10 * W, -min(v["depth"], 80) + 3 * edge,
                side_deg=12, round_=100, toe=48)
        base = (0.11 * W, 0.18 * W)
        port = (0.14 * W, 0.88 * W)
        # A continental shelf needs a wider blend than the small offshore islands.
        d = finish(self, v, h, xx, zz, W, rng, base, port, bottom_scale=1024)
        # Seeded, broad microrelief breaks up otherwise level mainland without
        # changing water depths or the explicit movement corridors.
        relief = ndimage.gaussian_filter(rng.normal(size=d.hm.shape), 60)
        relief = 0.5 * (relief + d.sym.mirror_grid(relief))
        relief -= relief.mean()
        relief /= max(float(np.max(np.abs(relief))), 1e-9)
        protected = np.zeros(d.hm.shape, dtype=bool)
        land_route = np.abs(zz - base[1]) < 0.065 * W
        protected |= land_route
        for x, z in [*d.starts, *d.geos]:
            protected |= (xx - x) ** 2 + (zz - z) ** 2 < 180 ** 2
        for m in d.mexes:
            protected |= (xx - m["x"]) ** 2 + (zz - m["z"]) ** 2 < 180 ** 2
        protected |= d.keep_clear
        protected |= d.blocked if d.blocked is not None else False
        protected |= d.hazard if d.hazard is not None else False
        for _, gate in d.gates or ():
            protected |= gate
        eligible = (d.hm >= 0) & ~protected
        d.hm[eligible] += (24.0 * relief[eligible]).astype(d.hm.dtype)
        # Keep a broad staging corridor intact under erosion and free of blocking decoration.
        d.keep_clear |= land_route
        d.tree_block |= land_route
        tanks = unit_masks(d.hm)["tanks"]
        front_ok = connected(tanks & land_route, d.starts[0], d.starts[1])
        d.notes += [f"Continuous mainland tank front: {'yes' if front_ok else 'NO'}"]
        d.notes_ok &= front_ok
        d.gates = [
            ("Mainland front", (np.abs(xx - W / 2) < 0.05 * W) & (zz < (v["land_share"] - 0.08) * W)),
            ("Coastal fleet route", (np.abs(xx - W / 2) < 0.05 * W) & (zz > 0.78 * W)),
        ]
        return d
