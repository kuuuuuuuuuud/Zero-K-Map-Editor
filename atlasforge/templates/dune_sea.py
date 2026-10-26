"""Procedural Dune Sea: domain-warped wind ridges, crescent fields and intersecting star dunes."""
import numpy as np

from ..noise import smoothstep
from .base import Param, Template
from ._wildlands import build, common_params, described


def terrain(v, rng, f):
    _, _, x, z, macro, detail = f
    theta = float(rng.uniform(0, np.pi))
    phase = float(rng.uniform(0, 2 * np.pi))
    frequency = v['dune_bands']
    u = x * np.cos(theta) + z * np.sin(theta)
    ridge = (0.5 + 0.5 * np.cos(2 * np.pi * frequency * u + phase)) ** 1.4
    if v['form'] == 'crescents':
        across = -x * np.sin(theta) + z * np.cos(theta)
        ridge = (0.5 + 0.5 * np.cos(2 * np.pi * frequency * u + 3 * np.sin(8 * across) + phase)) ** 2
        ridge *= smoothstep(0.12, 0.72, macro)
    elif v['form'] == 'star dunes':
        second = x * np.cos(theta + 1.15) + z * np.sin(theta + 1.15)
        other = (0.5 + 0.5 * np.cos(2 * np.pi * frequency * second - phase)) ** 1.4
        ridge = 0.5 * (ridge + other) + 0.25 * ridge * other
    sand = v['dune_height'] * ridge * (0.5 + 0.5 * macro)
    # Seeded rocky uplands interrupt the dune fields instead of placing fixed mountains.
    rock = v['rockiness'] * 130 * smoothstep(0.58, 0.92, macro)
    return 40 + v['relief'] * (sand + rock + 20 * macro) + 3 * detail


class DuneSeaTemplate(Template):
    id = 'dune_sea'
    title = 'Procedural Dune Sea'
    modes = ('1v1', 'team')
    tags = ('land',)
    players = '1v1 to 4v4'
    description = ('Changing winds and warped noise create long dune chains, crescent fields or intersecting star dunes. '
                   'Seeded rocky uplands interrupt the sand; tanks receive natural valleys and automatic ramps.')
    params = common_params('desert') + (
        described(Param('form', 'Dune form', 'choice', 'longitudinal', choices=('longitudinal', 'crescents', 'star dunes'),
                        help='Choose long wind ridges, broken crescent fields or intersecting dunes'),
                  'Selects the wind pattern used to build the dunes. Longitudinal dunes form continuous ridges, crescents break into curved patches, and star dunes intersect several ridge directions. Each choice generates different manoeuvring routes rather than changing only the colours.'),
        described(Param('dune_bands', 'Dune bands', 'int', 5, min=3, max=9, step=1,
                        adv_min=1, adv_max=18, help='Approximate number of dune wave bands across the map'),
                  'Sets the approximate number of wind-shaped dune bands before distortion and symmetry. More bands create narrower crests and more frequent valleys. For example, three gives broad dune chains while nine produces closely spaced formations.'),
        described(Param('dune_height', 'Dune height', 'int', 110, min=60, max=180, step=10,
                        adv_min=20, adv_max=400, help='Dune crest height scale in elmos before relief scaling'),
                  'Sets the dune crest height scale in elmos before applying Relief. Taller dunes offer stronger height advantages and can require additional tank ramps. For example, 110 creates medium crests while 60 keeps the sand more open.'),
        described(Param('rockiness', 'Rocky uplands', 'float', 0.6, min=0.0, max=1.2, step=0.1,
                        adv_max=3.0, help='Scales the seeded rocky highlands among the dunes'),
                  'Scales the height of noise-selected rocky uplands that interrupt the dune fields. More rock creates sheltered pockets and stronger defensive terrain. For example, zero leaves a pure sand landscape while 1.0 uses the full standard rocky elevation.'),
    )

    def make(self, v, seed, log=print):
        return build(self, v, seed, terrain, log)
