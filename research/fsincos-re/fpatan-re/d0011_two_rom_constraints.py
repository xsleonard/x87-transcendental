"""Exact two-shared-coefficient constraints for one fixed MR64 graph.

A118 is enumerated on a 69-bit grid within +/-16 P5 ULPs. A119 is inverted
exactly without a prior numerical bound; A120..123 are unchanged. A survivor
is only a constant-bank hypothesis, never an input-conditioned correction.
This does not alter the candidate or claim Skylake ROM provenance.
"""
import json
from d0010_causal_intervals import BASE,Interval,observation_interval
from d0011_terminal_preimage import Recipe,solve,lattice,inverse_chop,divide
from d0011_rom_constraint_audit import inverse_rn_range
from graph_v5 import prevalue
from model import F,ROM,cut,exponent,pow2
from prepare import save


def main():
    data=[];seen=set()
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        raw=pair['raw'];t={};prevalue(*raw,trace=t)
        if t['kind']!='direct' or t['swap'] or raw[2]&32768:continue
        band=observation_interval(pair['rows']);key=(t['z'],band)
        if key in seen:continue
        seen.add(key);z=t['z'];u=cut(z*cut(z,'chop64'),'rn64')
        answer=solve(z,band,Recipe('mr-cubic',z_read='exact',order='square-z-h'),u);assert answer['feasible']
        pre=inverse_rn_range(F(answer['h_first']),F(answer['h_last']),64)
        h=ROM[123]
        for k in range(122,119,-1):h=cut(ROM[k]+cut(u*h,'chop67'),'rn64')
        product=cut(u*h,'chop67');assert product<0
        data.append((pair,t,band,u,pre,product))
    reports=[];survivors=[];step=pow2(exponent(ROM[118])-68)
    for offset in range(-64,65):
        a118=abs(ROM[118])+offset*step;common=None;constraints=[];failure=None
        for pair,t,band,u,pre,product in data:
            pband=Interval(a118-pre.hi,a118-pre.lo,pre.hc,pre.lc)
            assert pband.lo>0
            mul=inverse_chop(pband,67)
            hvalues=lattice(divide(mul,u),64) if mul is not None else None
            if hvalues is None:
                failure=dict(input=pair['rows'][0]['input'],reason='no_h119_lattice');break
            prior=inverse_rn_range(*hvalues,64)
            allowed=Interval(prior.lo-product,prior.hi-product,prior.lc,prior.hc)
            common=allowed if common is None else common.intersect(allowed)
            constraints.append(dict(input=pair['rows'][0]['input'],allowed_A119=allowed.json()))
            if not common.valid():
                failure=dict(input=pair['rows'][0]['input'],reason='disjoint_global_A119_constraints');break
        possible=lattice(common,69) if failure is None else None
        r=dict(A118_offset_in_69bit_ULPs=offset,A118_magnitude=str(a118),
            tested_groups=len(constraints),intersection=common.json() if common is not None else None,
            counterexample=failure,feasible_69bit_A119=possible is not None,constraints=constraints)
        if possible:
            lo,hi=possible;a119=min(max(ROM[119],lo),hi)
            assert cut(a119,'chop69')==a119
            # Independent forward replay of the two globally shared values.
            for pair,t,band,u,pre,product in data:
                h=ROM[123]
                for k in range(122,117,-1):
                    a=-a118 if k==118 else a119 if k==119 else ROM[k]
                    h=cut(a+cut(u*h,'chop67'),'rn64')
                v=t['z']+cut(cut(u*t['z'],'chop67')*h,'chop67')
                assert band.contains(v)
            r['representative_A119']=str(a119)
            r['A119_offset_in_P5_ULPs']=str((a119-ROM[119])/pow2(exponent(ROM[119])-66))
            r['both_representable_in_67_bits']=cut(a118,'chop67')==a118 and cut(a119,'chop67')==a119
            survivors.append(r)
            print('LOCAL CONSTANT HYPOTHESIS',offset,r['A119_offset_in_P5_ULPs'],flush=True)
        reports.append(r)
    save(BASE/'d0011-two-rom-constraints.json',dict(status='TWO_GLOBAL_COEFFICIENT_DISCOVERY_AUDIT',
        graph='MR64 asymmetric square; cube-first C67 tail; C67 Horner products and RN64 adds',
        A118_grid_bits=69,A118_bound_in_P5_ULPs=16,A119_grid_bits=69,
        groups=len(data),trials=len(reports),survivors=survivors,results=reports,hardware_executed=False))
    print('COMPLETE',len(reports),'A118 values;',len(survivors),'two-constant hypotheses',flush=True)


if __name__=='__main__':main()
