"""Fresh prospective challenge for the role-specific finite V4 graph.

Every ROM center/midpoint, both octant orders and all quadrants, full exponent
scales, fresh random ratios, and tiny/subnormal paths. Predictions and four
structural alternatives are frozen before a single hardware label is read.
"""
import dataclasses
import random
from graph_v4 import PROGRAM,prevalue
from model import F,value,encode,pow2
from freeze_bank import freeze

SEED='fpatan-d0004-20260905-intermediate-sums'


def generate():
    rng=random.Random(SEED)
    def symmetries(pair,kind):
        ys,ym,xs,xm=pair
        for sy in (0,32768):
            for sx in (0,32768):
                yield (ys|sy,ym,xs|sx,xm),kind
                yield (xs|sx,xm,ys|sy,ym),kind+'-swapped'
    for k in range(1,65):
        for _ in range(3):
            xm=rng.getrandbits(63)|(1<<63);ys,ym=encode(value(16383,xm)*F(k,64))
            shift=rng.choice((-16000,-1000,0,1000,16000))
            for off in (-8,-2,-1,0,1,2,8):
                se,sig=encode(value(ys,ym)+off*pow2(ys-16383-63))
                yield from symmetries((se+shift,sig,16383+shift,xm),'all-ROM-centers-midpoints')
    for gap in (38,39,40,41,42,64,16400):
        for _ in range(8):
            xm=rng.getrandbits(63)|(1<<63)
            # The full exponent-gap probe may have a true subnormal numerator.
            for off in (-1,0,1):
                v=value(16383,xm)*pow2(-gap)+off*pow2(max(-gap-63,-16445))
                se,sig=encode(v)
                yield from symmetries((se,sig,16383,xm),'small-divider-boundaries')
    for _ in range(512):
        xe=rng.randrange(1,32767);ye=max(1,min(32766,xe+rng.randrange(-80,81)))
        yield from symmetries((ye,rng.getrandbits(63)|(1<<63),xe,rng.getrandbits(63)|(1<<63)),'full-exponent-random')
    for _ in range(128):
        ys,xs=rng.choice(((0,0),(0,1),(1,0)))
        ym=(rng.getrandbits(63) or 1)|((1<<63) if ys else 0)
        xm=(rng.getrandbits(63) or 1)|((1<<63) if xs else 0)
        yield from symmetries((ys,ym,xs,xm),'subnormal-pairs')


if __name__=='__main__':
    freeze('d0004',SEED,generate,prevalue,PROGRAM,
        ('graph_v3.py','graph_v4.py','prepare_d0004.py','fpatan_candidate.c'),
        {'old-direct32':dataclasses.replace(PROGRAM,direct_numerator=1,direct_limit=32),
         'uncut-table-kernel':dataclasses.replace(PROGRAM,table_kernel_cut='exact'),
         'RN64-index':dataclasses.replace(PROGRAM,index_read='rn64'),
         'exact-denominator':dataclasses.replace(PROGRAM,denominator='exact')})
