#!/usr/bin/env python3
"""Additive corpus-v1 revision: explicit public adversarial banks, never labels.

The previous content-addressed release is retained. No private directory is
searched, and architectural-state operands do not import their state contracts.
Exploratory billion-input searches remain recipes, not expanded default tests.
"""
import argparse
import csv
import gzip
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite
from h1716_build_corpus import domain

CAMPAIGNS=('h1400','h1406','h1408','h1410','h1412','h1472','h1477','h1488',
    'h1566','h1570','h1573','h1580','h1587','h1624','h1641','h1649','h1656',
    'h1662','h1670','h1675','h1680','h1694','h1712','h1714','h1715')
EARLY={'h1400':['core-transfer.tsv','architecture-semantics.tsv'],
    'h1406':['input-history.tsv'],'h1408':['input-history-controls.tsv'],
    'h1410':['producer-class.tsv'],'h1412':['prelude-transitions.tsv']}
PROPOSALS=('h1579_equality_bank','h1586_stream_control_plateaus',
    'h1622_fixed_candidate_challenge_bank_v2','h1639_remaining_scope_proposals',
    'h1692_remaining_center_state_bank','h1711_paired_challenge_bank',
    'h1714_rounding_challenge','h1715_challenge_bank')
RAW=re.compile(r'[0-9a-f]{4} [0-9a-f]{16}')


def extract(value):
    """Only explicit operand fields; never collect predicted output values."""
    if isinstance(value,list):
        for x in value:yield from extract(x)
    elif isinstance(value,dict):
        op=value.get('operand')
        if isinstance(op,str) and RAW.fullmatch(op.lower().replace(':',' ')):
            yield op.lower().replace(':',' ')
        for key,x in value.items():
            if key not in ('predictions','prediction','expected','hardware','model','outputs'):
                yield from extract(x)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    old=root/'corpus-suite/releases/h1716-v1-original/corpus-v1';previous=suite.verify_dataset(old)
    assert previous['corpus_id']=='x87-trig-v1-40620ee30e943c81'
    shutil.copyfile(old/'catalog.sqlite',out/'catalog.sqlite')
    db=sqlite3.connect(out/'catalog.sqlite');db.execute('PRAGMA journal_mode=OFF')
    db.execute('PRAGMA synchronous=OFF');db.execute('PRAGMA cache_size=-131072')
    sources=json.loads((old/'sources.json').read_text());initial=db.execute('SELECT count(*) FROM operands').fetchone()[0]
    assert initial==previous['profiles']['full']['operands']
    def add(name,ops,provenance,core=False,records=None):
        index=len(sources);assert index<62;batch=[];count=0
        for op in ops:
            op=op.lower().strip();assert RAW.fullmatch(op),(name,op)
            count+=1;batch.append((op,int(core),1<<index))
            if len(batch)==20000:
                db.executemany('INSERT INTO operands VALUES(?,?,?) ON CONFLICT(op) DO UPDATE SET profiles=profiles|excluded.profiles,sources=sources|excluded.sources',batch);batch=[]
        if batch:db.executemany('INSERT INTO operands VALUES(?,?,?) ON CONFLICT(op) DO UPDATE SET profiles=profiles|excluded.profiles,sources=sources|excluded.sources',batch)
        db.commit();sources.append(dict(index=index,name=name,operand_appearances=count,
            profile='core_and_full' if core else 'full',provenance=provenance,evidence=records or []))
        print(name,count,'appearances',flush=True)
    # These remote banks were missing from the first release. Explicit names
    # prevent accidental inclusion of implementation/private data.
    directory=root/'tmp/ledger33/current/h1717_i7_inputs'
    inventory=json.loads((directory/'SNAPSHOT.json').read_text())
    for name,meta in inventory['files'].items():
        path=directory/name;assert suite.digest(path)==meta['sha256']
        with path.open() as f:add('i7.'+name.removesuffix('_inputs.txt'),f,
            'retained_public_input_snapshot; historical labels separate',records=[dict(path=str(path.relative_to(root)),**meta)])
        assert sources[-1]['operand_appearances']==meta['rows']
    ops=set();records=[]
    for campaign in CAMPAIGNS:
        d=root/'transfer-tests'/campaign
        names=EARLY.get(campaign,['manifest.json' if (d/'manifest.json').exists() else 'manifest.tsv'])
        for name in names:
            path=d/name
            if path.suffix=='.json':selected=set(extract(json.loads(path.read_text())))
            else:
                with path.open() as f:selected={r['operand'].lower().replace(':',' ') for r in csv.DictReader(f,delimiter='\t')}
            assert selected,(campaign,name);ops.update(selected)
            records.append(dict(path=str(path.relative_to(root)),sha256=suite.digest(path),unique_operands=len(selected)))
    add('public.frozen_campaign_operand_union',sorted(ops),
        'explicit H1400-H1715 manifests; only raw inputs transferred into numerical depth1/clear/masked contract, not state tests or labels',True,records)
    ops=set();records=[]
    for name in PROPOSALS:
        path=root/'tmp/ledger33/current'/name/'bank.json';selected=set(extract(json.loads(path.read_text())))
        assert selected,name;ops.update(selected)
        records.append(dict(path=str(path.relative_to(root)),sha256=suite.digest(path),unique_operands=len(selected)))
    add('public.theoretical_proposal_union',sorted(ops),'all explicit bounded proposal-bank operands, including proposals not selected for fresh capture',True,records)
    path=root/'transfer-tests/review-20260905/bank/operands.txt'
    with path.open() as f:add('independent_review.stratified',f,'retained public review operands; labels remain separate',True,
        [dict(path=str(path.relative_to(root)),sha256=suite.digest(path))])
    frontier=root/'tmp/ledger33/current/h1638_tiny_c_transfer/report.json'
    report=json.loads(frontier.read_text());missops={r['operand'] for kind in ('frontier','legacy') for r in report['frontier_checks'][kind]['candidate_O2']}
    oldpaired=root/'tmp/ledger33/current/h1709_paired_retained_census/frontier.json'
    missops.update(r['operand'] for r in json.loads(oldpaired.read_text()))
    missops.update(('3ffc e79000000c3e46e7','bffc 94332f6145084ae1'))
    suite.save(out/'mandatory-misses.json',dict(operands=sorted(missops),
        meaning='Inputs that defeated earlier models, plus retained legacy controls. Presence is not a claim that the current model misses.',
        evidence=[dict(path=str(p.relative_to(root)),sha256=suite.digest(p)) for p in
            (frontier,oldpaired,root/'notes/REVIEW-20260905-independent-verification.md')]))
    add('regression.known_misses_and_legacy',sorted(missops),'mandatory core and full; original raw bits retained',True,
        [dict(path='mandatory-misses.json',sha256=suite.digest(out/'mandatory-misses.json'))])
    neighbors=set();transport=set()
    for op in missops:
        se,sig=map(lambda x:int(x,16),op.split());ef=se&0x7fff
        if not 0<ef<0x7fff or sig<1<<63:continue
        for delta in range(-16,17):
            s=sig+delta
            if not 1<<63<=s<1<<64:continue
            for sign in (0,0x8000):neighbors.add(f'{ef|sign:04x} {s:016x}')
        # Same-significand binade transports challenge all polynomial cells.
        # They are test inputs, not exact-reduction isomorphs or expected misses.
        for e in range(-32,-2):
            for delta in (-1,0,1):
                s=sig+delta
                if 1<<63<=s<1<<64:
                    for sign in (0,0x8000):transport.add(f'{e+16383|sign:04x} {s:016x}')
    add('theoretical.miss_signed_ulp_neighborhoods',sorted(neighbors),'both signs and +/-16 significand units around every mandatory finite-normal input',True)
    add('theoretical.miss_binade_transports',sorted(transport),'both signs, +/-1 significand unit, all 30 polynomial binades; not exact preimages',True)
    # Preserve every prior smoke member and make every known miss mandatory.
    db.executemany('UPDATE operands SET profiles=profiles|3 WHERE op=?',((op,) for op in missops));db.commit()
    counts=Counter();domains=Counter();smoke_domains=Counter()
    with suite.gzwrite(out/'operands.tsv.gz') as f:
        w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(('se','sig','profiles','sources'))
        for op,flags,mask in db.execute('SELECT op,profiles,sources FROM operands ORDER BY op'):
            se,sig=op.split();w.writerow((se,sig,flags,f'{mask:x}'));counts['full']+=1
            if flags&1:counts['core']+=1;domains[domain(op)]+=1
            if flags&2:counts['smoke']+=1;smoke_domains[domain(op)]+=1
    db.close();suite.save(out/'sources.json',sources)
    suite.save(out/'coverage.json',dict(unique_operands=dict(counts),previous_unique_operands=initial,
        added_unique_operands=counts['full']-initial,core_domains=dict(domains),smoke_domains=dict(smoke_domains),
        input_appearances=sum(s['operand_appearances'] for s in sources),
        capture_tuples_all_RC_PC={k:v*36 for k,v in counts.items()},capture_tuples_PC64={k:v*12 for k,v in counts.items()},
        excluded_expansions=['3.2-billion binary64 observation search','unbounded/exhaustive raw80 enumeration','billion-scale SAT/software search spaces'],
        scope='All enumerated source banks, deduplicated; not all mathematical adversarial inputs. Architectural histories are deliberately not imported.'))
    files={name:suite.digest(out/name) for name in ('operands.tsv.gz','sources.json','coverage.json','mandatory-misses.json')}
    manifest=dict(previous,schema='x87-suite-v1',revision='H1718-policy2',corpus_id='x87-trig-v1-'+files['operands.tsv.gz'][:16],
        previous_corpus_id=previous['corpus_id'],files=files,builder_sha256=suite.digest(Path(__file__)),
        profiles={k:dict(operands=v,default_capture_tuples=v*(12 if k=='full' else 36),
            all_control_capture_tuples=v*36,pc64_capture_tuples=v*12) for k,v in counts.items()},
        recommended_full_precision_controls=[64],
        limits='Explicit additive finite adversarial-input union. Old v1 release preserved by hash. All PCs remain available; PC64 is recommended for full and all three PCs for core. Neither full matrix nor expanded inputs are asserted observed. Public inputs only.')
    suite.save(out/'MANIFEST.json',manifest);print(json.dumps(dict(corpus_id=manifest['corpus_id'],counts=dict(counts),sources=len(sources))),flush=True)


if __name__=='__main__':main()
