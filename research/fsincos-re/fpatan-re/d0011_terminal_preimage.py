"""Exact coefficient-independent feasibility of direct FPATAN tail graphs.

The hardware RC/C1 intersection constrains the final prevalue. Invert a
positive-magnitude CHOP product exactly, then ask whether ANY h on the
specified significand lattice reaches it. This removes every ROM coefficient
constraint; impossibility therefore rejects the terminal graph, not merely a
particular coefficient bank. This is saved-data analysis, never a selector.
"""
import argparse
import json
from dataclasses import dataclass
from d0010_causal_intervals import BASE,Interval,observation_interval,selftest as interval_selftest
from graph_v5 import prevalue
from model import F,cut,exponent,pow2
from prepare import save


def successor(v,bits):
    assert v>0 and cut(v,'chop'+str(bits))==v
    return v+pow2(exponent(v)-bits+1)


def predecessor(v,bits):
    assert v>0 and cut(v,'chop'+str(bits))==v
    e=exponent(v)
    return v-pow2(e-bits if v==pow2(e) else e-bits+1)


def lattice(band,bits):
    """First/last positive p-bit values contained in a positive interval."""
    assert band.lo>0 and band.hi>0
    lo=cut(band.lo,'chop'+str(bits));hi=cut(band.hi,'chop'+str(bits))
    if lo<band.lo or not band.lc:lo=successor(lo,bits)
    if hi==band.hi and not band.hc:hi=predecessor(hi,bits)
    return None if lo>hi else (lo,hi)


def inverse_chop(band,bits):
    endpoints=lattice(band,bits)
    if endpoints is None:return None
    lo,hi=endpoints
    return Interval(lo,successor(hi,bits),True,False)


def divide(band,k):
    assert k>0
    return Interval(band.lo/k,band.hi/k,band.lc,band.hc)


@dataclass(frozen=True)
class Recipe:
    name:str
    z_read:str='chop64'
    square:str='chop67'
    first_bits:int=67
    last_bits:int=67
    h_bits:int=64
    order:str='square-h-z'


def tail(z,h,p,square_value=None):
    u=cut(z*z,p.square) if square_value is None else square_value
    zr=cut(z,p.z_read)
    if p.order=='square-z-h':
        return cut(cut(u*zr,'chop'+str(p.first_bits))*h,'chop'+str(p.last_bits))
    if p.order=='square-h-z':a,b=u,zr
    elif p.order=='z-h-square':a,b=zr,u
    else:raise ValueError(p.order)
    return cut(cut(a*h,'chop'+str(p.first_bits))*b,'chop'+str(p.last_bits))


def solve(z,band,p,square_value=None):
    # On an unrotated direct path the angle is z-|tail|. All coefficients
    # are freed; h need only have a negative sign and p.h_bits precision.
    target=Interval(z-band.hi,z-band.lo,band.hc,band.lc)
    assert target.lo>0
    u=cut(z*z,p.square) if square_value is None else square_value
    zr=cut(z,p.z_read)
    a,b=(u,zr) if p.order=='square-h-z' else (zr,u)
    last=inverse_chop(target,p.last_bits)
    if last is None:return dict(feasible=False,reason='no_final_product_lattice',target=target.json())
    if p.order=='square-z-h':
        hband=divide(last,cut(u*zr,'chop'+str(p.first_bits)))
    else:
        first=divide(last,b)
        before=inverse_chop(first,p.first_bits)
        if before is None:return dict(feasible=False,reason='no_first_product_lattice',target=target.json(),first=first.json())
        hband=divide(before,a)
    values=lattice(hband,p.h_bits)
    if values is None:
        return dict(feasible=False,reason='no_horner_lattice',target=target.json(),h_interval=hband.json(),
                    below=str(cut(hband.lo,'chop'+str(p.h_bits))),
                    above=str(successor(cut(hband.lo,'chop'+str(p.h_bits)),p.h_bits)))
    # Constructive validation of both endpoints, using forward arithmetic.
    for h in values:assert band.contains(z-tail(z,h,p,square_value))
    return dict(feasible=True,h_first=str(values[0]),h_last=str(values[1]),h_interval=hband.json())


def selftest():
    interval_selftest()
    # Exercise normal values, binade transitions, exact singleton targets,
    # and open intervals. Independent brute enumeration at small precision.
    grid=sorted(set(F(n)*pow2(e-3) for e in range(-5,6) for n in range(8,16)))
    for q in grid[2:-2]:
        assert predecessor(successor(q,4),4)==q
        assert successor(predecessor(q,4),4)==q
        for width in (F(0),pow2(exponent(q)-6)):
            for lc,hc in ((True,True),(True,False),(False,True),(False,False)):
                band=Interval(q-width,q+width,lc,hc)
                got=lattice(band,4);expected=[v for v in grid if band.contains(v)]
                assert got==((expected[0],expected[-1]) if expected else None)
                inv=inverse_chop(band,4)
                for j in range(-8,9):
                    v=q+j*pow2(exponent(q)-7)
                    assert (inv is not None and inv.contains(v))==band.contains(cut(v,'chop4'))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--expanded',action='store_true');args=ap.parse_args()
    selftest()
    recipes=[Recipe('V5'),Recipe('V4',z_read='exact'),Recipe('RN64-z',z_read='rn64')]
    recipes += [Recipe('free-h'+str(w),h_bits=w) for w in (65,66,67,68,69)]
    recipes += [Recipe('z-h-square-'+r,z_read=r,order='z-h-square') for r in ('exact','chop64','rn64')]
    if args.expanded:
        recipes=[Recipe(f'{order}-{r}-{first}-{last}-h{h}',z_read=r,order=order,
                        first_bits=first,last_bits=last,h_bits=h)
                 for order in ('square-h-z','z-h-square','square-z-h')
                 for r in ('exact','chop64','rn64')
                 for first in (64,67,69) for last in (64,67,69) for h in (64,67,69)]
    data=[];seen=set()
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        raw=pair['raw'];t={};prevalue(*raw,trace=t)
        if t['kind']!='direct' or t['swap'] or raw[2]&32768:continue
        band=observation_interval(pair['rows']);key=(t['z'],band)
        if key in seen:continue
        seen.add(key);data.append((pair,t,band))
    reports=[]
    for p in recipes:
        rows=[]
        for pair,t,band in data:
            outcome=solve(t['z'],band,p)
            rows.append(dict(input=pair['rows'][0]['input'],ratio=str(t['ratio']),z=str(t['z']),
                             interval=band.json(),**outcome))
        bad=[r for r in rows if not r['feasible']]
        if not args.expanded:print(p.name,'groups',len(rows),'impossible',len(bad),flush=True)
        reports.append(dict(recipe=vars(p),groups=len(rows),impossible=len(bad),results=rows))
    name='d0011-terminal-preimage-expanded.json' if args.expanded else 'd0011-terminal-preimage.json'
    save(BASE/name,dict(status='EXACT_TERMINAL_FEASIBILITY_NOT_A_SOLUTION',
        constraint='Any negative h at the specified precision; no coefficient bounds',
        reports=reports,hardware_executed=False))
    if args.expanded:
        print('Expanded recipes',len(reports),'feasible',sum(r['impossible']==0 for r in reports),flush=True)


if __name__=='__main__':main()
