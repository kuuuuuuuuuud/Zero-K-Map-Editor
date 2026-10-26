"""River Delta: a branching waterway, delta islands and several planned crossing corridors."""
import numpy as np

from ..noise import smoothstep
from ..terrain import pit, plateau, smin
from .base import Param, Template
from ._wildlands import build, common_params, described


def crossing_rows(v,W):
    return np.linspace(.24*W,.76*W,v['crossings']) if v['crossings']>1 else [.5*W]


def terrain(v,rng,fields):
    xx,zz,_,_,macro,detail=fields
    W=v['size']*512;X=xx*W;Z=zz*W
    h=(100+18*macro+4*detail).astype(np.float32)
    progress=smoothstep(.12,.88,zz)
    phase=rng.uniform(0,2*np.pi)
    reach=W*v['fan_spread']*progress*(1+.05*v['warp']*np.sin(2*np.pi*zz+phase))
    exponent=rng.uniform(.85,1.15)
    merged=None
    slope=np.tan(np.radians(14))
    # The width is measured at the waterline; banks need extra room to reach the bed.
    bed_half=v['channel_width']/2-v['channel_depth']/slope-48
    for factor in np.linspace(-1,1,v['branches']):
        factor=np.sign(factor)*abs(factor)**exponent
        field=abs(X-(W/2+factor*reach))-bed_half+24*detail
        merged=field if merged is None else smin(merged,field,160)
    pit(h,merged,-v['channel_depth'],side_deg=14,round_=96,toe=24)
    h=40+v['relief']*(h-40)
    deck=-4 if v['crossing_type']=='fords' else 30
    for z in crossing_rows(v,W):
        # Raise only the low channel cells: island interiors and banks stay intact.
        plateau(h,abs(Z-z)-v['crossing_width']/2,deck,side_deg=14,round_=96,toe=16)
    return h


class RiverDeltaTemplate(Template):
    id='river_delta'
    title='River Delta'
    modes=('1v1','team')
    tags=('land','chokes')
    players='1v1 to 4v4'
    description=('A central river fans into several channels around contested delta islands. '
                 'Cross at broad fords or raised causeways, switch between crossing fronts and use amphibious routes.')
    params=tuple(p for p in common_params('temperate') if p.key!='layout')+(
        described(Param('branches','River arms','int',3,min=3,max=5,step=1,
                        adv_min=2,adv_max=9,help='Number of distributary channels'),
                  'Sets how many river arms spread out from the upstream channel. More arms create more delta islands and more local water crossings. For example, three gives a simple fan, while five divides the delta into smaller contested pieces.'),
        described(Param('fan_spread','Delta spread','float',.30,min=.22,max=.36,step=.02,
                        adv_min=.12,adv_max=.43,help='Fraction of map width reached by the outer arms'),
                  'Sets how far the outer river arms spread from the centre, as a fraction of map width. A wide delta leaves more islands between the arms and brings water closer to the flanks. For example, 0.30 creates a broad fan while 0.22 concentrates the fighting near the middle.'),
        described(Param('channel_width','Channel width','int',500,min=350,max=750,step=50,
                        adv_min=150,adv_max=1600,help='Approximate waterline width in elmos'),
                  'Sets the approximate width of each arm at the water surface in elmos. Wider arms strengthen amphibious flanking and leave less dry island space; confluences are wider than individual arms. For example, 500 creates medium channels with room for shoreline fights.'),
        described(Param('channel_depth','Channel depth','int',36,min=20,max=70,step=2,
                        adv_min=5,adv_max=160,help='Maximum river-bed depth in elmos before Relief'),
                  'Sets the maximum channel depth in elmos below water before applying Relief. Deeper channels keep tanks on the crossing routes and make amphibious access more valuable. For example, 36 blocks ordinary tank travel through the main arms; narrow arms can be shallower than the maximum depth.'),
        described(Param('crossings','Crossing corridors','int',3,min=2,max=4,step=1,
                        adv_min=1,adv_max=7,help='Number of planned east-west crossing corridors'),
                  'Sets the number of planned crossing corridors spanning the river arms. More crossings spread the front and let armies switch between more approaches. For example, three offers northern, central and southern routes through the delta.'),
        described(Param('crossing_width','Crossing width','int',240,min=180,max=400,step=20,
                        adv_min=80,adv_max=900,help='Flat crossing core width in elmos'),
                  'Sets the flat core width of each crossing in elmos. Wide crossings are harder to seal with a few units and reduce traffic problems for large armies. For example, 240 is a medium front while 400 gives a broad approach.'),
        described(Param('crossing_type','Crossing type','choice','fords',choices=('fords','causeways'),
                        help='Shallow wading crossings or raised dry causeways'),
                  'Chooses the height of the planned crossings. Fords are shallow water routes for land armies, while causeways rise above water and provide dry connections. For example, causeways give tanks and bots dry approaches through the river arms.'),
    )

    def make(self,v,seed,log=print):
        values=dict(v,layout='ew',form='river delta')
        d=build(self,values,seed,terrain,log)
        Z=np.arange(len(d.hm),dtype=np.float32)[:,None]*8
        gates=[]
        for k,z in enumerate(crossing_rows(v,d.sym.W)):
            mask=np.broadcast_to(abs(Z-z)<v['crossing_width']/2+180,d.hm.shape).copy()
            d.keep_clear |= mask; d.tree_block |= mask
            gates.append((f'Delta crossing {k+1}',mask))
        d.gates=gates
        d.notes += [f'Planned delta crossing corridors: {v["crossings"]} ({v["crossing_type"]})']
        return d
