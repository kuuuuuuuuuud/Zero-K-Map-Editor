"""Twin Plateaus: two high team bases, several deliberate ramps and contested lowlands."""
import numpy as np

from ..biomes import BIOMES
from ..design import Design
from ..formats import west_east_boxes_lua
from ..procedural import place_resources
from ..symmetry import Symmetry, mirror_east_west
from ..terrain import box_sdf, plateau, road
from .base import Param, Template
from .common import base_terrain, biome_param, flatten_all, size_param


class TwinPlateausTemplate(Template):
    id = 'twin_plateaus'
    title = 'Twin Plateaus'
    modes = ('1v1', 'team')
    tags = ('land', 'chokes')
    players = '1v1 to 4v4, two starting pads per team'
    description = ('Each team starts on a high plateau with several deliberate ramps into a shared lowland. '
                   'Defend the home height, contest lowland metal and switch pressure between the ramps.')
    infos = {
        'plateau_height': 'Sets the height of the home plateaus in elmos above the lowland. Taller plateaus offer stronger height advantages and need longer access ramps. For example, 240 creates a substantial home height while 120 gives a gentler opening position.',
        'plateau_depth': 'Sets how far each home plateau extends from its back edge, as a fraction of map width. Deeper plateaus give teams more building space and leave less contested lowland. For example, 0.26 uses roughly a quarter of the width for each home height.',
        'ramps': 'Sets the number of planned ramps on each home plateau. More ramps spread attacks over more approaches; fewer make defence more concentrated. For example, two creates northern and southern approaches, while four adds intermediate routes.',
        'ramp_width': 'Sets the flat core width of each ramp in elmos. Wide ramps let more units fight side by side and make traffic easier for large armies. For example, 260 gives a medium approach while 420 provides a broad attack route.',
        'lowland_detail': 'Sets the height scale of lowland hills in elmos. More detail adds local cover between the plateau fronts without changing where the main ramps are. For example, zero gives a level lowland and 12 adds gentle rolling terrain.',
    }
    params = (
        size_param((12, 14, 16, 18, 20), 14, adv_smallest=8),
        biome_param('temperate'),
        Param('plateau_height', 'Plateau height', 'int', 240, min=120, max=320, step=20,
              adv_min=60, adv_max=600, help='Elmos above the lowland'),
        Param('plateau_depth', 'Plateau depth', 'float', 0.26, min=0.22, max=0.28, step=0.01,
              adv_min=0.16, adv_max=0.36, help='Fraction of map width occupied by each home plateau'),
        Param('ramps', 'Ramps per plateau', 'int', 2, min=2, max=4, step=1,
              adv_min=1, adv_max=6, help='Number of separate approaches into each home plateau'),
        Param('ramp_width', 'Ramp width', 'int', 260, min=180, max=420, step=20,
              adv_min=100, adv_max=900, help='Flat core width in elmos'),
        Param('lowland_detail', 'Lowland hills', 'int', 12, min=0, max=25, step=1,
              adv_max=70, help='Height scale of the rolling lowland in elmos'),
    )

    def make(self, v, seed, log=print):
        n=v['size']*64+1; W=v['size']*512; C=W/2
        rng=np.random.default_rng(seed)
        h,xx,zz,low,edge=base_terrain(n,rng,calm_r=1000,center_x=C,sym='ew')
        h=(100 + v['lowland_detail']*low).astype(np.float32)
        front=v['plateau_depth']*W
        top=100+v['plateau_height']
        plateau(h,box_sdf(xx,zz,front/2,C,front/2,0.32*W),top+4*low,
                side_deg=65,noise=edge,amp=22,round_=96,toe=24)
        length=v['plateau_height']/np.tan(np.radians(15))
        zs=[C] if v['ramps']==1 else np.linspace(0.29*W,0.71*W,v['ramps'])
        clear=np.zeros(h.shape,bool);gates=[]
        for k,z in enumerate(zs):
            road(h,(front-180,z),(front+length,z),v['ramp_width']/2,top,100,
                 down_deg=30,up_deg=30)
            mask=(xx>front-300)&(xx<front+length+240)&(abs(zz-z)<v['ramp_width']/2+160)
            clear |= mask | mask[:,::-1]
            gates.append((f'West ramp {k+1}',mask))
            gates.append((f'East ramp {k+1}',mask[:,::-1]))
        h=mirror_east_west(h)
        sym=Symmetry('ew',W,W)
        west=[(0.12*W,C-0.12*W),(0.12*W,C+0.12*W)]
        east=[sym.mirror(*p) for p in west]
        # Use the centre of the home height as the shared team opening economy.
        mexes,geos=place_resources(h,sym,[(0.12*W,C),(0.88*W,C)],v['size'],rng,log)
        for m in mexes[:6]:m['fixed']=True
        flatten_all(h,west+east,mexes,geos)
        h=mirror_east_west(h).astype(np.float32)
        return Design(hm=h,sym=sym,starts=west+east,teams=[west,east],mexes=mexes,geos=geos,
                      biome=dict(BIOMES[v['biome']]),title=self.title,description=self.description,
                      startboxes=west_east_boxes_lua(W,W,west,east,depth=int(0.22*W)),
                      gates=gates,keep_clear=clear,tree_block=clear,rng_state=rng.bit_generator.state,
                      notes=[f'Planned plateau ramps per team: {v["ramps"]}'])
