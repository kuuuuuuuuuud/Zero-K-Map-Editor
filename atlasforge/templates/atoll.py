"""Atoll: two home arcs around a lagoon, with northern and southern fleet entrances."""
import numpy as np

from ..checks import connected, unit_masks
from ..terrain import box_sdf, ellipse_sdf, pit
from .base import Param, Template
from ._naval import finish, islands, naval_params, sea


class AtollTemplate(Template):
    id = "atoll"
    title = "Atoll"
    modes = ("1v1", "team")
    tags = ("sea", "chokes")
    players = "1v1 to 4v4"
    description = ("Opposing island arcs surround a contested lagoon. Two deep entrances link the lagoon "
                   "to the outer ocean; control the inside route or sail around the island flanks.")
    infos = {
        "ring_radius": "Distance from the lagoon in the middle to the ring of islands, as a fraction of the map width. A large ring gives a big lagoon for fleet battles; a small ring brings the island arcs (and their defences) close together.",
        "ring_width": "Width of the dry island arcs as a fraction of the map width. Wide arcs give room for land bases and defences; thin arcs are easy for ships to shoot across.",
        "passage_width": "Minimum width in elmos of the deep-water entrances in the north and south that link the lagoon to the outer sea. Narrow entrances are easy to block with a few ships or torpedo turrets; wide ones let whole fleets pass.",
    }
    params = naval_params() + (
        Param("ring_radius", "Atoll radius", "float", 0.30, min=0.28, max=0.32, step=0.01,
              adv_min=0.22, adv_max=0.38, help="Distance from the lagoon centre to the island ring as a fraction of map width"),
        Param("ring_width", "Island ring width", "float", 0.11, min=0.09, max=0.14, step=0.01,
              adv_min=0.04, adv_max=0.24, help="Full width of the dry island arcs as a fraction of map width"),
        Param("passage_width", "Lagoon entrance width", "int", 560, min=400, max=800, step=20,
              adv_min=160, adv_max=1800, help="Minimum deep-water width of the northern and southern entrances"),
    )

    def make(self, v, seed, log=print):
        h, xx, zz, edge, rng, W = sea(v, seed)
        seabed = h.copy()
        C = W / 2
        radius = np.hypot(xx - C, zz - C)
        ring = np.abs(radius - v["ring_radius"] * W) - v["ring_width"] * W / 2
        home = ellipse_sdf(xx, zz, 0.20 * W, C, 0.085 * W, 0.16 * W)
        islands(h, edge, v, (ring, home))
        # Cut only the two entrances, retaining the natural lagoon and outer seabed between them.
        for z in (0.20 * W, 0.80 * W):
            pit(h, box_sdf(xx, zz, C, z, v["passage_width"] / 2, 0.18 * W), seabed,
                side_deg=v["beach_slope"], round_=96, toe=48)
        # Reserve an outer fleet bypass even when shallow beaches would meet the map edge.
        # Its steeper bank still remains within hover and amphibian movement limits.
        pit(h, xx - 0.035 * W, seabed, side_deg=24, round_=96, toe=48)
        # The combined ring/home SDF already rounds its flank contacts. A broad
        # seabed blur would fill the deliberately cut entrances and lagoon ports.
        d = finish(self, v, h, xx, zz, W, rng, (0.20 * W, C), (0.41 * W, C), smooth_bottom=False)
        ships = unit_masks(d.hm)["ships"]
        port = d.naval_starts[0][0]
        entrances = [(C, 0.04 * W), (C, 0.96 * W)]
        entry_ok = [connected(ships, port, point) for point in entrances]
        d.notes += [f"Lagoon connected to {name} ocean entrance: {'yes' if ok else 'NO'}"
                    for name, ok in zip(("north", "south"), entry_ok)]
        d.notes_ok &= all(entry_ok)
        channel = np.abs(xx - C) < v["passage_width"] / 2 + 180
        d.keep_clear |= channel
        d.tree_block |= channel
        d.gates = [("North lagoon entrance", channel & (zz < 0.35 * W)),
                   ("South lagoon entrance", channel & (zz > 0.65 * W))]
        d.marks += [(C, 0.37 * W, "Lagoon", (130, 210, 255))]
        return d
