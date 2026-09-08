#!/usr/bin/env python3
"""Preserving, additive corpus-v1 revision for the bounded H1720/H1721 bank.

Only explicit input operands are imported, never predictions or output lanes.
The 12-million-input proposal search is not expanded into the default suite.
This builds a new directory; installation/preservation is a separate step.
"""
import argparse
import csv
import json
import shutil
import sqlite3
from collections import Counter
from pathlib import Path
from h1718_build_corpus import suite,domain


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    old=root/'corpus-suite/corpus-v1';previous=suite.verify_dataset(old)
    assert previous['corpus_id']=='x87-trig-v1-d641d37292814c79'
    bankpath=root/'tmp/ledger33/current/h1721_challenge_bank/bank.json';bank=json.loads(bankpath.read_text())
    certpath=bankpath.parent/'boundary_certificate.json';cert=json.loads(certpath.read_text())
    ops={r['operand'] for r in bank['operands']}
    extrapath=root/'tmp/ledger33/current/h1724_challenge_bank/bank.json'
    extra=json.loads(extrapath.read_text());ops.update(r['operand'] for r in extra['operands'])
    for row in cert['stages']:
        se,sig=(int(w,16) for w in row['operand'].split())
        for sign in (0,0x8000):
            for d in (-1,0,1):
                if 1<<63<=sig+d<1<<64:ops.add(f'{se|sign:04x} {sig+d:016x}')
    for row in cert['relations']:
        se,sig=row['operand'].split()
        for sign in (0,0x8000):ops.add(f'{int(se,16)|sign:04x} {sig}')
    out.mkdir(parents=True,exist_ok=False);shutil.copyfile(old/'catalog.sqlite',out/'catalog.sqlite')
    db=sqlite3.connect(out/'catalog.sqlite');db.execute('PRAGMA cache_size=-131072')
    sources=json.loads((old/'sources.json').read_text());index=len(sources);assert index<62
    db.executemany('INSERT INTO operands VALUES(?,?,?) ON CONFLICT(op) DO UPDATE SET profiles=profiles|excluded.profiles,sources=sources|excluded.sources',
        ((op,1,1<<index) for op in sorted(ops)));db.commit()
    # Verify the old content and memberships against the attached immutable
    # previous database. This is set inclusion, not a size-only check.
    db.execute('ATTACH DATABASE ? AS previous',(str(old/'catalog.sqlite'),))
    lost=db.execute('SELECT count(*) FROM previous.operands p LEFT JOIN main.operands n ON p.op=n.op WHERE n.op IS NULL OR (n.profiles&p.profiles)!=p.profiles OR (n.sources&p.sources)!=p.sources').fetchone()[0]
    assert lost==0
    assert db.execute('SELECT count(*) FROM previous.operands').fetchone()[0]==previous['profiles']['full']['operands']
    counts=Counter();domains=Counter();smoke=Counter()
    with suite.gzwrite(out/'operands.tsv.gz') as f:
        w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(('se','sig','profiles','sources'))
        for op,flags,mask in db.execute('SELECT op,profiles,sources FROM main.operands ORDER BY op'):
            se,sig=op.split();w.writerow((se,sig,flags,f'{mask:x}'));counts['full']+=1
            if flags&1:counts['core']+=1;domains[domain(op)]+=1
            if flags&2:counts['smoke']+=1;smoke[domain(op)]+=1
    db.close()
    sources.append(dict(index=index,name='theoretical.h1720_h1721_policy2_cut_boundaries',operand_appearances=len(ops),
        profile='core_and_full',provenance='Bounded independently predicted stage-boundary panel, signed +/-1 neighbours, reduction brackets and exponent/dispatch controls. Proposal search itself is not expanded.',
        evidence=[dict(path=str(p.relative_to(root)),sha256=suite.digest(p)) for p in (bankpath,certpath,extrapath)]))
    suite.save(out/'sources.json',sources);shutil.copyfile(old/'mandatory-misses.json',out/'mandatory-misses.json')
    suite.save(out/'coverage.json',dict(unique_operands=dict(counts),previous_unique_operands=previous['profiles']['full']['operands'],
        added_unique_operands=counts['full']-previous['profiles']['full']['operands'],core_domains=dict(domains),smoke_domains=dict(smoke),
        input_appearances=sum(s['operand_appearances'] for s in sources),capture_tuples_all_RC_PC={k:v*36 for k,v in counts.items()},
        capture_tuples_PC64={k:v*12 for k,v in counts.items()},scope='Explicit additive finite adversarial input union; labels are separate per-CPU datasets.'))
    files={name:suite.digest(out/name) for name in ('operands.tsv.gz','sources.json','coverage.json','mandatory-misses.json')}
    manifest=dict(previous,revision='H1723-confidence',corpus_id='x87-trig-v1-'+files['operands.tsv.gz'][:16],
        previous_corpus_id=previous['corpus_id'],files=files,builder_sha256=suite.digest(Path(__file__)),
        profiles={k:dict(operands=v,default_capture_tuples=v*(12 if k=='full' else 36),all_control_capture_tuples=v*36,pc64_capture_tuples=v*12) for k,v in counts.items()})
    suite.save(out/'MANIFEST.json',manifest)
    suite.save(out/'preservation.json',dict(previous_manifest_sha256=suite.digest(old/'MANIFEST.json'),missing_operands_or_memberships=lost,
        imported_bounded_inputs=len(ops),new_full_operands=counts['full']-previous['profiles']['full']['operands']))
    print(json.dumps(dict(corpus_id=manifest['corpus_id'],counts=dict(counts),sources=len(sources),missing_previous_memberships=lost)),flush=True)


if __name__=='__main__':main()
