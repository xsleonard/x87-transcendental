"""Reusable local finite FPATAN bank freezer. Never executes hardware.

The private comparison is aggregate-only; all input/candidate source snapshots
and unopened predictions are immutable per-job. Legacy source paths/hashes
from private material are never exported or transferred.
"""
import collections
import dataclasses
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from model import ROOT,value,encode
from protocol import make_line,validate_inputs,case_key
from prepare import save,digest

HERE=Path(__file__).resolve().parent


def freeze(job,seed,generate,predictor,program,source_names,alternatives=None,*,
           encoding_predictor=None,mathematical_oracle=True,all_pc=False):
    out=ROOT/'tmp/fpatan-re'/job;out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(ROOT/'experiments'))
    from h1725_select_full import private_signatures
    private,_=private_signatures()
    hist=ROOT/'tmp/ledger33/current/h1725_full_campaign/skylake/possible-history.sqlite'
    db=sqlite3.connect('file:'+str(hist)+'?mode=ro',uri=True)
    public={int(op.split()[1],16) for (op,) in db.execute('SELECT op FROM possible')};db.close()
    catalog=sqlite3.connect('file:'+str(ROOT/'corpus-suite/corpus-v1/catalog.sqlite')+'?mode=ro',uri=True)
    prior=set()
    for old in sorted(out.parent.iterdir()):
        if old!=out and (old/'MANIFEST.json').exists():
            _,keys=validate_inputs((old/'inputs.txt').read_text());prior.update(keys)
    counts=collections.Counter();lines=[];predictions=[];categories={};seen=set();altrows=[];statuses={}
    alternatives=alternatives or {}
    for index,(pair,kind) in enumerate(generate()):
        if pair in seen:counts['generator_duplicate_pairs']+=1;continue
        seen.add(pair);ys,ym,xs,xm=pair;counts['generated_pairs']+=1
        if ym in private and xm in private:counts['private_possible_pair_holds']+=1;continue
        if ym in public and xm in public:counts['public_possible_pair_holds']+=1;continue
        if all(catalog.execute('SELECT 1 FROM operands WHERE op=?',(f'{s:04x} {m:016x}',)).fetchone() for s,m in ((ys,ym),(xs,xm))):
            counts['corpus_possible_pair_holds']+=1;continue
        before=None if encoding_predictor else predictor(*pair,program);counts['selected_pairs']+=1
        others={name:predictor(*pair,p) for name,p in alternatives.items()}
        for pc in ((24,53,64) if all_pc or index%61==0 else (64,)):
            for rc in ('rn','rd','ru','rz'):
                if case_key(rc,pc,*pair) in prior:counts['previous_tuple_holds']+=1;continue
                line=make_line(rc,pc,*pair);ident=line.split()[0]
                if encoding_predictor:
                    se,sig,c1,after_flags,before_flags=encoding_predictor(*pair,rc,program)
                    statuses[ident]={'after_exceptions':after_flags,'before_exceptions':before_flags}
                else:
                    se,sig=encode(before,rc);c1=int(abs(value(se,sig))>abs(before))
                lines.append(line);predictions.append(f'{ident} {se:04x} {sig:016x} {c1}');categories[ident]=kind
                if others:altrows.append(dict(id=ident,predictions={name:[*encode(v,rc),int(abs(value(*encode(v,rc)))>abs(v))] for name,v in others.items()}))
        if index and index%2000==0:print('prepared',index,flush=True)
    del private;catalog.close()
    for name,rows in (('inputs.txt',lines),('predictions.txt',predictions)):
        with (out/name).open('x') as f:f.write('\n'.join(rows)+'\n')
    validate_inputs((out/'inputs.txt').read_text());save(out/'categories.json',categories)
    files=['inputs.txt','predictions.txt','categories.json','math-oracle.txt']
    if statuses:save(out/'status-predictions.json',statuses);files.append('status-predictions.json')
    if alternatives:save(out/'alternatives.json',altrows);files.append('alternatives.json')
    if mathematical_oracle:
        with (out/'inputs.txt').open('rb') as source,(out/'math-oracle.txt').open('xb') as dest:
            subprocess.run(['/private/tmp/fpatan-math-oracle'],stdin=source,stdout=dest,check=True)
        assert all(l.split()[-1]=='CERTIFIED' for l in (out/'math-oracle.txt').read_text().splitlines())
    else:
        # No mathematical oracle is claimed for an architectural encoding test.
        with (out/'math-oracle.txt').open('x') as dest:
            for line in lines:dest.write(f'{line.split()[0]} 0000 0000000000000000 NOT_APPLICABLE\n')
    snapshot=out/'sources';snapshot.mkdir()
    names=sorted(set(source_names)|{'freeze_bank.py','model.py','protocol.py','capture.c','oracle.c','remote_guard.py'})
    for name in names:
        with (snapshot/name).open('xb') as f:f.write((HERE/name).read_bytes())
    save(out/'MANIFEST.json',dict(status='FROZEN_DISCOVERY_UNOPENED',purpose='Fresh structural discriminator; no completion claim',
        seed=seed,reference_host='45.32.204.118',expected_signature='00050654',expected_microcode='0x1',
        counts=dict(counts),rows=len(lines),policy=dataclasses.asdict(program),C1_predictions=True,
        alternatives={name:dataclasses.asdict(p) for name,p in alternatives.items()},
        files={name:digest(out/name) for name in files},source_pins={name:digest(snapshot/name) for name in names},
        hardware_executed=False,prior_tuple_keys_checked=len(prior),
        mathematical_oracle=mathematical_oracle,status_predictions=bool(statuses),
        privacy='No private identifiers, records, hashes or memberships exported',
        limits='Discovery only; full instruction closure and final C validation remain open.'))
    print(json.dumps(dict(status='FROZEN_DISCOVERY_UNOPENED',rows=len(lines),counts=dict(counts))),flush=True)
