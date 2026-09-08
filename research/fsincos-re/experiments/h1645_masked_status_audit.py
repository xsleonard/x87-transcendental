#!/usr/bin/env python3
"""Audit the class-based status algebra on cached data and encoding partitions.

H1641's previously null fields are retrospective checks, NOT fresh predictions.
H1637 contributes flags only here; supplied observed endpoints/C1 receive no
new independent numerical credit. H1401 standalone rows use the fixed C graph.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter,defaultdict
from dataclasses import asdict
from pathlib import Path
import h1645_masked_status_model as model
import h1644_load_status_causal_audit as provenance
import h1638_tiny_c_transfer as candidate
import h1634_independent_table_certificate as reader
from h1640_remaining_scope_freshness import save

TINY='tmp/ledger33/current/h1637_tiny_closed_form_audit/'
KIT='transfer-tests/h1641/'
LOCKS={**provenance.LOCKS,
    TINY+'report.json':'a18fb1a7a9dad745e7fea87430bfa1820273a52d43e99a175a8de5becb0d7158',
    KIT+'FREEZE.json':'066ac4f086d9132ba157195af02a3aaffaccb4f3e05c5337a4689b634f35f833',
    KIT+'manifest.json':'453ecfe5ab81dc49c23cd045d85af341df3e8e6b2125cca6dd7c064568d06a84',
    'tmp/ledger33/current/h1642_score_remaining_scope/report.json':'8f19ff7e9a95df22824497abec43b765ee73d832296444bed9976b86b7092293',
    'tmp/ledger33/current/h1638_tiny_c_transfer/report.json':'db6c8cbc1e0e2c9acdb54da5e1e381407a6b8c5f6f62cc7b1c52c4d90f8510e0',
}


def decoded(op): return tuple(int(w,16) for w in op.replace(':',' ').split())


def software_partition():
    counts=model.partition_counts(); assert sum(counts.values())==1<<80
    # Independent classification predicates on every exponent/sign and all
    # Boolean predicate boundaries, including zero/max nonzero payloads.
    tested=0
    for e in range(0x8000):
        for sig in (0,1,(1<<62)-1,1<<62,(1<<63)-1,1<<63,(1<<63)+1,(3<<62)-1,3<<62,(1<<64)-1):
            integer=bool(sig>>63); fraction=sig&((1<<63)-1); quiet=bool(sig&(1<<62))
            predicates=dict(zero=e==0 and sig==0,
                denormal=e==0 and not integer and sig!=0,pseudo_denormal=e==0 and integer,
                unsupported=e!=0 and not integer,infinity=e==0x7fff and integer and fraction==0,
                quiet_nan=e==0x7fff and integer and quiet,
                signaling_nan=e==0x7fff and integer and not quiet and fraction!=0,
                normal_in_range=0<e<0x403e and integer,normal_out_of_range=0x403e<=e<0x7fff and integer)
            assert sum(predicates.values())==1
            for sign in (0,0x8000):
                assert predicates[model.classify(e|sign,sig)]
                tested+=1
    # Exhaust all sticky-flag combinations and TOP values in software only.
    state_checks=0
    for top in range(8):
        for flags in range(64):
            for sf in (0,0x40):
                if sf and not flags&1: continue
                before=(top<<11)|flags|sf|0x4700
                normal=model.masked(0x0001,model.B63,'fsin',before_status=before,before_tag=1<<top)
                assert normal.new_exception_flags==0x20 and normal.status_bits&0x7f==(flags|sf|0x20)
                assert normal.top==top and normal.physical_abridged_tag==1<<top
                empty=model.masked(0x0001,model.B63,'fcos',before_status=before,before_tag=0)
                assert empty.output==model.INDEFINITE and empty.status_bits&0x7f==(flags|sf|0x41)
                assert empty.physical_abridged_tag==1<<top and empty.C1==0 and empty.C2 is None
                state_checks+=2
    for cw,sw in ((0x037e,0x3800),(0x017f,0x3800),(0x037f,0x3880),(0x037f,0xb800)):
        try: model.masked(1,model.B63,'fsin',control_word=cw,before_status=sw)
        except NotImplementedError: pass
        else: raise AssertionError('Unsupported state accepted')
    return dict(encodings_partitioned=str(1<<80),class_counts={k:str(v) for k,v in counts.items()},
        predicate_boundary_checks=tested,sticky_top_software_checks=state_checks,hardware_credit=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    digest=reader.digest
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    software=software_partition()
    freeze=json.loads((root/KIT/'FREEZE.json').read_text())
    predictions=json.loads((root/KIT/'manifest.json').read_text())
    oldreport=json.loads((root/'tmp/ledger33/current/h1642_score_remaining_scope/report.json').read_text())
    counts=Counter(); cells=defaultdict(Counter); misses=[]; scored=[]
    for lane,metadata in sorted(freeze['lanes'].items()):
        rows=[r for r in predictions if r['lane']==lane]
        path=root/KIT/'hardware-output'/f'{lane}.txt'
        assert digest(path)==oldreport['sha256']['raw_outputs'][path.name]
        lines=path.read_text().splitlines(); assert len(lines)==len(rows)==268
        for r,line in zip(rows,lines):
            value,sw=reader.raw(line,True)
            result=model.masked(*decoded(r['operand']),r['instruction'],finite_output=r['output'],finite_C1=r['C1'])
            expected='C2' if result.response=='C2' else result.output
            good=expected==value and result.agrees_with_status(sw)
            item=dict(case_id=r['case_id'],operand=r['operand'],instruction=r['instruction'],mode=r['mode'],
                precision_control=r['precision_control'],hardware=value,SW=f'{sw:04x}',result=asdict(result),exact=good,
                flags_previously_predicted=r['exception_flags'] is not None,C1_previously_predicted=r['C1'] is not None)
            if not good: misses.append(item)
            scored.append(item)
            measures=dict(rows=1,output_checks=1,known_status_checks=1,exception_mask_checks=1,
                C1_checks=int(result.C1 is not None),retrospective_new_flag_checks=int(r['exception_flags'] is None),
                retrospective_new_C1_checks=int(r['C1'] is None and result.C1 is not None))
            for k,v in measures.items(): counts['h1641/'+k]+=v; cells[result.encoding_class][k]+=v
    tiny=json.loads((root/TINY/'report.json').read_text())
    for name,sha in tiny['sha256']['evidence'].items(): assert digest(root/name)==sha,name
    prepared=root/TINY/'prepared.json'
    assert digest(prepared)==tiny['sha256']['artifacts']['prepared.json']
    smallest=[]; inputs_cache={}
    for bank in json.loads(prepared.read_text())['inventories']:
        if bank['inputs'] not in inputs_cache: inputs_cache[bank['inputs']]=(root/bank['inputs']).read_text().splitlines()
        inputs=inputs_cache[bank['inputs']]; lines=(root/bank['capture']).read_text().splitlines()
        assert len(inputs)==len(lines)==bank['count']
        for i,(op,line) in enumerate(zip(inputs,lines)):
            value,sw=reader.raw(line,True); se,sig=decoded(op)
            result=model.masked(se,sig,bank['instruction'],finite_output=value,finite_C1=(sw>>9)&1)
            # This bank credits FLAGS ONLY; values and C1 supplied from the
            # raw record cannot establish an independent numerical comparison.
            assert result.new_exception_flags==(sw&0x3f)
            counts['h1637/exception_mask_checks']+=1
            if (se&0x7fff)==1 and sig==model.B63:
                smallest.append(dict(bank=bank['tag'],row=i,operand=op,output=value,SW=f'{sw:04x}',flags=result.new_exception_flags))
    raw=provenance.old.parse_state(root/provenance.STATE/'raw-state-output.txt')
    identities=provenance.old.read_tsv(root/provenance.STATE/'identity-manifest.tsv')
    batches=defaultdict(list)
    for ident,r in zip(identities,raw):
        if r['INSN'] in ('fsin','fcos'): batches[(r['INSN'],r['MODE'])].append((ident,r))
    binary=root/'tmp/ledger33/current/h1638_tiny_c_transfer/candidate_O2'
    c_report=json.loads((root/'tmp/ledger33/current/h1638_tiny_c_transfer/report.json').read_text())
    assert digest(binary)==c_report['sha256']['binaries']['candidate_O2']
    states=[]
    for (insn,mode),batch in sorted(batches.items()):
        values,meta,_=candidate.run(binary,insn,mode,[r['operand'] for r,_ in batch])
        for i,((ident,r),value) in enumerate(zip(batch,values)):
            result=model.masked(*decoded(ident['operand']),insn,finite_output=value,finite_C1=meta.get(i,{}).get('C1'),
                before_status=int(r['B_SW'],16),before_tag=int(r['B_FTW'],16),control_word=int(r['B_CW'],16))
            good=result.output==r['A_R0'] and result.agrees_with_status(int(r['A_SW'],16))
            good=good and result.top==int(r['A_TOP']) and result.physical_abridged_tag==int(r['A_FTW'],16)
            good=good and all(r[f'A_R{j}']==r[f'B_R{j}'] for j in range(1,8))
            item=dict(case=ident['case_id'],result=asdict(result),actual_output=r['A_R0'],actual_SW=r['A_SW'],exact=good)
            states.append(item)
            if not good: misses.append(item)
            counts['h1401/standalone_state_checks']+=1
    out.mkdir(parents=True); save(out/'h1641_score.json',scored); save(out/'h1401_states.json',states)
    report=dict(experiment='h1645_masked_status_audit',status='PASS_CACHED_CLASS_STATUS' if not misses else 'CLASS_STATUS_FALSIFIED',
        counts=dict(counts),class_counts={k:dict(v) for k,v in cells.items()},misses=misses,software=software,
        smallest_normal_observations=smallest,hardware_execution='none',candidate_arithmetic_change='none',
        private_ledger_access='none',paper_or_default_change='none',
        claim_boundary='Post-hoc encoding-class status algebra, not new prospective proof. Class partition is all-encoding software logic, not silicon correctness. C0/C3, special C2, range C1, unmasked/pending/reserved-control and unobserved empty-stack behavior remain physical evidence gaps.',
        sha256=dict(script=digest(Path(__file__)),model=digest(root/'experiments/h1645_masked_status_model.py'),evidence=LOCKS,
            h1641_score=digest(out/'h1641_score.json'),h1401_states=digest(out/'h1401_states.json')))
    save(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('status','counts','misses')},sort_keys=True),flush=True)


if __name__=='__main__': main()
