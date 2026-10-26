"""Fjord Coast: deeply indented mirrored mainlands with sheltered fleet inlets."""
import numpy as np

from ..checks import connected,unit_masks
from ..terrain import ellipse_sdf,smax,smin
from .base import Param,Template
from ._naval import finish,islands,naval_params,sea


def bay_centres(v,W):
    north=(v['fjords']+1)//2; south=v['fjords']//2
    a=np.linspace(.12*W,.32*W,north) if north>1 else [.22*W]
    b=np.linspace(.68*W,.88*W,south) if south>1 else ([.78*W] if south else [])
    return list(a)+list(b)


class FjordCoastTemplate(Template):
    id='fjord_coast'
    title='Fjord Coast'
    modes=('1v1','team')
    tags=('sea','chokes')
    players='1v1 to 4v4'
    description=('Deep inlets cut into opposing mainlands and shelter local fleet approaches. '
                 'Hold the bay mouths, raid the inner shores and use amphibious landings behind the headlands.')
    infos={
        'fjords': 'Sets the number of seeded inlets along each coast. More inlets create more sheltered landing fronts, and nearby mouths can merge around intervening headlands. For example, two gives separate northern and southern bays while four makes a more intricate coast.',
        'fjord_reach': 'Sets how far the inlets reach into the mainland at the waterline, approximately in elmos. Deep inlets bring ships close to inland expansion areas and make headlands valuable defensive positions. For example, 900 creates substantial coastal raids while 600 keeps a broader mainland.',
        'fjord_width': 'Sets the approximate waterline width of an inlet in elmos. Wider mouths let fleets manoeuvre and make bay blockades harder; narrow mouths shelter local defences. For example, 1000 provides a medium bay and 800 makes a tighter approach.',
        'coast_depth': 'Sets how far the mainland extends from the back edge before the beach, as a fraction of map width. More mainland leaves more building space but narrows the shared sea. For example, 0.28 gives broad home territory, while 0.24 makes the open fleet front wider.',
    }
    params=naval_params()+(
        Param('fjords','Coastal inlets','int',2,min=2,max=4,step=1,
              adv_min=1,adv_max=7,help='Number of seeded inlets on each coast'),
        Param('fjord_reach','Inlet reach','int',900,min=600,max=1200,step=100,
              adv_min=250,adv_max=2200,help='Approximate inland reach at water level in elmos'),
        Param('fjord_width','Inlet width','int',1000,min=800,max=1400,step=100,
              adv_min=400,adv_max=2400,help='Approximate inlet width at water level in elmos'),
        Param('coast_depth','Mainland depth','float',.28,min=.24,max=.30,step=.01,
              adv_min=.18,adv_max=.38,help='Fraction of map width before the beach'),
    )

    def make(self,v,seed,log=print):
        h,xx,zz,edge,rng,W=sea(v,seed)
        shore=100/np.tan(np.radians(v['beach_slope']))+48
        coast_x=v['coast_depth']*W
        holes=None;centres=[]
        for z in bay_centres(v,W):
            z=float(np.clip(z+rng.uniform(-.015,.015)*W,.07*W,.93*W))
            centres.append(z)
            shape=ellipse_sdf(xx,zz,coast_x,z,v['fjord_reach']+shore,v['fjord_width']/2+shore)
            holes=shape if holes is None else smin(holes,shape,220)
        mainland=smax(xx-coast_x,-holes,260)
        # Keep the home headland between the inlet groups. An additional raised
        # ellipse would extend its submerged flank back into the adjacent fjords.
        islands(h,edge,v,(mainland,))
        base=(.105*W,.5*W)
        run=165/np.tan(np.radians(v['beach_slope']))+v['coast_noise']+96
        port=(min(.46*W,coast_x+run),.5*W)
        d=finish(self,v,h,xx,zz,W,rng,base,port)
        ships=unit_masks(d.hm)['ships']
        access=[]
        gates=[]
        for k,z in enumerate(centres):
            point=(float(np.clip(coast_x-.4*v['fjord_reach'],.04*W,.46*W)),z)
            reachable=connected(ships,port,point)
            access.append(reachable)
            d.marks += [(point[0],point[1],f'Fjord {k+1}',(110,200,255)),
                        (*d.sym.mirror(*point),f'Fjord {k+1}',(110,200,255))]
            mask=(abs(xx-coast_x)<v['fjord_width']/2+150)&(abs(zz-z)<v['fjord_width']/2+150)
            gates += [(f'West inlet {k+1}',mask),(f'East inlet {k+1}',mask[:,::-1])]
        d.gates=gates
        for _,mask in gates:d.keep_clear |= mask;d.tree_block |= mask
        d.notes += [f'Fleet access to seeded inlet {k+1}: {"yes" if ok else "NO"}' for k,ok in enumerate(access)]
        d.notes_ok &= all(access)
        return d
