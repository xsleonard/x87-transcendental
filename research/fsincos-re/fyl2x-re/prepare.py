"""Freeze public logarithm discovery inputs before any hardware is run.

Private history is an in-memory conservative pair exclusion only. No private
paths, hashes, identifiers, source text or membership records are exported.
The permanent remote guard additionally reserves complete instruction tuples.
"""
import argparse
from collections import Counter
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
import sys
from model import ROOT, F, pow2, encode, value, predict, Policy
from protocol import make_line, validate_inputs

BASE = ROOT/'tmp/fyl2x-re'
SOURCE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    with path.open('x') as f:
        json.dump(obj,f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())


def generate(seed):
    rng = random.Random(seed)
    for op in ('fyl2x','fyl2xp1'):
        for i in range(384):
            if op == 'fyl2x':
                xs = 16383+rng.randrange(-120,121)
                xm = (1 << 63)|rng.getrandbits(63)
            else:
                xs = 16383+rng.randrange(-15,-2)|(rng.randrange(2) << 15)
                xm = (1 << 63)|rng.getrandbits(63)
            if i%2:
                ys,ym = 16383,1 << 63
            else:
                ys,ym = 16383+rng.randrange(-100,101)|(rng.randrange(2) << 15),(1 << 63)|rng.getrandbits(63)
            yield op,(ys,ym,xs,xm),'independent-finite'
    for i in range(32):
        for k in range(8):
            for delta in (-1,0,1):
                y = ((1 << 63)|rng.getrandbits(63))*pow2(-63)
                center = F(64+2*i+(k & 1),64)
                x = center+delta*pow2(-63)
                if x > 0:
                    yield 'fyl2x',(*encode(y),*encode(x)),'table-centers-and-boundaries'
    for sign in (-1,1):
        for e in (-16380,-1000,-100,-80,-72,-71,-70,-69,-68,-67,-66,-65,-64,-63,-62,-60,-20,-10,-4):
            for k in range(8):
                ys,ym = 16383,(1 << 63)|rng.getrandbits(63)
                x = sign*((1 << 63)|rng.getrandbits(63))*pow2(e-63)
                yield 'fyl2xp1',(ys,ym,*encode(x)),'tiny-and-direct'
                if abs(x) >= pow2(-64):
                    yield 'fyl2x',(ys,ym,*encode(1+x)),'near-one'
    for x in (F(7,8),F(9,8)):
        for delta in range(-8,9):
            for k in range(8):
                yield 'fyl2x',(16383,(1 << 63)|rng.getrandbits(63),*encode(x+delta*pow2(-64))),'direct-join'


def clearance():
    sys.path.insert(0,str(ROOT/'experiments'))
    from h1725_select_full import private_signatures
    private,_ = private_signatures()
    base = ROOT/'tmp/ledger33/current/h1725_full_campaign/skylake'
    assert json.loads((base/'public-history.log').read_text().splitlines()[-1])['status']=='PUBLIC_HISTORY_EXPORT_COMPLETE'
    db = sqlite3.connect('file:'+str(base/'possible-history.sqlite')+'?mode=ro',uri=True)
    public = {int(op.split()[1],16) for (op,) in db.execute('SELECT op FROM possible')}
    db.close()
    catalog = sqlite3.connect('file:'+str(ROOT/'corpus-suite/corpus-v1/catalog.sqlite')+'?mode=ro',uri=True)
    prior = set()
    for path in BASE.glob('*/inputs.txt'):
        for line in path.read_text().splitlines():
            t = line.split(); prior.add((t[1],*t[4:]))
    return private,public,catalog,prior


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--job',required=True); p.add_argument('--seed',default='log-l0001-20260906')
    a = p.parse_args(); out = BASE/a.job
    assert out.parent == BASE and not out.exists()
    private,public,catalog,prior = clearance()
    counts = Counter(); lines=[]; categories={}; seen=set()
    for op,pair,kind in generate(a.seed):
        ys,ym,xs,xm = pair; counts['generated_pairs'] += 1
        if ym in private and xm in private:
            counts['private_possible_pair_holds'] += 1; continue
        if ym in public and xm in public:
            counts['public_possible_pair_holds'] += 1; continue
        y=f'{ys:04x} {ym:016x}'; x=f'{xs:04x} {xm:016x}'
        if all(catalog.execute('SELECT 1 FROM operands WHERE op=?',(v,)).fetchone() for v in (y,x)):
            counts['corpus_possible_pair_holds'] += 1; continue
        key=(op,*y.split(),*x.split())
        if key in prior or key in seen:
            counts['prior_or_repeated_pair_holds'] += 1; continue
        seen.add(key); counts['selected_pairs'] += 1
        for rc in ('rn','rd','ru','rz'):
            line=make_line(op,rc,64,*pair); lines.append(line); categories[line.split()[0]]=kind
    del private; catalog.close()
    validate_inputs('\n'.join(lines))
    out.mkdir()
    (out/'inputs.txt').write_text('\n'.join(lines)+'\n')
    save(out/'categories.json',categories)
    with (out/'predictions.txt').open('x') as f:
        for i,line in enumerate(lines):
            se,sig,c1=predict(line)
            f.write(f'{line.split()[0]} {se:04x} {sig:016x} {c1}\n')
            if i and i%4000==0: print('predicted',i,flush=True)
    save(out/'MANIFEST.json',dict(status='FROZEN_DISCOVERY_UNOPENED',seed=a.seed,
        reference_host='45.32.204.118',expected_signature='00050654',expected_microcode='0x1',
        rows=len(lines),counts=dict(counts),policy=dataclasses.asdict(Policy()),
        files={name:digest(out/name) for name in ('inputs.txt','predictions.txt','categories.json')},
        source_pins={name:digest(SOURCE/name) for name in ('model.py','prepare.py','protocol.py','capture.c','remote_guard.py')},
        public_rom_sha256=digest(ROOT/'data/pentium-rom/rom-constants.tsv'),
        history='Conservative local supplemental/public/corpus pair exclusion; initial remote logarithm audit and permanent tuple ledger required.',
        privacy='No private paths, hashes, records or membership exported',hardware_executed=False,
        limits='Discovery only; unvalidated finite hypothesis.'))
    print(json.dumps(dict(status='FROZEN_DISCOVERY_UNOPENED',rows=len(lines),counts=dict(counts))),flush=True)


if __name__ == '__main__':
    main()
