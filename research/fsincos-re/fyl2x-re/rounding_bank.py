"""Source-model inverse construction of unseen rounding/exception boundaries.

Targets are arithmetic rounding surfaces, never saved hardware mismatches.
The existing preparation driver still applies all local history exclusions.
"""
import random
from model import F, pow2, value, encode, logarithm, classify


def generate(seed, size):
    r=random.Random(seed)
    def target_neighbors(op,x,target,kind):
        xs,xm=encode(x);x=value(xs,xm);g=logarithm(op,x)
        if not g:return
        for sign in (-1,1):
            ys,ym=encode(sign*target/g)
            if classify(ys,ym) not in ('normal','denormal'):continue
            step=pow2(max(ys&0x7fff,1)-16383-63)
            for k in (-3,-2,-1,0,1,2,3):
                y=value(ys,ym)+k*step
                sy,sm=encode(y)
                if classify(sy,sm) not in ('normal','denormal'):continue
                yield op,(sy,sm,xs,xm),kind
    for i in range(size):
        op='fyl2x' if i%2 else 'fyl2xp1'
        eps=F(r.randrange(-(1<<62),1<<62),1<<64)
        if op=='fyl2x':
            x=1+eps if i%4==1 else ((1<<63)|r.getrandbits(63))*pow2(r.randrange(-1000,1001)-63)
        else:x=eps
        targets=(pow2(-16382),pow2(-16446),F(3)*pow2(-16446),pow2(-16445),
                 F((1<<64)-1,2)*pow2(-16382-63),
                 F((1<<64)|r.getrandbits(64))*pow2(-64))
        target=targets[(i//2)%len(targets)]
        kind='underflow-rounding-surfaces' if (i//2)%len(targets)<5 else 'normal-halfway-surfaces'
        yield from target_neighbors(op,x,target,kind)
        if op=='fyl2x':
            x=((1<<63)|r.getrandbits(63))*pow2(r.randrange(2,16384)-63)
            for target in (pow2(16384)-pow2(16319),pow2(16384),pow2(16384)-pow2(16320)):
                yield from target_neighbors(op,x,target,'overflow-rounding-surfaces')
    for sign in (-1,1):
        for e in range(-74,-62):
            for k in range(48):
                x=sign*((1<<63)|r.getrandbits(63))*pow2(e-63)
                target=F(((1<<63)|r.getrandbits(63))*2+1,1<<64)
                yield from target_neighbors('fyl2xp1',x,target,'tiny-halfway-surfaces')
    # Adjacent raw80 values at the exact documented FYL2XP1 endpoint.
    for sign in (0,0x8000):
        for delta in range(-32,1):
            for k in range(16):
                y=(16383+r.randrange(-20,21))|(r.randrange(2)<<15)
                yield 'fyl2xp1',(y,(1<<63)|r.getrandbits(63),0x3ffd|sign,0x95f619980c4336f7+delta),'documented-p1-endpoints'
    for e in (-8192,-128,-32,-16,-8,-4,-2,-1,1,2,4,8,16,32,128,8192):
        for k in range(64):
            ys=r.choice((0,1,2,3,4))|(r.randrange(2)<<15)
            ym=r.getrandbits(63)|1
            if ys&0x7fff:ym|=1<<63
            yield 'fyl2x',(ys,ym,16383+e,1<<63),'exact-subnormal-products'
    for k in range(512):
        xs=r.choice((0,1,2,3))|(r.randrange(2)<<15)
        xm=r.getrandbits(63)|1
        if xs&0x7fff:xm|=1<<63
        ys=(16383+r.choice((-2,-1,0,1,2)))|(r.randrange(2)<<15)
        yield 'fyl2xp1',(ys,1<<63,xs,xm),'exact-subnormal-products'
    # Equal NaN payloads with opposite signs and mixed quiet/signaling classes
    # discriminate tie priority without reusing any old significand pair.
    for op in ('fyl2x','fyl2xp1'):
        for k in range(128):
            payload=r.getrandbits(62)|1
            for sy in (0,0x8000):
                for sx in (0,0x8000):
                    for qy in (0,1):
                        for qx in (0,1):
                            yield op,(0x7fff|sy,(1<<63)|(qy<<62)|payload,0x7fff|sx,(1<<63)|(qx<<62)|payload),'nan-equal-payload'
