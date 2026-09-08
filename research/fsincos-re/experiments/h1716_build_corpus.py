#!/usr/bin/env python3
"""Build a deduplicated, CPU-independent full input corpus from public evidence.

Only explicit, authenticated retained inputs and declared software/campaign
fixtures are read. No supplemental/private source or directory discovery is
used. Historical labels are not copied or synthesized by this builder.
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite
import h1709_paired_retained_census as paired

CURRENT='tmp/ledger33/current/'
LOCKS={CURRENT+'h1713_paired_regression/report.json':'e4d451aa8f8f86a032826ca84a9672c38d5d5113d6291762c675f2e3aa5266cc',
    CURRENT+'h1713_standalone_regression/report.json':'12ca6d515b1fa9270c345f6292f5418235864aa30d92d37c4e3e52f8b25c3cb2',
    'transfer-tests/h1712/FREEZE.json':'3138415249016c51047ad56110826c2f700e7ec09037c292de22bae35e4a36fa',
    'transfer-tests/h1714/FREEZE.json':'e5bfa95ffde09a8756fb7912d3d919b574a35ba277628bb3fd1ae53eb42c1563'}


def domain(op):
    se,sig=(int(w,16) for w in op.split());ef=se&0x7fff
    if ef and not sig>>63:return 'invalid_encoding'
    if not sig:return 'zero'
    if ef==0x7fff:return 'infinity' if sig==1<<63 else 'qnan' if sig&(1<<62) else 'snan'
    if ef==0:return 'pseudo_denormal' if sig>>63 else 'subnormal'
    path=paired.classify(op)
    if path.endswith('polynomial'):
        if path.startswith('direct'):return path+'.e'+str(ef-16383)
        return path
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    for name,sha in LOCKS.items():assert suite.digest(root/name)==sha,name
    # The new proposal collection must already be frozen. Otherwise building
    # a public aggregate would pollute its pending freshness search.
    fresh=json.loads((root/'transfer-tests/h1715/FREEZE.json').read_text())
    assert fresh['capture_state']=='FROZEN_UNOPENED'
    out.mkdir(parents=True);db=sqlite3.connect(out/'catalog.sqlite')
    db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=OFF')
    db.execute('CREATE TABLE operands(op TEXT PRIMARY KEY,profiles INTEGER,sources INTEGER) WITHOUT ROWID')
    sources=[];paths=set();total=0
    def add_source(name,path,ops,core=False,provenance='retained_input'):
        nonlocal total
        assert len(sources)<62 and not str(path).startswith(('supplemental/','src/standalone/'))
        index=len(sources);flag=1<<index;count=0;batch=[]
        for op in ops:
            op=op.lower().strip();assert re.fullmatch('[0-9a-f]{4} [0-9a-f]{16}',op),name
            batch.append((op,int(core),flag));count+=1
            if len(batch)==10000:
                db.executemany('INSERT INTO operands VALUES(?,?,?) ON CONFLICT(op) DO UPDATE SET profiles=profiles|excluded.profiles,sources=sources|excluded.sources',batch);batch=[]
        if batch:db.executemany('INSERT INTO operands VALUES(?,?,?) ON CONFLICT(op) DO UPDATE SET profiles=profiles|excluded.profiles,sources=sources|excluded.sources',batch)
        db.commit();total+=count
        sources.append(dict(index=index,name=name,path=str(path),sha256=suite.digest(root/path),operand_appearances=count,
            profile='core_and_full' if core else 'full',provenance=provenance))
        print(name,count,'input appearances',flush=True)
    for kind in ('paired','standalone'):
        directory=root/CURRENT/('h1713_'+kind+'_regression');report=json.loads((directory/'report.json').read_text())
        for name,sha in sorted(report['sha256']['reports'].items()):
            path=directory/name;assert suite.digest(path)==sha,name;record=json.loads(path.read_text())
            if not isinstance(record,dict) or 'bank' not in record:continue
            bank=record['bank'];input_path=bank['inputs']
            if input_path is None:
                input_path='stageA/ties_comb7.txt'
                assert suite.digest(root/input_path)==report['sha256']['evidence'][input_path]
                with (root/input_path).open() as f:words=sorted({line.split()[0] for line in f if line.strip()})
                assert len(words)==1947982
                ops=('3ffc '+word for word in words)
                add_source('retained.paired.comb7',input_path,ops,provenance=bank['provenance']);paths.add(input_path)
            elif input_path not in paths:
                assert suite.digest(root/input_path)==report['sha256']['evidence'][input_path]
                with (root/input_path).open() as f:add_source('retained.'+kind+'.'+bank['tag'],input_path,f,provenance=bank.get('provenance','authenticated_retained_standalone_input'))
                paths.add(input_path)
    for campaign in ('h1712','h1714','h1715'):
        path=Path('transfer-tests')/campaign/'manifest.json';freeze=json.loads((root/path.parent/'FREEZE.json').read_text())
        assert suite.digest(root/path)==freeze['sha256']['manifest']
        rows=json.loads((root/path).read_text());ops=sorted({r['operand'] for r in rows})
        add_source(campaign+'.adversarial',path,ops,True,'frozen_campaign_inputs; observation state remains separate')
    path=Path(CURRENT)/'h1713_promotion_checks_v2/inputs.json'
    add_source('structured.raw80_controls',path,json.loads((root/path).read_text()),True,'software fixture; not a new hardware claim')
    path=Path(CURRENT)/'h1638_tiny_c_transfer/report.json';report=json.loads((root/path).read_text())
    ops=sorted({r['operand'] for kind in ('frontier','legacy') for r in report['frontier_checks'][kind]['candidate_O2']})
    add_source('historical.frontier81_and_legacy53',path,ops,True,'input union of authenticated historical frontier/legacy replay; no synthesized observations')
    path=Path('capture-kit/crossgen/inputs.txt')
    with (root/path).open() as f:add_source('historical.crossgen.borrow_gate',path,f,False,'public input snapshot; historical labels and claims not imported')
    # Smoke samples preserve domain diversity and both signs, rather than
    # merely taking the first few lexicographically sorted raw operands.
    smoke_counts=Counter();smoke=[]
    for (op,) in db.execute('SELECT op FROM operands WHERE profiles&1 ORDER BY op'):
        key=domain(op)+('.negative' if int(op[:4],16)&0x8000 else '.positive')
        if smoke_counts[key]<2:smoke_counts[key]+=1;smoke.append(op)
    db.executemany('UPDATE operands SET profiles=profiles|2 WHERE op=?',((op,) for op in smoke));db.commit()
    counts=Counter();domains=Counter()
    with suite.gzwrite(out/'operands.tsv.gz') as f:
        w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(('se','sig','profiles','sources'))
        for op,flags,mask in db.execute('SELECT op,profiles,sources FROM operands ORDER BY op'):
            se,sig=op.split();w.writerow((se,sig,flags,f'{mask:x}'));counts['full']+=1
            if flags&1:counts['core']+=1;domains[domain(op)]+=1
            if flags&2:counts['smoke']+=1
    db.close();suite.save(out/'sources.json',sources);suite.save(out/'coverage.json',dict(unique_operands=dict(counts),
        input_appearances=total,deduplicated_appearances=total-counts['full'],core_domains=dict(domains),smoke_domains=dict(smoke_counts),
        capture_tuples_all_RC_PC={k:v*36 for k,v in counts.items()},
        scope='FSIN, FCOS, FSINCOS; all four RC and PC24/53/64 by default. Source membership means test selection, not correctness or observation status.'))
    files={name:suite.digest(out/name) for name in ('operands.tsv.gz','sources.json','coverage.json')}
    corpus_id='x87-trig-v1-'+files['operands.tsv.gz'][:16]
    suite.save(out/'MANIFEST.json',dict(schema='x87-suite-v1',kind='input_corpus',corpus_id=corpus_id,files=files,
        profiles={k:dict(operands=v,default_capture_tuples=v*36) for k,v in counts.items()},
        instructions=list(suite.INSNS),rounding_modes=list(suite.MODES),precision_controls=list(suite.PCS),
        contract=dict(exceptions_masked='3f',depth=1,prior='clear',input='raw80 se+sig',case_id='n1-instruction-mode-pc-sesig'),
        private_material_included=False,model_predictions_included=False,hardware_labels_included=False,
        builder_sha256=suite.digest(Path(__file__)),source_membership_bits='sources.json index, least-significant bit first',
        limits='Full means the explicit union of retained promoted regression input banks and listed fixtures, not every historical experiment or exhaustive raw80 enumeration. Public inputs only; CPU observations are separate.'))
    print(json.dumps(dict(corpus_id=corpus_id,unique_operands=dict(counts),tuples={k:v*36 for k,v in counts.items()},sources=len(sources))),flush=True)


if __name__=='__main__':main()
