#!/usr/bin/env python3
"""Deduplicate attributable coverage; replay-host identity is not label origin.

Legacy i7 banks get a separate instruction/RC projection: without an
authenticated per-row CW they do not fill PC24/53/64 cells by inference.
Unmapped older campaigns are reported, not silently counted as absent tests.
"""
import argparse
import json
import sqlite3
from collections import Counter,defaultdict
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite
from h1719_run_saved_suite import digest,save


def family(op):
    se,sig=map(lambda s:int(s,16),op.split());e=(se&0x7fff)-16383
    if (se&0x7fff) and not sig>>63:return 'invalid'
    if (se&0x7fff)==0x7fff:return 'special'
    if not sig:return 'zero'
    if not se&0x7fff:return 'pseudo_denormal' if sig>>63 else 'subnormal'
    if e>=63:return 'range_C2'
    if e<-32:return 'direct_tiny'
    if e<-2:return 'direct_polynomial_e'+str(e)
    if e<-1 or (e==-1 and sig<0xc90fdaa22168c234):return 'direct_table'
    return 'reduced_e'+str(e)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    corpus=root/'corpus-suite/corpus-v1';m=suite.verify_dataset(corpus)
    with sqlite3.connect('file:'+str(corpus/'catalog.sqlite')+'?mode=ro',uri=True) as db:
        core={op for op, in db.execute('SELECT op FROM operands WHERE profiles & 1')}
    assert len(core)==m['profiles']['core']['operands']
    families={op:family(op) for op in core};grouped=defaultdict(set);sources={}
    for name in ('h1712-h1714-skylake','h1715-skylake','review-20260905-skylake'):
        d=root/'corpus-suite/references'/name;meta=json.loads((d/'cpu.json').read_text())
        identity=meta.get('context_id',json.dumps(meta['reported'],sort_keys=True) if 'reported' in meta else '')
        key=meta['identity_kind']+':'+identity
        rows={r['case_id'] for r in suite.observations(d)};grouped[key].update(rows)
        sources[name]=dict(rows=len(rows),manifest_sha256=digest(d/'MANIFEST.json'),group=key)
    coverage=[]
    for key,cases in grouped.items():
        counts=Counter();cells=Counter();matched=set()
        for case in cases:
            insn,mode,pc,op=suite.decode_case(case)
            if op in core:
                counts[(insn,mode,pc)]+=1;cells[(families[op],insn,mode,pc)]+=1;matched.add(case)
        coverage.append(dict(identity_group=key,unique_observed_tuples=len(cases),core_observed_tuples=len(matched),
            core_cells=[dict(instruction=i,mode=r,pc=p,observed=counts[i,r,p],not_established_in_this_group=len(core)-counts[i,r,p])
                for i in suite.INSNS for r in suite.MODES for p in suite.PCS],
            family_cells=[dict(family=f,instruction=i,mode=r,pc=p,observed=n) for (f,i,r,p),n in sorted(cells.items())]))
    replay=root/'tmp/ledger33/current/h1719_two_host_replay/i7-bulk/results'
    inv=json.loads((replay/'inventory.json').read_text());snap=root/'tmp/ledger33/current/h1717_i7_inputs'
    proof=json.loads((snap/'SNAPSHOT.json').read_text())['files'];hits={};legacy=defaultdict(set)
    mapped=[];unmapped=[]
    for job in inv['jobs']:
        name=Path(job['inputs']).name
        if name not in proof:unmapped.append(job);continue
        if name not in hits:
            path=snap/name;assert digest(path)==proof[name]['sha256']
            with path.open() as f:hits[name]={line.strip().lower() for line in f if line.strip().lower() in core}
            print(name,'core operands',len(hits[name]),flush=True)
        legacy[job['instruction'],job['mode']].update(hits[name]);mapped.append(job)
    out.mkdir(parents=True,exist_ok=False)
    report=dict(status='ATTRIBUTABLE_COVERAGE_AUDITED',corpus_id=m['corpus_id'],core_operands=len(core),
        core_cartesian_tuples=len(core)*36,core_families=dict(sorted(Counter(families.values()).items())),
        normalized_sources=sources,coverage=coverage,
        i7_legacy_instruction_RC_projection=[dict(instruction=i,mode=r,unique_core_operands=len(legacy[i,r]),
            PC_attribution='not upgraded from historical labels') for i in suite.INSNS for r in suite.MODES],
        legacy_mapped_jobs=len(mapped),legacy_unmapped_jobs=unmapped,missing_mode_files=inv['unavailable_modes'],
        limits=['Missing bank files are not missing tuple counts.',
            'This is a lower bound from authenticated mapped evidence, not an assertion that other historical rows were never observed.',
            'Historical FMS and direct CPUID identity groups remain separate.',
            'No absent PC cell is credited through assumed numerical PC invariance.',
            'Execution of shared labels on a second CPU does not create second-CPU hardware observations.'],
        hardware_execution='none',candidate_changed=False,paper_changed=False)
    save(out/'report.json',report)
    print(json.dumps(dict(core_operands=len(core),groups=[(c['identity_group'],c['core_observed_tuples']) for c in coverage],legacy_mapped_jobs=len(mapped),legacy_unmapped_jobs=len(unmapped))),flush=True)


if __name__=='__main__':main()
