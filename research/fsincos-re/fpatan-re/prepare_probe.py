"""Freeze D0002, a fresh prospective challenge of the D0001-exact graph.

No new labels are opened. Includes all quadrants, native80 cell/ratio edges,
extreme exponents and subnormals. Known earlier tuples and conservative
private/public possible pairs are excluded. Only aggregate holds are saved.
"""
import collections
import dataclasses
import json
import random
import sqlite3
import subprocess
import sys
from pathlib import Path
from graph_v2 import Graph,prevalue
from model import ROOT,Policy,F,encode,value,pow2
from protocol import make_line,validate_inputs,case_key
from prepare import save,digest

HERE=Path(__file__).resolve().parent
OUT=ROOT/'tmp/fpatan-re/d0002'
SEED='fpatan-d0002-20260905-prospective'
CANDIDATE=Graph(arithmetic=dataclasses.replace(Policy(),denominator='chop67',direct_limit=32),reduction_mul='exact')


def generate():
    rng=random.Random(SEED);seen=set()
    def orbit(ys,ym,xs,xm,kind):
        for sy in (0,0x8000):
            for sx in (0,0x8000):
                p=(ys|sy,ym,xs|sx,xm)
                if p not in seen:seen.add(p);yield p,kind
    for _ in range(768):
        ys=16383+rng.randrange(-80,81);xs=16383+rng.randrange(-80,81)
        yield from orbit(ys,rng.getrandbits(63)|(1<<63),xs,rng.getrandbits(63)|(1<<63),'broad-ratios')
    for k in range(1,65):
        for _ in range(2):
            xm=rng.getrandbits(63)|(1<<63);target=value(16383,xm)*F(k,64)
            ys,ym=encode(target)
            for off in (-4,-1,0,1,4):
                yse,ysig=encode(value(ys,ym)+off*pow2(ys-16383-63))
                yield from orbit(yse,ysig,16383,xm,'table-boundary')
    for e in range(-74,-61):
        for _ in range(8):
            xm=rng.getrandbits(63)|(1<<63)
            for off in (-1,0,1):
                ys,ym=encode(value(16383+e,xm)+off*pow2(e-63))
                yield from orbit(ys,ym,16383,xm,'tiny-boundary')
    for _ in range(64):
        ym=rng.getrandbits(63)|(1<<63);xm=rng.getrandbits(63)|(1<<63)
        ys=rng.randrange(1,32767);xs=rng.randrange(1,32767)
        yield from orbit(ys,ym,xs,xm,'full-exponent-range')
    for _ in range(32):
        ym=rng.getrandbits(63) or 1;xm=rng.getrandbits(63) or 1
        yield from orbit(0,ym,0,xm,'both-subnormal')
        yield from orbit(0,ym,16383,rng.getrandbits(63)|(1<<63),'subnormal-numerator')
        yield from orbit(16383,rng.getrandbits(63)|(1<<63),0,xm,'subnormal-denominator')
    for _ in range(24):
        xm=rng.getrandbits(63)|(1<<63)
        for offset in (-1,0,1):
            ys,ym=encode(value(16383,xm)+offset*pow2(-63))
            for scale in (-16000,-1000,0,1000,16000):
                yield from orbit(ys+scale,ym,16383+scale,xm,'near-one-scaled')


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(ROOT/'experiments'))
    from h1725_select_full import private_signatures
    private,_=private_signatures()
    history=ROOT/'tmp/ledger33/current/h1725_full_campaign/skylake/possible-history.sqlite'
    db=sqlite3.connect('file:'+str(history)+'?mode=ro',uri=True)
    public={int(op.split()[1],16) for (op,) in db.execute('SELECT op FROM possible')};db.close()
    catalog=sqlite3.connect('file:'+str(ROOT/'corpus-suite/corpus-v1/catalog.sqlite')+'?mode=ro',uri=True)
    prior=set()
    for job in sorted(OUT.parent.iterdir()):
        if job!=OUT and (job/'MANIFEST.json').exists():
            _,keys=validate_inputs((job/'inputs.txt').read_text());prior.update(keys)
    counts=collections.Counter();lines=[];predictions=[];categories={}
    for index,(pair,kind) in enumerate(generate()):
        ys,ym,xs,xm=pair;counts['generated_pairs']+=1
        if ym in private and xm in private:counts['private_possible_pair_holds']+=1;continue
        if ym in public and xm in public:counts['public_possible_pair_holds']+=1;continue
        if all(catalog.execute('SELECT 1 FROM operands WHERE op=?',(f'{s:04x} {m:016x}',)).fetchone() for s,m in ((ys,ym),(xs,xm))):
            counts['corpus_possible_pair_holds']+=1;continue
        before=prevalue(*pair,CANDIDATE);counts['selected_pairs']+=1
        for pc in ((24,53,64) if index%31==0 else (64,)):
            for rc in ('rn','rd','ru','rz'):
                if case_key(rc,pc,*pair) in prior:counts['previous_tuple_holds']+=1;continue
                line=make_line(rc,pc,*pair);se,sig=encode(before,rc)
                c1=int(abs(value(se,sig))>abs(before));ident=line.split()[0]
                lines.append(line);predictions.append(f'{ident} {se:04x} {sig:016x} {c1}');categories[ident]=kind
        if index and index%1000==0:print('prepared pairs',index,flush=True)
    del private;catalog.close()
    for name,rows in (('inputs.txt',lines),('predictions.txt',predictions)):
        with (OUT/name).open('x') as f:f.write('\n'.join(rows)+'\n')
    validate_inputs((OUT/'inputs.txt').read_text());save(OUT/'categories.json',categories)
    with (OUT/'inputs.txt').open('rb') as source,(OUT/'math-oracle.txt').open('xb') as out:
        subprocess.run(['/private/tmp/fpatan-math-oracle'],stdin=source,stdout=out,check=True)
    source_dir=OUT/'sources';source_dir.mkdir()
    names=('model.py','graph_v2.py','prepare_probe.py','protocol.py','capture.c','oracle.c','remote_guard.py')
    for name in names:
        with (source_dir/name).open('xb') as f:f.write((HERE/name).read_bytes())
    save(OUT/'MANIFEST.json',dict(status='FROZEN_DISCOVERY_UNOPENED',purpose='Prospective challenge, not a closure declaration',
        seed=SEED,reference_host='45.32.204.118',expected_signature='00050654',expected_microcode='0x1',
        counts=dict(counts),rows=len(lines),policy=dataclasses.asdict(CANDIDATE),C1_predictions=True,
        files={name:digest(OUT/name) for name in ('inputs.txt','predictions.txt','math-oracle.txt','categories.json')},
        source_pins={name:digest(source_dir/name) for name in names},hardware_executed=False,
        prior_tuple_keys_checked=len(prior),privacy='Private records remain local; no private identifiers, hashes or memberships exported',
        limits='Only finite nonzero valid inputs; specials remain open. Prediction graph is a hypothesis, not a delivered solution.'))
    print(json.dumps(dict(status='FROZEN_DISCOVERY_UNOPENED',counts=dict(counts),rows=len(lines))),flush=True)


if __name__=='__main__':main()
