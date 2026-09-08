"""Analysis-only FPATAN stage graph; D0001/D0002 snapshots stay immutable.

Candidate hardware dispatch and stage cuts are explicit. In particular,
small-ratio cutoffs remain hypotheses until prospectively discriminated.
"""
from dataclasses import dataclass
from model import F,ROM,Policy,value,cut,encode,pow2,exponent


@dataclass(frozen=True)
class Program:
    tiny_exponent: int = 40
    direct_limit: int = 32
    direct_test: str = 'ratio'
    index_read: str = 'exact'
    denominator: str = 'chop67'
    divider: str = 'chop67'
    multiply: str = 'chop67'
    add: str = 'rn64'
    tail_first: str = 'chop67'
    tail_second: str = 'chop67'
    coefficient_set: str = 'long'
    direct_divider: str | None = None
    direct_lead: str = 'rounded'
    table_coefficients: str | None = None
    direct_numerator: int = 1
    table_index: str = 'nearest'
    numerator: str = 'chop67'
    table_divider: str | None = None
    kernel_cut: str = 'exact'
    forced_index: int | None = None
    table_kernel_cut: str | None = None
    square_cut: str | None = None
    tail_order: str = 'square-h-z'
    last_add: str | None = None
    last_multiply: str | None = None
    tail_z_read: str = 'exact'


def prevalue(ys,ym,xs,xm,p=Program(),trace=None):
    y,x=abs(value(ys,ym)),abs(value(xs,xm))
    if not y or not x:raise ValueError('nonzero finite program only')
    swap=y>x
    if swap:y,x=x,y
    r=y/x;index_ratio=cut(r,p.index_read);n=0
    if p.tiny_exponent and r < pow2(-p.tiny_exponent):
        z=cut(r,p.divider);angle=z;kind='tiny';h=F(0);square=F(0);tail=F(0)
    else:
        if p.direct_test=='exponent':direct=exponent(y)-exponent(x)<=-5
        elif p.direct_test=='ratio-le':direct=index_ratio<=F(p.direct_numerator,p.direct_limit)
        else:direct=index_ratio<F(p.direct_numerator,p.direct_limit)
        if p.forced_index is not None:direct=p.forced_index==0
        if direct:kind='direct';z=cut(r,p.direct_divider or p.divider)
        else:
            kind='table';q,rem=divmod((index_ratio*32).numerator,(index_ratio*32).denominator)
            if p.table_index=='floor':n=q
            elif p.table_index=='even':n=q+int(2*rem>(index_ratio*32).denominator or (2*rem==(index_ratio*32).denominator and q&1))
            else:n=q+int(2*rem >= (index_ratio*32).denominator)
            if p.forced_index is not None:n=p.forced_index
            if not 1<=n<=32:raise ValueError('out-of-ROM index')
            c=F(n,32)
            numerator=cut(y-c*x,p.numerator)
            denominator=cut(x+c*y,p.denominator)
            z=cut(numerator/denominator,p.table_divider or p.divider)
        square=cut(z*z,p.square_cut or p.multiply)
        coefficients=(p.table_coefficients or p.coefficient_set) if kind=='table' else p.coefficient_set
        cs=[ROM[i] for i in (range(118,124) if coefficients=='long' else range(114,118))]
        h=cs[-1]
        for i,a in enumerate(reversed(cs[:-1])):
            final=i==len(cs)-2
            mul=(p.last_multiply or p.multiply) if final else p.multiply
            add=(p.last_add or p.add) if final else p.add
            h=cut(a+cut(square*h,mul),add)
        tail_z=cut(z,p.tail_z_read)
        if p.tail_order=='z-h-square':tail=cut(cut(tail_z*h,p.tail_first)*square,p.tail_second)
        elif p.tail_order=='square-z-h':tail=cut(cut(square*tail_z,p.tail_first)*h,p.tail_second)
        else:tail=cut(cut(square*h,p.tail_first)*tail_z,p.tail_second)
        lead=r if kind=='direct' and p.direct_lead=='exact' else z
        kernel_cut=(p.table_kernel_cut or p.kernel_cut) if n else p.kernel_cut
        angle=cut(lead+tail,kernel_cut)+(ROM[124+n] if n else 0)
    intermediate=angle
    if swap or xs&0x8000:intermediate=cut(angle,'chop67')
    if swap:result=ROM[20]+(intermediate if xs&0x8000 else -intermediate)
    elif xs&0x8000:result=ROM[19]-intermediate
    else:result=intermediate
    if ys&0x8000:result=-result
    if trace is not None:
        trace.update(kind=kind,n=n,ratio=r,z=z,square=square,horner=h,tail=tail,
                     angle=angle,intermediate=intermediate,swap=swap,result=result)
    return result


def predict(line,p=Program()):
    _,rc,pc,*raw=line.split();v=prevalue(*(int(t,16) for t in raw),p)
    se,sig=encode(v,rc);c1=int(abs(value(se,sig))>abs(v))
    return se,sig,c1
