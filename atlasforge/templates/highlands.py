"""Procedural Highlands: warped terrain regions become mesas, massifs or stepped uplands."""
import numpy as np

from ..noise import norm01, smoothstep, terrace
from .base import Param, Template
from ._wildlands import build, common_params, described


def terrain(v, rng, f):
    _, _, x, z, macro, detail = f
    nearest = np.full(x.shape, np.inf, np.float32)
    second = nearest.copy()
    height = np.zeros(x.shape, np.float32)
    for cx, cz, level in zip(rng.uniform(-0.12, 1.12, v['regions']),
                             rng.uniform(-0.12, 1.12, v['regions']),
                             rng.uniform(0.45, 1.0, v['regions'])):
        distance = (x - cx) ** 2 + (z - cz) ** 2
        closer = distance < nearest
        second = np.where(closer, nearest, np.minimum(second, distance))
        height = np.where(closer, level, height)
        nearest = np.minimum(nearest, distance)
    interior = smoothstep(0.005, 0.11, np.sqrt(second) - np.sqrt(nearest))
    if v['form'] == 'mesas':
        elevation = 35 * macro + 180 * height * interior
    elif v['form'] == 'massifs':
        elevation = 30 * macro + 230 * height * np.exp(-nearest / 0.032)
    else:
        elevation = 210 * terrace(norm01(0.6 * macro + 0.4 * height * interior),
                                  v['steps'], sharp=0.20, rng=rng, units=v['size'])
    return 50 + v['relief'] * elevation + 5 * detail


class HighlandsTemplate(Template):
    id = 'highlands'
    title = 'Procedural Highlands'
    modes = ('1v1', 'team')
    tags = ('land',)
    players = '1v1 to 4v4'
    description = ('Seeded highland regions become irregular mesas, rounded massifs or stepped uplands. '
                   'Valleys, expansion sites and automatically carved tank ramps change with every seed.')
    params = common_params('temperate') + (
        described(Param('form', 'Highland form', 'choice', 'mesas', choices=('mesas', 'massifs', 'terraces'),
                        help='Choose isolated uplands, rounded mountain groups or stepped terrain'),
                  'Selects the formula used to turn terrain regions into high ground. Mesas favour raised interiors and valley borders, massifs form rounded mountain groups, and terraces create elevation steps. The same seed produces a different battlefield when this choice changes.'),
        described(Param('regions', 'Terrain regions', 'int', 12, min=6, max=20, step=1,
                        adv_min=3, adv_max=36, help='Number of seeded highland regions before symmetry'),
                  'Sets how many terrain centres compete for space across the map. More regions usually produce smaller highlands and a denser valley network. For example, six gives broad formations while twenty breaks the landscape into smaller areas.'),
        described(Param('steps', 'Terrace levels', 'int', 4, min=3, max=6, step=1,
                        adv_min=2, adv_max=10, help='Number of elevation levels in the terraces form'),
                  'Sets the number of elevation levels used by the terraces form. More levels create smaller height steps; fewer levels create larger upland shelves. For example, four gives four principal elevation bands, and this setting does not affect mesas or massifs.'),
    )

    def make(self, v, seed, log=print):
        return build(self, v, seed, terrain, log)
