"""Procedural Watershed: seeded river graphs become braided channels, wetlands or dry ravines."""
import numpy as np
from scipy import ndimage
from scipy.interpolate import CubicSpline

from ..noise import smoothstep
from .base import Param, Template
from ._wildlands import build, common_params, described


def _course(mask, points):
    points = np.asarray(points)
    lengths = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    t = np.linspace(0, lengths[-1], max(32, int(lengths[-1] * len(mask) * 2)))
    coords = CubicSpline(lengths, points, axis=0, bc_type='natural')(t)
    grid = np.clip(np.rint(coords * (len(mask) - 1)), 0, len(mask) - 1).astype(int)
    mask[grid[:, 1], grid[:, 0]] = False


def terrain(v, rng, f):
    _, _, x, z, macro, detail = f
    n = len(x)
    channel = np.ones(x.shape, bool)
    trunk = np.stack([rng.uniform(0.25, 0.75, 6), np.linspace(0, 1, 6)], axis=1)
    _course(channel, trunk)
    for k in range(v['branches']):
        junction = trunk[int(rng.integers(1, 5))]
        mouth = np.array([float(k % 2), rng.uniform(0.03, 0.97)])
        middle = (junction + mouth) / 2 + rng.uniform(-0.12, 0.12, 2)
        _course(channel, [junction, middle, mouth])
        if v['form'] == 'braided':
            offset = np.array([0.035, 0.045]) * rng.choice((-1, 1), 2)
            _course(channel, [junction, middle + offset, mouth])
    distance = ndimage.distance_transform_edt(channel).astype(np.float32) * 8
    distance = ndimage.map_coordinates(distance, [z * (n - 1), x * (n - 1)], order=1, mode='nearest')
    distance = ndimage.gaussian_filter(distance, 3)
    width = v['channel_width']
    bank = smoothstep(width * 0.25, width * 1.75, distance)
    if v['form'] == 'ravines':
        floor = 30 + 22 * macro
        upland = 140 + 90 * macro
    elif v['form'] == 'wetlands':
        # Regional depressions broaden selected stretches into lakes without fixed lake locations.
        bank *= smoothstep(0.18, 0.50, macro)
        floor = -v['water_depth'] * (1 - 0.7 * macro)
        upland = 65 + 85 * macro
    else:
        floor = -v['water_depth'] * (1 - smoothstep(0.48, 0.75, macro))
        upland = 100 + 95 * macro
    return 40 + v['relief'] * (floor + bank * (upland - floor) - 40) + 4 * detail


class WatershedTemplate(Template):
    id = 'watershed'
    title = 'Procedural Watershed'
    modes = ('1v1', 'team')
    tags = ('land', 'chokes')
    players = '1v1 to 4v4'
    description = ('Seeded river branches carve braided channels, broad wetlands or dry ravines. '
                   'Changing the seed reshapes the drainage network; automatic crossings keep land armies connected.')
    params = common_params('temperate') + (
        described(Param('form', 'Watershed form', 'choice', 'braided', choices=('braided', 'wetlands', 'ravines'),
                        help='Choose branching river channels, lake-rich lowlands or dry ravines'),
                  'Selects how the generated drainage graph shapes the battlefield. Braided channels offer many crossings, wetlands broaden into lakes, and ravines replace water with dry valley floors. Changing this choice changes both route geometry and the role of amphibious units.'),
        described(Param('branches', 'Tributaries', 'int', 5, min=3, max=9, step=1,
                        adv_min=1, adv_max=18, help='Number of seeded tributaries connected to the main channel'),
                  'Sets how many tributaries join the generated main channel. More branches divide the land into more fronts and create more crossing decisions. For example, three gives a simpler watershed while nine creates a denser network.'),
        described(Param('channel_width', 'Channel scale', 'int', 240, min=140, max=400, step=20,
                        adv_min=60, adv_max=900, help='Channel and bank width scale in elmos'),
                  'Sets the horizontal scale of river beds and their banks in elmos. Wider channels leave less continuous high ground and give amphibious units more room. For example, 240 creates medium channels, with extra crossings carved where tanks need them.'),
        described(Param('water_depth', 'Channel depth', 'int', 12, min=0, max=40, step=2,
                        adv_max=160, help='Maximum channel depth below water in elmos before relief scaling'),
                  'Sets the deepest river floor in elmos below the water surface before relief scaling. Deeper channels favour hovers and amphibians; tank crossings are added where needed. For example, 12 allows shallow wading, while 40 requires dry or raised crossings; dry ravines ignore this setting.'),
    )

    def make(self, v, seed, log=print):
        return build(self, v, seed, terrain, log)
