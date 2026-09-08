"""Bounded-memory gzip corpus freeze; generic capture receives no model."""
import collections
import dataclasses
import gzip
import json
import os
from pathlib import Path
import sqlite3
import sys
from architecture import POLICY,predict
from model import ROOT
from protocol import make_line,parse_line,case_key
from compressed_guard import packed,digest
from prepare import save

HERE=Path(__file__).resolve().parent


def freeze(job,seed,generate,source_names,policy=POLICY,
           purpose='Larger independent balanced finite verification'):
    out=ROOT/'tmp/fpatan-re'/job;out.mkdir(parents=True,exist_ok=False)
    snapshot=out/'sources';snapshot.mkdir()
    names=sorted(set(source_names)|{'freeze_stream.py','architecture.py','model.py','graph_v3.py','graph_v4.py',
        'protocol.py','capture.c','compressed_guard.py','fpatan_candidate.c'})
    for name in names:
        with (snapshot/name).open('xb') as f:f.write((HERE/name).read_bytes())
    print('Pinned source snapshots',flush=True)
    sys.path.insert(0,str(ROOT/'experiments'))
    from h1725_select_full import private_signatures
    private,_=private_signatures()
    db=sqlite3.connect('file:'+str(ROOT/'tmp/ledger33/current/h1725_full_campaign/skylake/possible-history.sqlite')+'?mode=ro',uri=True)
    public={int(op.split()[1],16) for op, in db.execute('SELECT op FROM possible')};db.close()
    catalog=sqlite3.connect('file:'+str(ROOT/'corpus-suite/corpus-v1/catalog.sqlite')+'?mode=ro',uri=True)
    previous=set()
    for old in sorted(out.parent.iterdir()):
        if old==out or not (old/'MANIFEST.json').exists():continue
        m=json.loads((old/'MANIFEST.json').read_text());compressed=m.get('format')=='fpatan-gzip-v2'
        path=old/('inputs.txt.gz' if compressed else 'inputs.txt')
        with (gzip.open(path,'rt') if compressed else path.open()) as f:
            for line in f:previous.add(packed(parse_line(line)))
    print('Prior tuples checked',len(previous),flush=True)
    counts=collections.Counter();seen=set();files={}
    for name in ('inputs.txt.gz','predictions.txt.gz','categories.tsv.gz'):
        raw=(out/name).open('xb');z=gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=6);files[name]=(raw,z)
    try:
        for index,(pair,kind) in enumerate(generate()):
            if pair in seen:counts['generator_duplicate_pairs']+=1;continue
            seen.add(pair);ys,ym,xs,xm=pair;counts['generated_pairs']+=1
            if ym in private and xm in private:counts['private_possible_pair_holds']+=1;continue
            if ym in public and xm in public:counts['public_possible_pair_holds']+=1;continue
            if all(catalog.execute('SELECT 1 FROM operands WHERE op=?',(f'{s:04x} {m:016x}',)).fetchone() for s,m in ((ys,ym),(xs,xm))):
                counts['corpus_possible_pair_holds']+=1;continue
            counts['selected_pairs']+=1
            for pc in ((24,53,64) if index%257==0 else (64,)):
                for rc in ('rn','rd','ru','rz'):
                    if packed(case_key(rc,pc,*pair)) in previous:counts['previous_tuple_holds']+=1;continue
                    line=make_line(rc,pc,*pair);ident=line.split()[0]
                    se,sig,c1,flags,before=predict(*pair,rc,policy)
                    files['inputs.txt.gz'][1].write((line+'\n').encode())
                    files['predictions.txt.gz'][1].write(f'{ident} {se:04x} {sig:016x} {c1} {flags:02x} {before:02x}\n'.encode())
                    files['categories.tsv.gz'][1].write(f'{ident}\t{kind}\n'.encode());counts['rows']+=1
            if index and index%8192==0:print('Frozen pairs',index,'rows',counts['rows'],flush=True)
    finally:
        for raw,z in files.values():z.close();raw.flush();os.fsync(raw.fileno());raw.close()
        catalog.close()
    del private
    save(out/'MANIFEST.json',dict(status='FROZEN_DISCOVERY_UNOPENED',format='fpatan-gzip-v2',
        purpose=purpose,seed=seed,
        reference_host='45.32.204.118',expected_signature='00050654',expected_microcode='0x1',
        counts=dict(counts),rows=counts['rows'],policy=dataclasses.asdict(policy),C1_predictions=True,
        files={n:digest(out/n) for n in files},source_pins={n:digest(snapshot/n) for n in names},
        prior_tuple_keys_checked=len(previous),hardware_executed=False,mathematical_oracle=False,
        status_predictions=True,privacy='Private details remain local and unpublished',
        limits='Prospective verification, not exhaustive proof of all raw80 pairs.'))
    print(json.dumps(dict(counts)),flush=True)
