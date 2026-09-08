"""Independent balanced finite pairs with arbitrary low bits, no labels."""
import random
from model import F,pow2,value,encode
from freeze_stream import freeze

SEED='fpatan-d0008-20260905-balanced-wide'
PAIRS=262144


def generate():
    rng=random.Random(SEED)
    for i in range(PAIRS):
        family=i%8;xm=rng.getrandbits(63)|(1<<63);xs=16383
        x=value(xs,xm);u=F(rng.getrandbits(64)+1,(1<<64)+1)
        if family==0:
            n=2+(i//8)%31;lo=F(2*n-1,64);hi=min(F(1),F(2*n+1,64))
            ys,ym=encode(x*(lo+(hi-lo)*u));kind='balanced-table-cells'
        elif family==1:
            ys,ym=encode(x*u*F(3,64));kind='direct-uniform'
        elif family==2:
            ys=16383-rng.randrange(5,40);ym=rng.getrandbits(63)|(1<<63);kind='direct-logarithmic'
        elif family==3:
            xs=rng.randrange(257,32510);ys=xs+rng.randrange(-256,257)
            ym=rng.getrandbits(63)|(1<<63);kind='wide-exponent-gap'
        elif family==4:
            k=rng.randrange(1,65);ys,ym=encode(x*F(k,64))
            ys,ym=encode(value(ys,ym)+rng.randrange(-4096,4097)*pow2(ys-16383-63));kind='midpoint-4096-neighborhood'
        elif family==5:
            n=rng.randrange(2,33);r=F(n,32)+rng.choice((-1,1))*u*pow2(-rng.randrange(8,100))
            ys,ym=encode(x*r);kind='reduction-cancellation'
        elif family==6:
            ys,ym=encode(x+rng.choice((-1,1))*rng.randrange(1,1<<20)*pow2(-63));kind='near-equal-low-bits'
        else:
            xs=rng.randrange(1,32767);ys=rng.randrange(1,32767)
            ym=rng.getrandbits(63)|(1<<63);kind='full-exponent-independent'
        if family in (0,1,2,4,5,6):
            shift=rng.randrange(-16000,16001);ys+=shift;xs+=shift
        if rng.getrandbits(1):ys,ym,xs,xm=xs,xm,ys,ym
        ys|=rng.getrandbits(1)<<15;xs|=rng.getrandbits(1)<<15
        yield (ys,ym,xs,xm),kind


if __name__=='__main__':freeze('d0008',SEED,generate,('prepare_d0008.py',))
