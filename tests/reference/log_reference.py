"""Exact-rational logarithm reference and source-analysis policy family.

Literal constants: Ken Shirriff's public P5 ROM decode (2025). Operation
order: hypothesis transferred from the pinned public Goldmont listing.
Rounding policies are global operation classes, never operand patches.
No hardware outputs or mathematical log implementation are consulted.
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
        raise ValueError('nonfinite discovery input')
    return (-1 if se & 0x8000 else 1) * sig * pow2(max(se & 0x7fff, 1)-16383-63)


def exponent(v):
    v = abs(v)
    e = v.numerator.bit_length()-v.denominator.bit_length()
    return e-int(v < pow2(e))


def quantize(v, bits=64, mode='rn'):
    if not v or mode == 'exact':
        return v
    sign = -1 if v < 0 else 1
    step = pow2(exponent(v)-bits+1)
    z = abs(v)/step; q,r = divmod(z.numerator,z.denominator)
    up = mode == 'rn' and (2*r > z.denominator or (2*r == z.denominator and q & 1))
    up |= bool(r) and (mode == 'away' or (mode == 'rd' and sign < 0) or (mode == 'ru' and sign > 0))
    return sign*(q+up)*step


def cut(v, spec):
    if spec == 'exact':
        return v
    for mode in ('chop','away','rn','rd','ru'):
        if spec.startswith(mode):
            return quantize(v,int(spec[len(mode):]),mode)
    raise ValueError(spec)


def encode(v, mode='rn', zero_sign=0):
    if not v:
        return zero_sign << 15, 0
    sign = int(v < 0)
    e = max(exponent(v),-16382); step = pow2(e-63)
    z = abs(v)/step; q,r = divmod(z.numerator,z.denominator)
    up = mode == 'rn' and (2*r > z.denominator or (2*r == z.denominator and q & 1))
    up |= bool(r) and ((mode == 'rd' and sign) or (mode == 'ru' and not sign))
    q += up
    if q >= 1 << 64:
        q >>= 1; e += 1
    if e > 16383:
        inf = mode == 'rn' or (mode == 'rd' and sign) or (mode == 'ru' and not sign)
        return (sign << 15) | (0x7fff if inf else 0x7ffe), (1 << 63) if inf else (1 << 64)-1
    return (sign << 15) | (0 if q < 1 << 63 else e+16383), q


def constants():
    with (ROOT/'data/pentium-rom/rom-constants.tsv').open() as f:
        rows = list(csv.DictReader(f,delimiter='\t'))
    # These four transcription corrections are derived independently from
    # log2(1+n/64), and their upper 64 bits agree with the public Goldmont ROM.
    # The original public TSV stays intact. No operand/output table is used.
    corrections = {207:'43ace27e8a8000000',245:'6f66cc899b64b03f7',
                   259:'5c813d56efe4338fe',268:'4a83eb6e0f93f7a44'}
    return {int(r['row']):(-1 if r['sign']=='1' else 1)*int(corrections.get(int(r['row']),r['sig68']),16)*pow2(int(r['exp'],16)-65535-66)
            for r in rows if 193 <= int(r['row']) <= 269}


ROM = constants()


@dataclass(frozen=True)
class Policy:
    mul: str = 'chop67'
    add: str = 'rn64'
    wide: str = 'chop67'
    direct_div: str = 'chop67'
    table_div: str = 'rn64'
    square: str = 'paired'
    table_denominator: str = 'rn64'
    direct_limit: bool = True


def logarithm(op, x, p=Policy()):
    M = lambda a,b: cut(a*b,p.mul)
    A = lambda a,b: cut(a+b,p.add)
    W = lambda a,b: cut(a+b,p.wide)
    if op == 'fyl2xp1' and abs(x) > F(1,8):
        return logarithm('fyl2x',W(x,F(1)),p)
    if op == 'fyl2xp1' or (p.direct_limit and F(7,8) <= x <= F(9,8)):
        delta = x if op == 'fyl2xp1' else A(x,-F(1))
        if not delta:
            return F(0)
        if op == 'fyl2xp1' and exponent(delta) <= -70:
            return M(ROM[195],delta)
        denominator = W(x,F(2) if op == 'fyl2xp1' else F(1))
        z = cut(M(ROM[196],delta)/denominator,p.direct_div)
        u = quantize(z*quantize(z,64,'chop'),64) if p.square == 'paired' else cut(z*z,p.square)
        v = M(u,u)
        odd = A(M(A(M(ROM[205],v),ROM[203]),v),ROM[201])
        even = A(M(A(M(ROM[204],v),ROM[202]),v),ROM[200])
        h = A(M(odd,v),M(even,u))
        return W(M(h,z),z)
    if x <= 0:
        raise ValueError('nonpositive FYL2X discovery input')
    e = exponent(x); m = x/pow2(e)
    i = int((m-1)*32)
    anchor = F(65+2*i,64)
    numerator = A(A(m,-anchor),A(m,-anchor))
    denominator = cut(m+anchor,p.table_denominator)
    z = cut(numerator/denominator,p.table_div)
    lead = M(ROM[195],z); u = M(z,z)
    h = A(M(A(M(ROM[199],u),ROM[198]),u),ROM[197])
    tail = M(M(h,u),z)
    return W(W(A(tail,lead),ROM[238+i]),A(F(e),ROM[206+i]))


def prevalue(op, ys,ym,xs,xm,p=Policy()):
    return value(ys,ym)*logarithm(op,value(xs,xm),p)


def predict(line,p=Policy()):
    _,op,rc,pc,ys,ym,xs,xm = line.split()
    v = prevalue(op,*(int(s,16) for s in (ys,ym,xs,xm)),p)
    se,sig = encode(v,rc)
    c1 = int((se & 0x7fff) == 0x7fff or abs(value(se,sig)) > abs(v))
    return se,sig,c1


def classify(se, sig):
    e = se & 0x7fff
    if not e:
        return 'zero' if not sig else ('pseudo' if sig >> 63 else 'denormal')
    if not sig >> 63:
        return 'unsupported'
    if e != 0x7fff:
        return 'normal'
    return 'infinity' if sig == 1 << 63 else ('qnan' if sig & (1 << 62) else 'snan')


def architectural(op,ys,ym,xs,xm,rc='rn',p=Policy()):
    """Masked numerical contract: result, C1, exception flags.

    FYL2XP1 finite arguments are used only in Intel's documented interval.
    Arbitrary state histories and undefined condition bits are outside scope.
    """
    ky,kx = classify(ys,ym),classify(xs,xm)
    invalid = (0xffff,0xc000000000000000,0,1)
    if 'unsupported' in (ky,kx):
        return invalid
    ny,nx = ky in ('qnan','snan'),kx in ('qnan','snan')
    if ny or nx:
        if not ny: pick=xs,xm
        elif not nx: pick=ys,ym
        elif ky == 'qnan' and kx == 'snan': pick=ys,ym
        elif kx == 'qnan' and ky == 'snan': pick=xs,xm
        else: pick=(ys,ym) if ym > xm or (ym == xm and ys < xs) else (xs,xm)
        return pick[0],pick[1]|(1 << 62),0,int('snan' in (ky,kx))
    if op == 'fyl2xp1' and ((xs & 0x7fff) > 0x3ffd or
            ((xs & 0x7fff) == 0x3ffd and xm > 0x95f619980c4336f7)):
        raise ValueError('FYL2XP1 argument outside Intel specified range')
    de = 2 if any(k in ('denormal','pseudo') for k in (ky,kx)) else 0
    sy,sx = ys >> 15,xs >> 15
    if op == 'fyl2x':
        if sx and kx != 'zero': return invalid
        if kx == 'zero':
            return invalid if ky == 'zero' else (((sy^1) << 15)|0x7fff,1 << 63,0,4)
        if kx == 'infinity':
            return invalid if ky == 'zero' else ((sy << 15)|0x7fff,1 << 63,0,de)
        x = value(xs,xm)
        logsign = int(x < 1)
        logzero = x == 1
    else:
        x = value(xs,xm)
        logsign = sx
        logzero = kx == 'zero'
    sign = sy^logsign
    if logzero:
        return invalid if ky == 'infinity' else (sign << 15,0,0,de)
    if ky == 'infinity': return (sign << 15)|0x7fff,1 << 63,0,de
    if ky == 'zero': return sign << 15,0,0,de
    v = value(ys,ym)*logarithm(op,x,p)
    se,sig = encode(v,rc)
    c1 = int((se & 0x7fff) == 0x7fff or abs(value(se,sig)) > abs(v))
    flags = de|32
    if abs(quantize(v,64,rc)) < pow2(-16382): flags |= 16
    if exponent(v) > 16383 or (se & 0x7fff) == 0x7fff: flags |= 8
    return se,sig,c1,flags


def predict_full(line,p=Policy()):
    _,op,rc,pc,ys,ym,xs,xm = line.split()
    return architectural(op,*(int(s,16) for s in (ys,ym,xs,xm)),rc,p)
