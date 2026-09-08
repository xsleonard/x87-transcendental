"""Fresh exponent/ratio-dispatch and table-boundary structural discriminators."""
import dataclasses
import random
from graph_v3 import Program,prevalue
from model import F,value,encode,pow2
from freeze_bank import freeze

SEED='fpatan-d0003-20260905-dispatch'


def generate():
    rng=random.Random(SEED)
    def signs(pair,kind):
        ys,ym,xs,xm=pair
        for sy in (0,32768):
            for sx in (0,32768):yield (ys|sy,ym,xs|sx,xm),kind
    for gap in range(30,51):
        for i in range(8):
            xm=rng.getrandbits(63)|(1<<63)
            for off in (-1,0,1):
                ys,ym=encode(value(16383-gap,xm)+off*pow2(-gap-63))
                yield from signs((ys,ym,16383,xm),'small-exact-and-neighbors')
            yield from signs((16383-gap,rng.getrandbits(63)|(1<<63),16383,xm),'small-inexact')
    for k in (1,2,3,15,49,63,64):
        for i in range(12):
            xm=rng.getrandbits(63)|(1<<63);ys,ym=encode(value(16383,xm)*F(k,64))
            for off in (-16,-4,-2,-1,0,1,2,4,16):
                yse,ysig=encode(value(ys,ym)+off*pow2(ys-16383-63))
                for shift in ((-1000,0,1000) if i==0 else (0,)):
                    yield from signs((yse+shift,ysig,16383+shift,xm),'table-boundary-scaled')
    # Unconditioned controls catch changes away from selected boundaries.
    for i in range(256):
        yield from signs((16383+rng.randrange(-12,4),rng.getrandbits(63)|(1<<63),
                          16383+rng.randrange(-4,4),rng.getrandbits(63)|(1<<63)),'broad-controls')


if __name__=='__main__':
    p=Program()
    freeze('d0003',SEED,generate,prevalue,p,('graph_v3.py','prepare_d0003.py'),
           {'tiny39':dataclasses.replace(p,tiny_exponent=39),
            'tiny41':dataclasses.replace(p,tiny_exponent=41),
            'direct16':dataclasses.replace(p,direct_limit=16),
            'exponent-direct':dataclasses.replace(p,direct_test='exponent')})
