"""Fresh discriminators for pre-rounding underflow detection.

Construct exact minimum-normal ratio preimages and nearby quotients at many
common scales, rather than selecting previously observed failing operands.
Additional minimum-subnormal and pseudo-denormal priority controls are fresh.
"""
import random
from architecture import POLICY,predict
from freeze_bank import freeze
from model import F,value,pow2,encode

SEED='fpatan-d0007-20260905-preround-tininess'


def generate():
    rng=random.Random(SEED)
    def sym(ys,ym,xs,xm,kind):
        for sy in (0,32768):
            for sx in (0,32768):yield (ys|sy,ym,xs|sx,xm),kind
    for _ in range(96):
        xm=rng.getrandbits(63)|(1<<63)
        for shift in (0,rng.randrange(1,16001)):
            for off in (-4,-2,-1,0,1,2,4):
                ys,ym=encode(value(1+shift,xm)+off*pow2(-16445+shift))
                yield from sym(ys,ym,16383+shift,xm,'scaled-minimum-normal-ratio')
    for _ in range(64):
        ym=rng.getrandbits(63) or 1
        for multiple in (1,2,3,4,8):
            xs,xm=encode(F(2*ym,multiple))
            for off in (-1,0,1):
                se,sig=encode(value(xs,xm)+off*pow2(xs-16383-63))
                yield from sym(0,ym,se,sig,'subnormal-rounding-lattice')
    for _ in range(32):
        m=rng.getrandbits(63)|(1<<63)
        for e in (0,1):
            for xs,xm in ((0,0),(32767,1<<63),(0,rng.getrandbits(63)|(1<<63))):
                yield from sym(e,m,xs,xm,'denormal-assist-control')


if __name__=='__main__':
    freeze('d0007',SEED,generate,None,POLICY,
        ('architecture.py','graph_v3.py','graph_v4.py','prepare_d0007.py','fpatan_candidate.c'),
        encoding_predictor=predict,mathematical_oracle=False,all_pc=True)
