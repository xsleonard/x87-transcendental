"""Prospective DE correction and output-underflow-boundary adversaries.

Probe the numerical/encoding distinction of pseudo-denormals and the point
at which a rounded result crosses minimum normal or zero. Every tuple is
fresh and covers all four RC and three PC settings. No labels are inspected.
"""
import random
from architecture import POLICY,predict
from freeze_bank import freeze
from model import encode,F,pow2,value

SEED='fpatan-d0006-20260905-exception-boundaries'


def generate():
    rng=random.Random(SEED)
    def sym(pair,kind):
        ys,ym,xs,xm=pair
        for sy in (0,32768):
            for sx in (0,32768):
                yield (ys|sy,ym,xs|sx,xm),kind
                yield (xs|sx,xm,ys|sy,ym),kind+'-swapped'
    for _ in range(24):
        xm=rng.getrandbits(63)|(1<<63)
        for off in (-2,-1,0,1,2):
            se,sig=encode(value(1,xm)+off*pow2(-16445))
            yield from sym((se,sig,16383,xm),'minimum-normal-output')
        ym=rng.getrandbits(63) or 1;xse,xsig=encode(F(ym*2))
        for off in (-2,-1,0,1,2):
            se,sig=encode(value(xse,xsig)+off*pow2(xse-16383-63))
            yield from sym((0,ym,se,sig),'zero-half-ulp-output')
    for _ in range(24):
        ym=rng.getrandbits(63)|(1<<63);payload=rng.getrandbits(62) or 1
        controls=((0,0),(32767,1<<63),(0,rng.getrandbits(63) or 1),
                  (0,rng.getrandbits(63)|(1<<63)),
                  (rng.randrange(1,32767),rng.getrandbits(63)|(1<<63)),
                  (32767,(1<<63)|payload),(32767,(3<<62)|payload),
                  (rng.randrange(1,32767),rng.getrandbits(63) or 1))
        for xse,xsig in controls:
            yield from sym((0,ym,xse,xsig),'pseudo-denormal-priority')
            # Same value, canonical normal encoding, independently fresh tuple.
            yield from sym((1,ym,xse,xsig),'canonical-normal-control')


if __name__=='__main__':
    freeze('d0006',SEED,generate,None,POLICY,
        ('architecture.py','graph_v3.py','graph_v4.py','prepare_d0006.py','fpatan_candidate.c'),
        encoding_predictor=predict,mathematical_oracle=False,all_pc=True)
