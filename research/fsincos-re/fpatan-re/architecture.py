"""Masked raw80 architecture around the fixed V7 graph (D0027).

Special-value classes follow Intel SDM Vol. 2A FPATAN Table 3-30 and Vol. 1
NaN propagation rules. Actual raw encodings, rounding and flags were checked
in D0005--D0007 and the subsequent retained corpus. The contract excludes
unmasked traps, arbitrary restore history and undefined condition bits.
"""
from dataclasses import dataclass
from functools import lru_cache
from model import ROM,encode,value,pow2
from graph_v4 import PROGRAM,prevalue


@dataclass(frozen=True)
class ArchitecturePolicy:
    numerical_graph: str='v7'
    pseudo_denormal_DE: bool=True
    tininess_before_rounding: bool=True


POLICY=ArchitecturePolicy()


def classify(se,sig):
    e=se&32767
    if not e:
        if not sig:return 'zero'
        return 'pseudo' if sig>>63 else 'denormal'
    if not sig>>63:return 'unsupported'
    if e!=32767:return 'normal'
    if sig==1<<63:return 'infinity'
    return 'qnan' if sig&(1<<62) else 'snan'


@lru_cache(maxsize=32768)
def finite_prevalue(ys,ym,xs,xm,graph='v7'):
    if graph=='v4':return prevalue(ys,ym,xs,xm)
    if graph=='v5':
        from graph_v5 import prevalue as candidate_v5
        return candidate_v5(ys,ym,xs,xm)
    if graph=='v6':
        from graph_v6 import prevalue as candidate_v6
        return candidate_v6(ys,ym,xs,xm)
    if graph=='v7':
        from graph_v7 import prevalue as candidate_v7
        return candidate_v7(ys,ym,xs,xm)
    raise ValueError('unknown analysis numerical graph')


def predict(ys,ym,xs,xm,rc,p=POLICY):
    """Return se, significand, C1, masked exception flags, pre-load flags."""
    ky,kx=classify(ys,ym),classify(xs,xm);kinds=(ky,kx)
    if 'unsupported' in kinds:return 0xffff,0xc000000000000000,0,1,0
    nans=[(se,sig,k) for se,sig,k in ((ys,ym,ky),(xs,xm,kx)) if k in ('qnan','snan')]
    if nans:
        quiet=[n for n in nans if n[2]=='qnan'];pool=quiet or nans
        se,sig,_=max(pool,key=lambda n:(n[1],-n[0]))
        return se,sig|(1<<62),0,int('snan' in kinds),0
    de=2*int('denormal' in kinds or (p.pseudo_denormal_DE and 'pseudo' in kinds))
    sy=ys>>15;sx=xs>>15
    if ky=='zero':angle=ROM[19] if sx else 0
    elif kx=='zero':angle=ROM[20]
    elif ky=='infinity':angle=3*ROM[21] if kx=='infinity' and sx else (ROM[21] if kx=='infinity' else ROM[20])
    elif kx=='infinity':angle=ROM[19] if sx else 0
    else:
        v=finite_prevalue(ys,ym,xs,xm,p.numerical_graph);se,sig=encode(v,rc)
        tiny=abs(v)<pow2(-16382) if p.tininess_before_rounding else (se&32767)==0
        return se,sig,int(abs(value(se,sig))>abs(v)),32|de|(16 if tiny else 0),0
    v=-angle if sy else angle;se,sig=encode(v,rc,zero_sign=sy)
    return se,sig,int(abs(value(se,sig))>abs(v)),de|(32 if angle else 0),0


def selftest():
    assert classify(0,0)=='zero'
    assert classify(0,1)=='denormal'
    assert classify(0,1<<63)=='pseudo'
    assert classify(1,1)=='unsupported'
    assert classify(0x7fff,1<<63)=='infinity'
    assert classify(0x7fff,(1<<63)|1)=='snan'
    assert classify(0x7fff,3<<62)=='qnan'
    for s in (0,32768):
        assert predict(s,0,0x3fff,1<<63,'rn')[:2]==(s,0)
        assert predict(s|0x3fff,1<<63,0x7fff,1<<63,'rn')[:2]==(s,0)
    assert predict(0x7fff,(1<<63)|5,0x7fff,(3<<62)|2,'rn')[:4]==(0x7fff,(3<<62)|2,0,1)
    print('PASS architecture candidate synthetic tests; no hardware')


if __name__=='__main__':selftest()
