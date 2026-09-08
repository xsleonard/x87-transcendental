#!/usr/bin/env python3
"""Closed-form summary projection: exhaustive algebra, bounded silicon evidence.

This function is analysis-only. It is not installed as a general emulator law.
Exhaustive algebra proves properties of this function, not universal silicon
reachability or completeness of the physical pending-exception predicate.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from h1640_remaining_scope_freshness import save

LOCKS={
    'transfer-tests/h1680/FREEZE.json':'4a496faab3a3dbbc4e679ceeb32773f063cd9afb25fac920606b5bf5a7ea7b78',
    'transfer-tests/h1680/manifest.json':'9a36a1444aaaff31c3008e93208bd5a6fd2b8e043c4feb3cf0c4aa98d020c0ed',
    'transfer-tests/h1680/hardware-output/state-output.txt':'b40b0b78f569ec873a6172667d045d76bbecac037a6a6f31d06cdd86e6b85cfd',
    'tmp/ledger33/current/h1681_restore_paths_score/report.json':'8dbc25db111e1ce56895d490993e5662fb9491aca230732e4996c47a759c4a1e',
    'tmp/ledger33/current/h1682_independent_restore_hardware/report.json':'2511d74261cacae81cd8d5a2a4f529ea63995e48a4e727cf4d78f4ca7c5e423d',
}
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_status(sw,cw):
    """Preserve every non-summary bit; ES and B reflect the pending bit."""
    return (sw&0x7f7f)|(0x8080 if sw&~cw&0x3f else 0)

def algebra():
    counts=Counter()
    for sw in range(65536):
        for masks in range(64):
            result=canonical_status(sw,masks)
            pending=int(any((sw>>i)&1 and not (masks>>i)&1 for i in range(6)))
            assert result&0x7f7f==sw&0x7f7f
            assert ((result>>7)&1)==((result>>15)&1)==pending
            assert canonical_status(result,masks)==result
            assert canonical_status(sw,masks|0xffc0)==result
            assert canonical_status(result,63)==sw&0x7f7f
            counts['full_status_mask_cases']+=1; counts['fixed_points']+=result==sw
    assert counts['full_status_mask_cases']==4194304 and counts['fixed_points']==1048576
    # Composition depends only on the low exception flags and the two summary
    # bits. The other eight status bits are untouched by both expressions;
    # testing all values of those bits above establishes that factorization.
    for flags in range(64):
        for first in range(64):
            for second in range(64):
                for summary in (0,128,32768,32896):
                    sw=flags|summary
                    assert canonical_status(canonical_status(sw,first),second)==canonical_status(sw,second)
                    counts['factored_composition_cases']+=1
    assert counts['factored_composition_cases']==1048576
    return dict(counts)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path); a=p.parse_args()
    root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    counts=algebra(); kit=root/'transfer-tests/h1680'
    rows=json.loads((kit/'manifest.json').read_text()); lines=(kit/'hardware-output/state-output.txt').read_text().splitlines()
    assert len(rows)==len(lines)==1008
    hardware=Counter(); identity=Counter(); states=Counter()
    for row,line in zip(rows,lines):
        f=dict(word.split('=',1) for word in line.split()); assert f['CASE']==row['case_id']
        fxsw,fxcw,scsw,sccw=(int(f[k],16) for k in ('FX_SW','FX_CW','SCALAR_SW','SCALAR_CW'))
        assert fxsw==scsw and fxcw==sccw and canonical_status(fxsw,fxcw)==fxsw
        hardware['restoration_rows']+=1
        states[f'{int(bool(fxsw&~fxcw&63))}{int(bool(fxsw&128))}{int(bool(fxsw&32768))}']+=1
        if row['method'] in ('fxrstor','fldenv','frstor'):
            changed=bool((scsw^row['requested_SW'])&0x8080)
            identity[row['method']]+=changed
            if row['order']=='scalar' and changed: hardware['scalar_first_requested_summary_disagreements']+=1
        if row['method']=='fnstenv':
            saved_sw,saved_cw=(int(f[k],16) for k in ('SAVED_SW','SAVED_CW'))
            assert fxsw&0x8080==0 and fxcw&63==63
            if saved_sw&~saved_cw&63:
                assert saved_sw&0x8080==0x8080
                hardware['paired_saved_pending_to_post_mask_clear']+=1
        if row['method']=='fldcw' and fxsw&~fxcw&63:
            hardware['control_load_final_pending_rows']+=1
    assert dict(identity)=={'fxrstor':216,'fldenv':216,'frstor':216}
    assert hardware['scalar_first_requested_summary_disagreements']==324
    assert hardware['paired_saved_pending_to_post_mask_clear']==32
    assert hardware['control_load_final_pending_rows']==32
    out.mkdir(parents=True)
    report=dict(experiment='h1683_summary_normal_form',status='EXHAUSTIVE_FUNCTION_ALGEBRA_AND_BOUNDED_RESTORE_SUPPORT',
        algebra=counts,retained_hardware=dict(hardware),actual_states=dict(states),identity_misses=dict(identity),
        formula='C(SW,CW)=(SW & 0x7f7f) | (0x8080 if (SW & ~CW & 0x3f)!=0 else 0)',
        conditional_induction='If every state-establishing/writing primitive emits this normal form, reset plus composition preserves ES=B=U. The universal premise is NOT proved by these captures.',
        unresolved_writer_coverage=['XRSTOR/XRSTORS and component initialization/skip paths',
            '16-bit legacy environment formats and other execution modes',
            'all exceptional arithmetic and asynchronous restore histories',
            'reserved controls and complete field/physical-state semantics'],
        causal_limit='324 direct status reads precede post-restore FXSAVE yet already disagree with requested summary bits. A normalization caused solely by that later FXSAVE cannot explain them. This does not isolate restore versus direct-read projection or asynchronous state handling.',
        claim_boundary='Exact universal properties of an explicit bit function plus retained finite hardware support. Not a universal silicon law, unreachable-state proof, pending-gate selection or all-input FSIN/FCOS closure.',
        hardware_execution='none; retained audit only',default_or_paper_change='none',
        sha256=dict(script=digest(Path(__file__)),evidence=LOCKS))
    save(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('algebra','retained_hardware','actual_states','identity_misses')},sort_keys=True),flush=True)
if __name__=='__main__': main()
