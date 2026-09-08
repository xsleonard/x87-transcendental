#!/usr/bin/env python3
"""Reconcile retained FSIN RZ/PC captures with the fixed combined graph.

No capture, private-ledger access, source change or candidate adjustment.
Each hook row is checked using the separate H1634 rational graph/reducer.
PC is capture metadata, not a new emulator control-field implementation.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
import h1633_shared_table_audit as candidate
import h1634_independent_table_certificate as proof

PARENT='tmp/ledger33/current/h1633_shared_table_audit/'
RZ='capture-kit-captures/skylake-vm-r88-rz-20260826/'
PC='capture-kit-captures/skylake-fsin-h172/'
LOCKS={
    **candidate.LOCKS,
    PARENT+'report.json':'935a4352843b0b0b96559fb4447fc1a329b0da9d5530c85790b622b3bc5bb51c',
    'experiments/h1633_shared_table_audit.py':'3f23458fff3cc1b4965215554874eb011d53283ab18c93a6fa8fce933bbf864b',
    'experiments/h1634_independent_table_certificate.py':'41393ef2dd4fc42ff4d047b8fae87af529f9cb51e2ef784a78bf7ddc1a20cefa',
    'experiments/h172_fsin_precision_control.py':'e2101235e5cc82bb6e13e4e590965dbb448989783549fb16a799bfa8dd1c3dec',
    'experiments/vm_check.sh':'dcf32d05a54d2ee89afa1905bd503af086d4f4b721efac186f28ae62ce5458a6',
    'experiments/vmfsin_check.sh':'6f291ad5e280aa7edb605e358d871142fa9d2e313170ae80409686a0b39b3e49',
}


def initialize_proof(root):
    rom=(root/'src/p5_rom_constants.h').read_text()
    def constant(sign,e,hi,lo): return (-1 if int(sign) else 1)*((int(hi,16)<<64)|int(lo,16))*proof.p2(int(e))
    for kind,size,index,sign,e,hi,lo in re.findall(r'P5([SC])([46])_(\d) = \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull',rom):
        proof.C.setdefault(kind+size,{})[int(index)]=constant(sign,e,hi,lo)
    proof.C['S4'][4]-=proof.p2(-25)
    pattern=r'\{ (\d+), \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \}, \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \} \}'
    for b,*fields in re.findall(pattern,rom): proof.TABLE[int(b)]=constant(*fields[:4]),constant(*fields[4:])
    assert len(proof.C)==4 and len(proof.TABLE)==8


def verify_hit(operand,instruction,mode,meta):
    r,rs,cosine,negative,reduced=proof.external(operand,instruction)
    sign,e,word=meta['magnitude'].split(':')
    assert sign=='0' and int(word,16)*proof.p2(int(e))==r
    assert (rs,cosine,negative,proof.top(r))==(meta['residual_sign'],meta['cosine'],meta['negative'],meta['top'])
    center=False
    if meta['lane']=='table':
        b=proof.table_lane(r); assert b==meta['b']
        pre,_,_,precision,_,center=proof.table_graph(r,b)
        assert precision==meta['precision']<=61
        pre=pre[cosine]
    else:
        assert -32<=proof.top(r)<=-3 and proof.precision(r)==meta['precision']<=64
        pre=proof.polynomial_graph(r,cosine)
    value,c1=proof.final(pre,negative,mode)
    return value,c1,reduced,bool(center)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args(); root,output=args.root.resolve(),args.output_dir.resolve()
    assert not output.exists()
    digest=candidate.records.digest; evidence=dict(LOCKS)
    for name,expected in evidence.items(): assert digest(root/name)==expected,name
    parent=json.loads((root/PARENT/'report.json').read_text())
    for name,expected in parent['sha256']['evidence'].items():
        assert digest(root/name)==expected,name
        evidence[name]=expected
    prepared=json.loads((root/PARENT/'prepared.json').read_text())
    assert digest(root/PARENT/'prepared.json')==parent['sha256']['prepared']
    old={b['tag']:b for b in prepared['inventories']}
    pins={n:h for h,n in (line.split() for line in (root/RZ/'SHA256SUMS').read_text().splitlines())}
    assert set(pins)=={'cpu_info.txt','dense_fsin_rz.txt','h347_fsin_rz.txt','sweep_fsin_rz.txt'}
    for name,expected in pins.items(): assert digest(root/RZ/name)==expected
    evidence[RZ+'SHA256SUMS']=digest(root/RZ/'SHA256SUMS')
    evidence[RZ+'cpu_info.txt']=pins['cpu_info.txt']
    banks=[]
    for name in ('h347','sweep','dense'):
        previous=old[name+'_fsin']
        banks.append(dict(tag=name+'_fsin_rz_pc64',instruction='fsin',mode='rz',pc=64,
            inputs=previous['inputs'],count=previous['count'],capture=RZ+name+'_fsin_rz.txt',
            provenance='Restored and previously opened R88 VM bank; SHA256SUMS and documented runner/input mapping; no new capture.'))
    for family,inputs,count,stem,legacy in (
        ('sweep',old['sweep_fsin']['inputs'],50038,'sweep_fsin_rn',old['sweep_fsin']['captures']['rn']),
        ('h171','capture-kit/inputs/constraint_fsin_table_correction_h171.txt',283,'constraint_fsin_table_correction_h171_rn',
         'capture-kit-captures/skylake-fsin-h171/constraint_fsin_table_correction_h171_rn_status.txt')):
        ref=(root/legacy).read_bytes()
        evidence[legacy]=digest(root/legacy)
        for pc in (24,53,64):
            capture=PC+stem+f'_pc{pc}_status.txt'
            assert (root/capture).read_bytes()==ref,(family,pc)
            banks.append(dict(tag=family+f'_fsin_rn_pc{pc}',instruction='fsin',mode='rn',pc=pc,inputs=inputs,count=count,capture=capture,
                provenance='Previously opened H172 files; PC24/53/64 full lines equal legacy; source pinned here, no complete historical checksum manifest.'))
    for bank in banks:
        for name in (bank['inputs'],bank['capture']):
            h=digest(root/name); assert evidence.get(name,h)==h; evidence[name]=h
    initialize_proof(root)
    binaries={}
    for label in ('candidate_O0','candidate_O2','candidate_O3','candidate_ubsan'):
        binaries[label]=root/PARENT/label
        assert digest(binaries[label])==parent['sha256']['binaries'][label]
    output.mkdir(parents=True)
    candidate.records.save(output/'prepared.json',dict(state='RETAINED_RZ_PC_SOFTWARE_REPLAY',inventories=banks,sha256=evidence))
    totals,groups,reports,examples=Counter(),{},[],[]
    for bank in banks:
        directory=output/bank['tag']; directory.mkdir()
        operands=(root/bank['inputs']).read_text().splitlines()
        hardware=(root/bank['capture']).read_text().splitlines()
        assert len(operands)==len(hardware)==bank['count']
        counts=Counter(); sample_indices=set(); sampled_cells=set()
        with ExitStack() as stack:
            out=candidate.records.zipped(stack,directory/'candidate.stdout.gz')
            metaout=candidate.records.zipped(stack,directory/'metadata.jsonl.gz')
            failures=candidate.records.zipped(stack,directory/'misses.jsonl.gz')
            for start in range(0,len(operands),4096):
                batch=operands[start:start+4096]
                values,metadata,_,stdout=candidate.run(binaries['candidate_O2'],'fsin',bank['mode'],batch)
                out.write(stdout.encode())
                for i,meta in metadata.items(): metaout.write((json.dumps(dict(index=start+i,**meta),sort_keys=True)+'\n').encode())
                for i,(op,line) in enumerate(zip(batch,stdout.splitlines())):
                    value,_=proof.raw(line,False); actual,sw=proof.raw(hardware[start+i],True); assert value==values[i]
                    meta=metadata.get(i); lane=meta['lane'] if meta else 'fallback'
                    counts['rows']+=1; counts[lane+'_rows']+=1
                    counts[lane+'_output_misses']+=value!=actual
                    badc1=meta is not None and meta['C1']!=(sw>>9)&1
                    if meta:
                        expected,c1,reduced,center=verify_hit(op,'fsin',bank['mode'],meta)
                        assert expected==value and c1==meta['C1']
                        counts[lane+'_independent_checks']+=1; counts[lane+'_C1_misses']+=badc1
                        counts[lane+'_reduced_rows']+=reduced; counts[lane+'_exact_center_rows']+=center
                        cell=(lane,meta.get('b'),meta['cosine'],meta['negative'],meta['top'])
                        if cell not in sampled_cells: sample_indices.add(start+i); sampled_cells.add(cell)
                    detail=dict(index=start+i,operand=op,mode=bank['mode'],pc=bank['pc'],instruction='fsin',hardware=actual,hardware_status=f'{sw:04x}',candidate=value,metadata=meta)
                    if value!=actual or badc1:
                        failures.write((json.dumps(detail,sort_keys=True)+'\n').encode()); sample_indices.add(start+i)
                        if len(examples)<32: examples.append(dict(bank=bank['tag'],**detail))
        chosen=sorted(sample_indices); build_checks={}
        for label,binary in binaries.items():
            values,metadata,_,_=candidate.run(binary,'fsin',bank['mode'],[operands[i] for i in chosen])
            build_checks[label]=dict(values=values,metadata=metadata)
        assert all(check==build_checks['candidate_O2'] for check in build_checks.values())
        candidate.records.save(directory/'compiler_checks.json',dict(indices=chosen,builds=build_checks))
        reports.append(dict(bank=bank['tag'],counts=dict(counts),compiler_checked_rows=len(chosen),sha256={p.name:digest(p) for p in sorted(directory.iterdir())}))
        totals.update(counts); groups.setdefault(f"{bank['mode']}/PC{bank['pc']}",Counter()).update(counts)
        print(bank['tag'],dict(counts),flush=True)
    for name,expected in evidence.items(): assert digest(root/name)==expected,name
    result=dict(experiment='h1636_retained_rz_pc_transfer',status='CANDIDATE_FALSIFIED' if any(totals[l+s] for l in ('table','polynomial','fallback') for s in ('_output_misses','_C1_misses')) else 'PASS_RETAINED_FSIN_RZ_AND_RN_PC_ONLY',
        counts=dict(totals),groups={k:dict(v) for k,v in groups.items()},banks=reports,examples=examples,
        coverage_limits='External FSIN only. RZ at PC64; RN at PC24/53/64. Other instruction/control combinations are not inferred. H172 raw PC lines agree including status, but the numerical model has no new PC or full-status implementation. Fallback output-only. Overlapping retained bank appearances, not fresh/deduplicated evidence.',
        hardware_execution='none',private_ledger_access='none',canonical_default_or_paper_change='none',
        sha256=dict(script=digest(Path(__file__)),evidence=evidence,binaries={k:digest(v) for k,v in binaries.items()}))
    candidate.records.save(output/'report.json',result)
    print(result['status'],dict(totals),flush=True)


if __name__=='__main__': main()
