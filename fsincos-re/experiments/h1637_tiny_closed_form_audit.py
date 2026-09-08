#!/usr/bin/env python3
"""Closed-form tiny outputs/C1 and explicit remaining special/status coverage.

No hardware and no emulator changes. Derive tiny answers by predecessor and
mode/sign logic, without polynomial fitting or an arbitrary far-sticky value.
The -68 cutoff is the existing silicon-observed bypass, not a new fitted gate.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import h1633_shared_table_audit as candidate
import h1634_independent_table_certificate as raw_reader

PARENT='tmp/ledger33/current/h1633_shared_table_audit/'
EXTENDED='tmp/ledger33/current/h1636_retained_rz_pc_transfer/'
M66=0x3243f6a8885a308d3
B63=1<<63
LOCKS={
    **candidate.LOCKS,
    PARENT+'report.json':'935a4352843b0b0b96559fb4447fc1a329b0da9d5530c85790b622b3bc5bb51c',
    'experiments/h1633_shared_table_audit.py':'3f23458fff3cc1b4965215554874eb011d53283ab18c93a6fa8fce933bbf864b',
    'experiments/h1634_independent_table_certificate.py':'41393ef2dd4fc42ff4d047b8fae87af529f9cb51e2ef784a78bf7ddc1a20cefa',
    'experiments/h117_fsin_tiny_boundary.py':'c949df2429f7a3d38bbf8992916b77f3d50e0923fe6b4ae82d4ca3e030adf75e',
    'experiments/h238_fcos_tiny_boundary.py':'2e1fc746cc2151dd27e5cc94ae9f374ab307cf1b984d21110e8e01d00480fe52',
    'capture-kit/run_standalone_prebuilt.sh':'f3b7db50ef7f2bfa898b66f502e66ae6a079d909aec4fc100f06b5db90390466',
}


def normal(sign,e,sig):
    assert B63<=sig<1<<64
    if e < -16382:
        sig >>= -16382-e; field=0
    else: field=e+16383
    return f'{field+(0x8000 if sign else 0):04x}:{sig:016x}'


def evaluate(operand,instruction,mode):
    se,sig=(int(w,16) for w in operand.split()); ef=se&0x7fff; sign=se>>15
    detail=dict(input_exponent_field=ef,input_sign=sign,C1=None,exception_flags=None,reduced=False)
    def result(path,value=None,**more): return dict(detail,path=path,output=value,**more)
    if ef and not sig&B63: return result('invalid_encoding','ffff:c000000000000000')
    if not sig: return result('zero', '3fff:8000000000000000' if instruction=='fcos' else f'{sign<<15:04x}:0000000000000000')
    if ef==0x7fff:
        if sig==B63: return result('infinity','ffff:c000000000000000')
        return result('quiet_nan' if sig&(1<<62) else 'signaling_nan',f'{se:04x}:{sig|(1<<62):016x}')
    e=(ef if ef else 1)-16383; shift=64-sig.bit_length(); sig<<=shift; e-=shift
    detail['input_top']=e
    if e>=63: return result('out_of_range_C2','C2')
    # The captured normal finite instruction sets precision even when its
    # internal numerical endpoint is exact. This is tested as a separate
    # flag hypothesis, not derived from the final rounding remainder.
    if ef: detail['exception_flags']=0x20
    direct=e<-1 or (e==-1 and sig<0xc90fdaa22168c234)
    phase=int(instruction=='fcos')
    if direct:
        if e>=-32: return result('table' if e>=-2 else 'polynomial')
        if e < -68:
            detail['C1']=0
            return result('direct_bypass_cosine' if phase else 'direct_bypass_sine',
                '3fff:8000000000000000' if phase else normal(sign,e,sig))
        magnitude_sig,magnitude_exp,residual_sign,n=sig,e,sign,phase
    else:
        a=sig<<(e+2); q,rem=divmod(a,M66); assert rem*2!=M66
        q+=int(rem*2>M66); d=a-q*M66
        n=(-q if sign else q)+phase; residual_sign=sign^int(d<0)
        detail['reduced']=True
        if not d:
            negative=((n>>1)&1)^(0 if n&1 else residual_sign)
            return result('exact_reduced_zero',f'{0x3fff+(negative<<15):04x}:8000000000000000' if n&1 else f'{negative<<15:04x}:0000000000000000')
        width=abs(d).bit_length(); magnitude_exp=width-1-65
        if magnitude_exp>=-32: return result('table' if magnitude_exp>=-2 else 'polynomial')
        assert width<=33 and width<=64
        magnitude_sig=abs(d)<<(64-width)
    cosine=n&1; negative=((n>>1)&1)^(0 if cosine else residual_sign)
    if cosine: out_sig,out_exp=B63,0
    else: out_sig,out_exp=magnitude_sig,magnitude_exp
    toward_zero=mode=='rz' or (mode=='rd' and not negative) or (mode=='ru' and negative)
    detail['C1']=int(not toward_zero)
    if toward_zero:
        if out_sig>B63: out_sig-=1
        else: out_sig=(1<<64)-1; out_exp-=1
    path=('reduced' if detail['reduced'] else 'direct')+'_sticky_'+('cosine' if cosine else 'sine')
    return result(path,normal(negative,out_exp,out_sig),residual_top=magnitude_exp)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--extended-sha256',required=True)
    args=parser.parse_args(); root,output=args.root.resolve(),args.output_dir.resolve(); assert not output.exists()
    digest=candidate.records.digest; evidence={**LOCKS,EXTENDED+'report.json':args.extended_sha256}
    for name,expected in evidence.items(): assert digest(root/name)==expected,name
    parent=json.loads((root/PARENT/'report.json').read_text())
    extended=json.loads((root/EXTENDED/'report.json').read_text())
    for report in (parent,extended):
        for name,expected in report['sha256']['evidence'].items():
            assert digest(root/name)==expected,name
            evidence[name]=expected
    banks=[]
    previous=json.loads((root/PARENT/'prepared.json').read_text())
    assert digest(root/PARENT/'prepared.json')==parent['sha256']['prepared']
    for b in previous['inventories']:
        if b['tag'] not in ('sweep_fsin','sweep_fcos'): continue
        for mode,capture in b['captures'].items():
            banks.append(dict(tag=b['tag']+'_'+mode+'_pc64',instruction=b['instruction'],mode=mode,pc=64,inputs=b['inputs'],count=b['count'],capture=capture))
    extra=json.loads((root/EXTENDED/'prepared.json').read_text())
    for b in extra['inventories']:
        if b['tag'].startswith('sweep_') and b['tag']!='sweep_fsin_rn_pc64': banks.append(b)
    # Authenticate the tiny generator's exact expected order without running
    # any legacy capture runner or rewriting an existing input file.
    tiny='capture-kit/inputs/constraint_fsin_tiny_h117.txt'
    expected=[f'{(sign<<15)|(e+16383):04x} {sig:016x}' for e in range(-72,-27)
              for sig in (B63,B63+1,0xaaaaaaaaaaaaaaaa,(1<<64)-1) for sign in (0,1)]
    assert (root/tiny).read_text().splitlines()==expected
    for mode in ('rn','rd','ru'):
        banks.append(dict(tag='h117_fsin_'+mode+'_pc64',instruction='fsin',mode=mode,pc=64,inputs=tiny,count=360,
            capture='capture-kit-captures/skylake-fsin-h110/constraint_fsin_tiny_'+mode+'_status.txt'))
    for b in banks:
        for name in (b['inputs'],b['capture']):
            h=digest(root/name); assert evidence.get(name,h)==h; evidence[name]=h
    binaries={label:root/PARENT/label for label in ('candidate_O0','candidate_O2','candidate_O3','candidate_ubsan')}
    for label,binary in binaries.items(): assert digest(binary)==parent['sha256']['binaries'][label]
    output.mkdir(parents=True)
    candidate.records.save(output/'prepared.json',dict(state='SOFTWARE_TINY_CLOSED_FORM_AND_SCOPE_AUDIT',inventories=banks,sha256=evidence))
    totals,paths,sw_hist,reports,exceptions=Counter(),{}, {},[],[]
    all_scored=[]
    for b in banks:
        operands=(root/b['inputs']).read_text().splitlines(); actual=(root/b['capture']).read_text().splitlines()
        assert len(operands)==len(actual)==b['count']; counts=Counter(); sampled={}; details=[]
        for start in range(0,len(operands),4096):
            batch=operands[start:start+4096]
            values,metadata,_,_=candidate.run(binaries['candidate_O2'],b['instruction'],b['mode'],batch)
            for i,(op,value) in enumerate(zip(batch,values)):
                expected=evaluate(op,b['instruction'],b['mode']); path=expected['path']
                observed,sw=raw_reader.raw(actual[start+i],True)
                assert value==observed
                counts['rows']+=1
                has_numerical_hook=i in metadata
                assert has_numerical_hook==(path in ('polynomial','table'))
                pc=paths.setdefault(path,Counter()); pc['rows']+=1
                sw_hist.setdefault(path,Counter())[f'{sw:04x}']+=1
                if expected['output'] is None:
                    counts['existing_numerical_hook_rows']+=1
                else:
                    counts['closed_form_output_checks']+=1; pc['output_checks']+=1
                    wrong=value!=expected['output']; counts['closed_form_output_misses']+=wrong; pc['output_misses']+=wrong
                    if expected['C1'] is not None:
                        badc1=expected['C1']!=(sw>>9)&1
                        counts['closed_form_C1_checks']+=1; pc['C1_checks']+=1
                        counts['closed_form_C1_misses']+=badc1; pc['C1_misses']+=badc1
                    else: badc1=False
                    row=dict(bank=b['tag'],index=start+i,operand=op,instruction=b['instruction'],mode=b['mode'],pc=b['pc'],
                             hardware=observed,hardware_status=f'{sw:04x}',candidate=value,closed_form=expected)
                    details.append(row); all_scored.append(row)
                    if wrong or badc1: exceptions.append(row)
                    key=(path,b['mode'],expected.get('input_top'),expected['input_sign'])
                    if key not in sampled: sampled[key]=start+i
                if expected['exception_flags'] is not None:
                    badflags=(sw&0x3f)!=expected['exception_flags']
                    counts['normal_finite_precision_flag_checks']+=1; pc['exception_flag_checks']+=1
                    counts['normal_finite_precision_flag_misses']+=badflags; pc['exception_flag_misses']+=badflags
                    if badflags:
                        exceptions.append(dict(bank=b['tag'],index=start+i,operand=op,hardware_status=f'{sw:04x}',expected_exception_flags=expected['exception_flags'],path=path))
        indices=sorted(sampled.values()); builds={}
        for label,binary in binaries.items():
            values,metadata,_,_=candidate.run(binary,b['instruction'],b['mode'],[operands[i] for i in indices])
            assert not metadata
            builds[label]=values
        assert all(v==builds['candidate_O2'] for v in builds.values())
        candidate.records.save(output/(b['tag']+'_closed_form.json'),details)
        candidate.records.save(output/(b['tag']+'_compiler.json'),dict(indices=indices,builds=builds))
        reports.append(dict(bank=b['tag'],counts=dict(counts),compiler_checked_rows=len(indices)))
        totals.update(counts); print(b['tag'],dict(counts),flush=True)
    unique={}
    for row in all_scored:
        key=(row['instruction'],row['mode'],row['pc'],row['operand'])
        if key in unique: assert (row['hardware'],row['hardware_status'])==unique[key]
        unique[key]=row['hardware'],row['hardware_status']
    certificate=dict(status='TINY_NUMERICAL_RULE_NOT_FULL_SILICON_PROOF',
        nonbypass='For 0<r<2^-32, sine is strictly below r by less than half the predecessor spacing; cosine is strictly below1 by less than2^-65. Round-nearest or away-from-zero returns the exact leading value (C1=1); toward-zero returns its 64-bit predecessor (C1=0). Quadrant/sign choose numerical direction.',
        reduced_grid='Nonzero reduced tiny r=D*2^-65 has at most33 significant bits. The leading r is exactly64-representable, so no hidden fractional input rounding is needed.',
        bypass='Unreduced external top exponent<-68 follows the existing silicon-observed bypass: FSIN returns x, FCOS returns1, C1=0. This is not correct mathematical directed rounding of sin/cos and is not derived from an epsilon bound.',
        source_equivalence='The existing far-sticky term lies strictly below half a leading ulp in this domain; its arbitrary magnitude can be replaced by the predecessor/mode/sign rule. This is a source-backed mathematical argument, not full C formal verification.',
        flags='Normal finite in-range nonzero inputs are separately tested for exception bits0x20, including bypass. Do not derive instruction PE from endpoint exactness or impute denormal/special/unmasked exception behavior.',
        coverage='Counts and absent paths are explicit. Stored SW includes FLD effects and excludes later FSTP; full x87 state/status is not implemented.')
    for name,expected in evidence.items(): assert digest(root/name)==expected,name
    result=dict(experiment='h1637_tiny_closed_form_audit',status='FAIL_CLOSED_FORM_OR_FLAGS' if exceptions else 'PASS_RETAINED_TINY_AND_NORMAL_FLAG_CHECKS',
        counts=dict(totals),unique_closed_form_tuples=len(unique),banks=reports,paths={k:dict(v) for k,v in paths.items()},
        status_histograms={k:dict(v) for k,v in sw_hist.items()},exceptions=exceptions,certificate=certificate,
        hardware_execution='none',private_ledger_access='none',canonical_default_or_paper_change='none',
        sha256=dict(script=digest(Path(__file__)),evidence=evidence,artifacts={p.name:digest(p) for p in sorted(output.iterdir())}))
    candidate.records.save(output/'report.json',result)
    print(result['status'],dict(totals),'unique',len(unique),flush=True)


if __name__=='__main__': main()
