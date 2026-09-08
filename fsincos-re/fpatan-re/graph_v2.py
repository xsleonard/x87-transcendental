"""Analysis-only explicit FPATAN graph, separating final and intermediate adds.

The frozen D0001 model.py is preserved byte-for-byte. These are structural
hypotheses on already opened discovery labels, never validated selectors.
"""
from dataclasses import dataclass
from model import F,ROM,Policy,value,cut,encode,pow2


@dataclass(frozen=True)
class Graph:
    arithmetic: Policy = Policy()
    kernel: str = 'exact'
    intermediate: str = 'chop67'
    placement: str = 'rotate'
    tiny: int = 68
    constant: str = 'exact'
    swap_test: str = 'exact'
    reduction_mul: str | None = None


def prevalue(ys,ym,xs,xm,g=Graph()):
    p=g.arithmetic
    y,x=abs(value(ys,ym)),abs(value(xs,xm))
    if not y or not x:raise ValueError('zero outside current graph')
    swap=y>x
    if g.swap_test=='rn64':swap=cut(y/x,'rn64')>1
    if swap:y,x=x,y
    ratio=cut(y/x,p.initial_div)
    if g.tiny and ratio < pow2(-g.tiny):
        # Direct division bypass is a hardware hypothesis. It deliberately
        # differs from mathematical atan at directed-rounding exact ratios.
        angle=y/x;n=0;tail=F(0)
    else:
        if ratio < F(1,p.direct_limit):n=0
        else:
            q,r=divmod((ratio*32).numerator,(ratio*32).denominator)
            n=q+int(2*r >= (ratio*32).denominator)
        if n>32:raise ValueError('candidate table-index overflow')
        c=F(n,32)
        if n==0:z=cut(y/x,p.div)
        elif p.reduction=='pair':
            rm=g.reduction_mul or p.mul
            z=cut(cut(y-cut(c*x,rm),p.sub)/cut(x+cut(c*y,rm),p.denominator),p.div)
        else:
            z=cut(cut(ratio-c,p.sub)/cut(1+cut(c*ratio,p.mul),p.denominator),p.div)
        coeffs=[ROM[i] for i in (range(118,124) if p.polynomial=='long' else range(114,118))]
        square=cut(z*z,p.mul);h=coeffs[-1]
        for a in reversed(coeffs[:-1]):h=cut(a+cut(square*h,p.mul),p.add)
        tail=cut(cut(square*h,p.mul)*z,p.tail)
        angle=cut(z+tail,g.kernel)
    negative_x=bool(xs&0x8000)
    rotated=swap or negative_x
    table=cut(ROM[124+n],p.table) if n else F(0)
    if g.placement=='base-first':
        base=table
        if swap:base=cut(ROM[20],g.constant)-base;angle=-angle
        if negative_x:base=cut(ROM[19],g.constant)-base;angle=-angle
        result=cut(base,g.intermediate)+angle
    else:
        angle=table+angle
        if g.placement=='always' or (g.placement=='rotate' and rotated) or (g.placement=='swap' and swap):
            angle=cut(angle,g.intermediate)
        if swap:
            result=cut(ROM[20],g.constant)+(angle if negative_x else -angle)
        elif negative_x:result=cut(ROM[19],g.constant)-angle
        else:result=angle
    return -result if ys&0x8000 else result


def predict(line,g=Graph()):
    _,rc,pc,*raw=line.split()
    return encode(prevalue(*(int(t,16) for t in raw),g),rc)
