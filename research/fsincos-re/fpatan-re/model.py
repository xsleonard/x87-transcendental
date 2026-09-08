"""Analysis-only exact-rational FPATAN schedule family, NOT a solved model.

Constants come from the public physically decoded P5 ROM. Every explicit cut
is exact integer arithmetic. Operation policies are global hardware hypotheses,
not operand exception rules. No captures or external library atan are used.
"""
import csv
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pow2(e):
    return F(1 << e) if e >= 0 else F(1, 1 << -e)


def value(se, sig):
    if (se & 0x7fff) == 0x7fff:
        raise ValueError('special value outside finite candidate')
    return (-1 if se & 0x8000 else 1) * sig * pow2(max(se & 0x7fff, 1)-16383-63)


def exponent(v):
    v = abs(v); n, d = v.numerator, v.denominator
    e = n.bit_length()-d.bit_length()
    return e - int(v < pow2(e))


def quantize(v, bits=64, mode='rn'):
    if not v or mode == 'exact': return v
    sign = -1 if v < 0 else 1
    step = pow2(exponent(v)-bits+1)
    z = abs(v)/step; q, r = divmod(z.numerator, z.denominator)
    up = (mode == 'rn' and (2*r > z.denominator or (2*r == z.denominator and q & 1)))
    up |= bool(r) and (mode == 'away' or (mode == 'rd' and sign < 0) or (mode == 'ru' and sign > 0))
    return sign * (q + up) * step


def cut(v, spec):
    if spec == 'exact': return v
    for mode in ('chop','away','rn','rd','ru'):
        if spec.startswith(mode): return quantize(v,int(spec[len(mode):]),mode)
    raise ValueError(spec)


def encode(v, mode='rn', zero_sign=0):
    if not v: return (zero_sign << 15, 0)
    sign = int(v < 0); mag = abs(v)
    e = max(exponent(mag), -16382); step = pow2(e-63)
    z = mag/step; q,r = divmod(z.numerator,z.denominator)
    up = mode == 'rn' and (2*r > z.denominator or (2*r == z.denominator and q & 1))
    up |= bool(r) and ((mode=='rd' and sign) or (mode=='ru' and not sign))
    q += up
    if q >= 1 << 64: q >>= 1; e += 1
    if e > 16383: raise OverflowError('finite encoder overflow')
    return ((sign << 15) | (0 if q < 1 << 63 else e+16383), q)


def constants():
    with (ROOT/'data/pentium-rom/rom-constants.tsv').open() as f:
        rows = list(csv.DictReader(f,delimiter='\t'))
    result = {}
    for r in rows:
        i = int(r['row'])
        if i in (19,20,21) or 114 <= i <= 123 or 125 <= i <= 156:
            result[i] = (-1 if r['sign']=='1' else 1)*int(r['sig68'],16)*pow2(int(r['exp'],16)-65535-66)
    return result


ROM = constants()


@dataclass(frozen=True)
class Policy:
    mul: str = 'chop67'
    add: str = 'rn64'
    sub: str = 'chop67'
    div: str = 'chop67'
    initial_div: str = 'exact'
    reduction: str = 'pair'
    denominator: str = 'rn64'
    polynomial: str = 'long'
    direct_limit: int = 64
    tail: str = 'chop67'
    combine: str = 'exact'
    rotate: str = 'exact'
    table: str = 'exact'


def prevalue(ys,ym,xs,xm,p=Policy()):
    y,x = abs(value(ys,ym)),abs(value(xs,xm))
    if not y or not x: raise ValueError('zero outside finite discovery model')
    swap = y > x
    if swap: y,x = x,y
    ratio = cut(y/x,p.initial_div)
    # Candidate branch/table rule, not yet a recovered silicon fact.
    if ratio < F(1,p.direct_limit): n = 0
    else:
        q,r = divmod((ratio*32).numerator,(ratio*32).denominator)
        n = q + int(2*r >= (ratio*32).denominator)
    c = F(n,32)
    if n == 0: z = cut(y/x,p.div)
    elif p.reduction == 'pair':
        numerator = cut(y-cut(c*x,p.mul),p.sub)
        denominator = cut(x+cut(c*y,p.mul),p.denominator)
        z = cut(numerator/denominator,p.div)
    elif p.reduction == 'ratio':
        z = cut(cut(ratio-c,p.sub)/cut(1+cut(c*ratio,p.mul),p.denominator),p.div)
    else: raise ValueError(p.reduction)
    coeffs = [ROM[i] for i in (range(118,124) if p.polynomial=='long' else range(114,118))]
    square = cut(z*z,p.mul)
    h = coeffs[-1]
    for a in reversed(coeffs[:-1]): h = cut(a+cut(square*h,p.mul),p.add)
    tail = cut(cut(square*h,p.mul)*z,p.tail)
    a = cut(z+tail,p.combine)
    if n: a = cut(cut(ROM[124+n],p.table)+a,p.combine)
    if swap: a = cut(ROM[20]-a,p.rotate)
    if xs & 0x8000: a = cut(ROM[19]-a,p.rotate)
    return -a if ys & 0x8000 else a


def predict(row,p=Policy()):
    _,rc,pc,ys,ym,xs,xm = row.split()
    return encode(prevalue(int(ys,16),int(ym,16),int(xs,16),int(xm,16),p),rc)


def selftest():
    assert value(0x3fff,1<<63)==1
    assert value(0x8000,1)==-pow2(-16445)
    for mode in ('rn','rd','ru','rz'):
        for s in (0,1):
            for e,m in ((0,1),(0,(1<<63)-1),(1,1<<63),(0x3fff,1<<63),(0x7ffe,(1<<64)-1)):
                assert encode(value(e|(s<<15),m),mode)==(e|(s<<15),m)
    assert quantize(F(9,8),3,'rn')==1
    assert quantize(F(11,8),3,'rn')==F(3,2)
    assert quantize(-F(9,8),3,'rd')==-F(5,4)
    assert encode(F(1,2)*pow2(-16445),'rn')==(0,0)
    assert encode(F(1,2)*pow2(-16445),'ru')==(0,1)
    print('PASS exact arithmetic selftest')


if __name__=='__main__': selftest()
