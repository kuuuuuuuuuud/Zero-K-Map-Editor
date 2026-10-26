"""Open Dunes: broad low sand waves, open basins and scattered rocky cover."""
import numpy as np

from ..noise import smoothstep
from .base import Param, Template
from ._wildlands import build, common_params, described


def terrain(v, rng, fields):
    _, _, x, z, macro, detail = fields
    angle = rng.uniform(0, np.pi) if v['dune_direction'] == 'seeded' else np.radians({'east': 0, 'northeast': 45, 'north': 90}[v['dune_direction']])
    along = (x*np.cos(angle) + z*np.sin(angle)) * v['size']*512
    wave = 0.5 + 0.5*np.sin(2*np.pi*along/v['wavelength'] + rng.uniform(0, 2*np.pi))
    # Wide shallow basins interrupt the crests rather than forming continuous barriers.
    crests = wave * (0.35 + 0.65*smoothstep(0.2, 0.7, macro))
    rocks = 40*v['outcrops']*smoothstep(0.68, 0.94, macro)
    return 65 + v['relief']*(v['dune_height']*crests + rocks + 8*macro) + 2*detail


class OpenDunesTemplate(Template):
    id = 'open_dunes'
    title = 'Open Dunes'
    modes = ('1v1', 'team')
    tags = ('land',)
    players = '1v1 to 4v4'
    description = ('Broad, low dune waves and open basins favour mobile armies and wide flanks. '
                   'Seeded winds and small rocky outcrops change cover without a dominant barrier.')
    params = common_params('desert') + (
        described(Param('dune_direction', 'Dune direction', 'choice', 'seeded', choices=('seeded', 'east', 'northeast', 'north'),
                        help='Wind direction for the low dune bands'),
                  'Sets the direction of the wind-shaped dune bands before team symmetry. Seeded chooses a new angle for each seed; the named directions use a fixed compass angle. For example, north aligns the bands across north-south travel and changes how armies approach each crest.'),
        described(Param('dune_height', 'Dune height', 'int', 55, min=25, max=90, step=5,
                        adv_min=10, adv_max=240, help='Low dune height scale in elmos before Relief'),
                  'Sets the dune height scale in elmos before applying Relief. Low values keep the battlefield open, while higher values create more useful cover and height advantages. For example, 55 makes gentle dunes and 25 produces an almost flat sand plain.'),
        described(Param('wavelength', 'Dune spacing', 'int', 1400, min=900, max=2200, step=100,
                        adv_min=400, adv_max=4000, help='Distance between broad dune bands in elmos'),
                  'Sets the approximate distance between dune crests in elmos before distortion. Wider spacing gives armies longer open approaches; close spacing creates more frequent changes in line of sight. For example, 1400 leaves broad manoeuvring valleys between the dunes.'),
        described(Param('outcrops', 'Rocky cover', 'float', 0.3, min=0, max=1, step=0.1,
                        adv_max=3, help='Height scale of small rocky terrain outcrops'),
                  'Scales the small rocky landforms within the sand field. These interrupt sight lines and shelter local positions without creating a map-wide wall. For example, zero removes rocky terrain, while 1.0 uses the full standard outcrop height; reclaim rocks have their own general setting.'),
    )

    def make(self, v, seed, log=print):
        return build(self, dict(v, form='open dunes'), seed, terrain, log)

