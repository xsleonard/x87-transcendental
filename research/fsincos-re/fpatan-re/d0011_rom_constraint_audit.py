"""Invert the final RN64 add to constrain one globally shared ROM value.

Only terminal graphs that admit an arbitrary 64-bit Horner carrier are
examined. No coefficient is chosen per input. A disjoint intersection is a
coefficient-independent incompatibility for the specified upstream graph.
"""
import json
from d0010_causal_intervals import BASE,Interval,observation_interval
from d0011_terminal_preimage import Recipe,lattice,solve,predecessor,successor,selftest
from graph_v5 import prevalue
from model import ROM,F,cut,exponent,pow2
from prepare import save


def inverse_rn_range(lo,hi,bits):
    """Union of RN-even preimages for consecutive positive p-bit values."""
    assert 0<lo<=hi
    even=lambda v:not(int(v/pow2(exponent(v)-bits+1))&1)
    return Interval((predecessor(lo,bits)+lo)/2,(hi+successor(hi,bits))/2,even(lo),even(hi))


def main():
    selftest()
    expanded=json.loads((BASE/'d0011-terminal-preimage-expanded.json').read_text())
    recipes=[Recipe(**r['recipe']) for r in expanded['reports'] if r['impossible']==0 and r['recipe']['h_bits']==64]
    data=[];seen=set()
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        raw=pair['raw'];t={};prevalue(*raw,trace=t)
        if t['kind']!='direct' or t['swap'] or raw[2]&32768:continue
        band=observation_interval(pair['rows']);key=(t['z'],band)
        if key in seen:continue
        seen.add(key);data.append((pair,t,band))
    reports=[]
    for p in recipes:
        common=None;constraints=[];lower=None;upper=None
        for pair,t,band in data:
            answer=solve(t['z'],band,p);assert answer['feasible']
            hr=inverse_rn_range(F(answer['h_first']),F(answer['h_last']),64)
            u=cut(t['z']*t['z'],'chop67');h=ROM[123]
            for k in range(122,118,-1):h=cut(ROM[k]+cut(u*h,'chop67'),'rn64')
            product=cut(u*h,'chop67');assert product>0
            allowed=Interval(hr.lo+product,hr.hi+product,hr.lc,hr.hc)
            line=pair['rows'][0]['input']
            if common is None or allowed.lo>common.lo:lower=line
            if common is None or allowed.hi<common.hi:upper=line
            common=allowed if common is None else common.intersect(allowed)
            constraints.append(dict(input=line,allowed_A118_magnitude=allowed.json()))
        possible=common.valid() and lattice(common,67) is not None
        step=pow2(exponent(ROM[118])-66)
        offset=Interval((common.lo-abs(ROM[118]))/step,(common.hi-abs(ROM[118]))/step,common.lc,common.hc)
        reports.append(dict(recipe=vars(p),groups=len(data),feasible=possible,
            intersection=common.json(),offset_in_P5_ULPs=offset.json(),
            strongest_lower_input=lower,strongest_upper_input=upper,constraints=constraints))
        print(p.name,'shared A118 feasible',possible,'offset',offset.json(),flush=True)
    save(BASE/'d0011-rom-constraint-audit.json',dict(status='ONE_GLOBAL_ROM_COEFFICIENT_CONSTRAINT_AUDIT',
        fixed='A119..123 P5; square/Horner multiply CHOP67; Horner add RN64',
        reports=reports,hardware_executed=False))


if __name__=='__main__':main()
