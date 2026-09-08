"""Generate/freeze FPATAN discovery candidates and predictions locally.

This is discovery, not an acceptance test. No hardware output is read. Private
history is processed in memory; no private identifiers/hashes/membership are
exported. Public inputs and aggregate exclusion counts alone are retained.
"""
import argparse
import collections
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
import subprocess
import sys
from model import F,ROOT,Policy,predict,encode,value,pow2
from protocol import make_line,validate_inputs


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,obj):
    with path.open('x') as f:json.dump(obj,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())


def generate(seed):
    rng=random.Random(seed);seen=set()
    def add(ys,ym,xs,xm,kind,scale=0):
        for sy in (0,0x8000):
            for sx in (0,0x8000):
                pair=(ys+scale|sy,ym,xs+scale|sx,xm)
                if pair not in seen:
                    seen.add(pair);yield pair,kind
    for _ in range(192):
        ym=rng.getrandbits(63)|(1<<63);xm=rng.getrandbits(63)|(1<<63)
        ye=16383+rng.randrange(-20,5);xe=16383+rng.randrange(-4,5)
        yield from add(ye,ym,xe,xm,'independent-ratios')
    for e in (-70,-34,-33,-32,-31,-12,-8,-6,-5,-4,-3,-2,-1,0,1,4,32,70):
        for _ in range(12):
            ym=rng.getrandbits(63)|(1<<63)
            yield from add(16383+e,ym,16383,1<<63,'direct-ratio')
    for k in range(1,65):
        xm=rng.getrandbits(63)|(1<<63);x=value(16383,xm)
        ys,ym=encode(x*F(k,64))
        for offset in (-2,-1,0,1,2):
            y=value(ys,ym)+offset*pow2(ys-16383-63)
            sy,sm=encode(y)
            yield from add(sy,sm,16383,xm,'table-centers-and-midpoints')
    for _ in range(32):
        xm=rng.getrandbits(63)|(1<<63)
        for offset in (-1,0,1):
            ys,ym=encode(value(16383,xm)+offset*pow2(-63))
            for scale in (-1000,0,1000):
                yield from add(ys,ym,16383,xm,'equal-scale-orbits',scale)


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seed',default='fpatan-d0001-20260905')
    p.add_argument('--oracle',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(ROOT/'experiments'))
    from h1725_select_full import private_signatures
    private,_=private_signatures()
    base=ROOT/'tmp/ledger33/current/h1725_full_campaign/skylake'
    log=json.loads((base/'public-history.log').read_text().splitlines()[-1])
    assert log['status']=='PUBLIC_HISTORY_EXPORT_COMPLETE'
    db=sqlite3.connect('file:'+str(base/'possible-history.sqlite')+'?mode=ro',uri=True)
    public={int(op.split()[1],16) for (op,) in db.execute('SELECT op FROM possible')};db.close()
    catalog=sqlite3.connect('file:'+str(ROOT/'corpus-suite/corpus-v1/catalog.sqlite')+'?mode=ro',uri=True)
    counts=collections.Counter();lines=[];categories={}
    for pair,kind in generate(a.seed):
        ys,ym,xs,xm=pair;counts['generated_pairs']+=1
        # An exact earlier pair requires both operands to be present. Ignore
        # order, exponents, signs and modes for conservative private holds.
        if ym in private and xm in private:
            counts['private_possible_pair_holds']+=1;continue
        if ym in public and xm in public:
            counts['public_possible_pair_holds']+=1;continue
        y=f'{ys:04x} {ym:016x}';x=f'{xs:04x} {xm:016x}'
        if all(catalog.execute('SELECT 1 FROM operands WHERE op=?',(v,)).fetchone() for v in (y,x)):
            counts['corpus_possible_pair_holds']+=1;continue
        counts['selected_pairs']+=1
        for pc in ((24,53,64) if kind=='equal-scale-orbits' else (64,)):
            for rc in ('rn','rd','ru','rz'):
                line=make_line(rc,pc,*pair);lines.append(line);categories[line.split()[0]]=kind
    del private;catalog.close();text='\n'.join(lines)+'\n';validate_inputs(text)
    with (a.out/'inputs.txt').open('x') as f:f.write(text)
    save(a.out/'categories.json',categories)
    with (a.out/'predictions.txt').open('x') as f:
        for i,line in enumerate(lines):
            se,sig=predict(line)
            f.write(f'{line.split()[0]} {se:04x} {sig:016x}\n')
            if i and i%4000==0:print('predicted',i,flush=True)
    with (a.out/'inputs.txt').open('rb') as source,(a.out/'math-oracle.txt').open('xb') as out:
        subprocess.run([str(a.oracle)],stdin=source,stdout=out,check=True)
    save(a.out/'MANIFEST.json',dict(status='FROZEN_DISCOVERY_UNOPENED',seed=a.seed,
        reference_host='45.32.204.118',expected_signature='00050654',expected_microcode='0x1',
        counts=dict(counts),rows=len(lines),policy=dataclasses.asdict(Policy()),
        files={name:digest(a.out/name) for name in ('inputs.txt','predictions.txt','math-oracle.txt','categories.json')},
        source_pins={name:digest(Path(__file__).parent/name) for name in ('model.py','prepare.py','protocol.py','capture.c','oracle.c')},
        public_rom_sha256=digest(ROOT/'data/pentium-rom/rom-constants.tsv'),
        history='Conservative local supplemental/public/corpus pair exclusion; remote no-prior-FPATAN audit required before execution.',
        privacy='No private paths, hashes, records or membership exported',
        hardware_executed=False,limits='Discovery only; candidate is not a solution; PC effect not assumed.'))
    print(json.dumps(dict(status='FROZEN_DISCOVERY_UNOPENED',rows=len(lines),counts=dict(counts))),flush=True)


if __name__=='__main__':main()
