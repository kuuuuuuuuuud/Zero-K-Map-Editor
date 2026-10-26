"""Lake District: separate lake basins inside a connected dry land network."""
import numpy as np

from ..noise import smoothstep
from ..terrain import ellipse_sdf, pit, smin
from .base import Param, Template
from ._wildlands import build, common_params, described


def dry_routes(xx,zz,W):
    edge=np.minimum.reduce([xx,zz,W-xx,W-zz])
    frame=1-smoothstep(0.055*W,0.115*W,edge)
    cross=np.maximum(1-smoothstep(0.025*W,0.065*W,abs(xx-W/2)),
                     1-smoothstep(0.025*W,0.065*W,abs(zz-W/2)))
    return np.maximum(frame,cross)


def terrain(v,rng,fields):
    xx,zz,x,z,macro,detail=fields
    W=v['size']*512
    base=(95+16*macro+4*detail).astype(np.float32)
    h=base.copy();merged=None
    for k in range(v['lake_basins']):
        cx=W*rng.uniform(.24,.38)
        cz=W*(.18+.64*k/max(v['lake_basins']-1,1)+rng.uniform(-.02,.02))
        rx=W*rng.uniform(.045,.075)*v['lake_scale']
        rz=W*rng.uniform(.055,.085)*v['lake_scale']
        shape=ellipse_sdf(x*W,z*W,cx,cz,rx,rz)+30*detail
        merged=shape if merged is None else smin(merged,shape,180)
    pit(h,merged,-v['lake_depth'],side_deg=14,round_=96,toe=30)
    # Wide dry axes and an outer land belt survive even if large lake basins merge.
    guard=dry_routes(xx*W,zz*W,W)
    h=h+(base-h)*guard
    return 40+v['relief']*(h-40)


class LakeDistrictTemplate(Template):
    id='lake_district'
    title='Lake District'
    modes=('1v1','team')
    tags=('land',)
    players='1v1 to 4v4'
    description=('Several seeded lake basins interrupt a connected mainland. Dry central routes and an outer land belt '
                 'keep armies moving, while amphibians can cross the lakes and raid exposed shores.')
    params=common_params('temperate')+(
        described(Param('lake_basins','Lake basins','int',3,min=2,max=5,step=1,
                        adv_min=1,adv_max=9,help='Seeded basins before team symmetry'),
                  'Sets how many lake basins are seeded before team symmetry. More basins divide the mainland into more local fronts; neighbouring lakes can merge and dry routes can divide a basin. For example, two gives a simpler lake district while five produces a denser pattern.'),
        described(Param('lake_scale','Lake size','float',1,min=.6,max=1.2,step=.1,
                        adv_min=.25,adv_max=2,help='Scale of lake footprints'),
                  'Multiplies the horizontal size of the lake basins, with 1.0 as the standard scale. Larger lakes make amphibious shortcuts more valuable and leave less open mainland. For example, 0.6 gives small local obstacles while 1.2 creates broad shorelines.'),
        described(Param('lake_depth','Lake depth','int',45,min=20,max=80,step=5,
                        adv_min=5,adv_max=180,help='Maximum lake depth in elmos before Relief'),
                  'Sets the maximum lake-floor depth below water in elmos before applying Relief. Shallow lakes allow more wading, while deep lakes strengthen amphibious routes and shoreline defence. For example, 45 keeps tanks on land approaches; broad dry routes remain available around the water.'),
    )

    def make(self,v,seed,log=print):
        d=build(self,dict(v,form='lake district'),seed,terrain,log)
        n=len(d.hm);W=d.sym.W
        z,x=np.mgrid[:n,:n].astype(np.float32)*8
        reserve=(abs(x-W/2)<.025*W)|(abs(z-W/2)<.025*W)
        reserve |= np.minimum.reduce([x,z,W-x,W-z])<.055*W
        d.keep_clear |= reserve
        d.tree_block |= reserve
        d.notes += ['Dry central axes and outer land belt reserved for land armies.']
        return d
