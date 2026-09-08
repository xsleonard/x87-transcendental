"""Final prospective logarithm challenge: independent strata plus boundaries.

The first two blocks below use only raw80 encodings and Intel's input bound;
they do not import model arithmetic to select operands. The later boundary
block is explicitly model-guided, as recorded in its own generator.
"""
import random


def generate(seed,size):
    r=random.Random(seed)
    maximum=0x95f619980c4336f7
    for i in range(size*2):
        op=('fyl2x','fyl2xp1')[i%2]
        ys=r.randrange(0,0x7fff)|(r.randrange(2)<<15)
        ym=r.getrandbits(64)|1
        if ys&0x7fff:ym|=1<<63
        if op=='fyl2x':
            xs=r.randrange(0,0x7fff);xm=r.getrandbits(64)|1
            if xs:xm|=1<<63
        else:
            xs=r.randrange(0,0x3ffe);xm=r.getrandbits(64)|1
            if xs:xm|=1<<63
            if xs==0x3ffd:xm=(1<<63)+r.randrange(maximum-(1<<63)+1)
            xs|=r.randrange(2)<<15
        yield op,(ys,ym,xs,xm),'independent-raw-exponent-strata'
    for i in range(size):
        xs=0x3ffd|(r.randrange(2)<<15)
        xm=(1<<63)+r.randrange(maximum-(1<<63)+1)
        ys=(16383+r.randrange(-100,101))|(r.randrange(2)<<15)
        ym=(1<<63)|r.getrandbits(63)
        yield 'fyl2xp1',(ys,ym,xs,xm),'independent-upper-p1-interval'
    from prepare_challenge import generate as broad
    from rounding_bank import generate as boundaries
    yield from broad(seed+'-broad',size)
    yield from boundaries(seed+'-boundaries',384)
