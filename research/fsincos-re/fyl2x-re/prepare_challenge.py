"""Freeze fresh source-guided logarithm challenges, without reading labels."""
import argparse
from collections import Counter
import dataclasses
import json
from pathlib import Path
import random
import shutil
import subprocess
from model import F, pow2, encode, value, Policy
from prepare import ROOT, BASE, SOURCE, clearance, save, digest
from protocol import make_line, validate_inputs


def generate(seed, size):
    r=random.Random(seed)
    def y():
        return 16383+r.randrange(-40,41)|(r.randrange(2)<<15),(1<<63)|r.getrandbits(63)
    def normal(e=0):
        return 16383+e,(1<<63)|r.getrandbits(63)
    for _ in range(size):
        eps=F(r.randrange(-(1<<62),1<<62),1<<65)
        yield 'fyl2xp1',(*y(),*encode(eps)),'direct-random'
        yield 'fyl2x',(*y(),*encode(1+eps)),'near-one-random'
        eps=F(r.randrange(-(1<<62),1<<62),1<<64)
        yield 'fyl2xp1',(*y(),*encode(eps)),'p1-direct-table-range'
        yield 'fyl2x',(*y(),*normal(r.randrange(-16000,16001))),'table-wide-exponents'
    for i in range(65):
        center=F(64+i,64)
        for j in (-33,-17,-9,-5,-3,-2,-1,0,1,2,3,5,9,17,33):
            for e in (-1000,-1,0,1,1000):
                yield 'fyl2x',(*y(),*encode((center+j*pow2(-65))*pow2(e))),'all-table-boundaries'
    for sign in (-1,1):
        for center in (F(1,8),F(1,4),F(19,64)):
            for offset in range(-32,33):
                eps=sign*(center+offset*pow2(-66))
                # 19/64 is just outside Intel's specified domain: retain only
                # a strict rational bound within 1-sqrt(1/2).
                if abs(eps)>F(29289,100000): continue
                yield 'fyl2xp1',(*y(),*encode(eps)),'p1-joins'
    for e in range(-76,-57):
        for k in range(96):
            xs,xm=normal(e); xs|=r.randrange(2)<<15
            yield 'fyl2xp1',(*y(),xs,xm),'tiny-bypass-join'
    for _ in range(768):
        xs,xm=normal(r.randrange(-40,41))
        ys,ym=normal(r.choice((-16382,-16381,-16380,16378,16379,16380,16381,16382,16383)))
        ys|=r.randrange(2)<<15
        yield 'fyl2x',(ys,ym,xs,xm),'underflow-overflow'
        xs,xm=normal(r.choice((-16382,-16381,-16380,-16379,-1000,-100,-10,-4)))
        xs|=r.randrange(2)<<15
        ys,ym=normal(r.choice((-16382,-1000,-10,0,10,1000,16380,16381,16382,16383)))
        ys|=r.randrange(2)<<15
        yield 'fyl2xp1',(ys,ym,xs,xm),'underflow-overflow'
    for op in ('fyl2x','fyl2xp1'):
        for _ in range(64):
            freshx=normal(-4 if op=='fyl2xp1' else r.randrange(-5,6))
            if op=='fyl2xp1':freshx=(freshx[0]|(r.randrange(2)<<15),freshx[1])
            freshy=y()
            payload=r.getrandbits(62)|1
            specials=[(0,0),(0x8000,0),(0x7fff,1<<63),(0xffff,1<<63),
                      (0,r.getrandbits(63)|1),(0x8000,r.getrandbits(63)|1),
                      (0,(1<<63)|r.getrandbits(63)),
                      (0x7fff,(3<<62)|payload),(0xffff,(3<<62)|payload),
                      (0x7fff,(1<<63)|payload),(0xffff,(1<<63)|payload),
                      (0x4000,payload),(0x7fff,payload)]
            for special in specials:
                yield op,(*special,*freshx),'special-y'
                if op=='fyl2x' or special[0]&0x7fff!=0x7fff or special[1]!=(1<<63):
                    yield op,(*freshy,*special),'special-x'
            if op=='fyl2x':
                yield op,(*freshy,0x3fff,1<<63),'exact-log-zero'
                yield op,(*freshy,*normal(r.randrange(-5,6))) ,'normal-controls'
                negx=normal(r.randrange(-5,6))
                yield op,(*freshy,negx[0]|0x8000,negx[1]),'negative-domain'
                yield op,(*freshy,16383+r.randrange(-16382,16384),1<<63),'exact-powers'
            for sx in (0,0x8000):
                for sy in (0,0x8000):
                    for qx in (0,1):
                        for qy in (0,1):
                            xm=(1<<63)|(qx<<62)|r.getrandbits(62)|1
                            ym=(1<<63)|(qy<<62)|r.getrandbits(62)|1
                            yield op,(0x7fff|sy,ym,0x7fff|sx,xm),'nan-priority'


def main():
    p=argparse.ArgumentParser(); p.add_argument('--job',required=True)
    p.add_argument('--seed',required=True);p.add_argument('--size',type=int,default=2048)
    p.add_argument('--bank',choices=('broad','rounding','final'),default='broad')
    p.add_argument('--candidate',type=Path,required=True); a=p.parse_args()
    out=BASE/a.job; assert out.parent==BASE and not out.exists()
    private,public,catalog,prior=clearance()
    seen=set();counts=Counter();lines=[];categories={}
    generator=generate
    if a.bank=='rounding':
        from rounding_bank import generate as generator
    elif a.bank=='final':
        from final_bank import generate as generator
    for op,pair,kind in generator(a.seed,a.size):
        ys,ym,xs,xm=pair;counts['generated_pairs']+=1
        if ym in private and xm in private: counts['private_possible_pair_holds']+=1;continue
        if ym in public and xm in public: counts['public_possible_pair_holds']+=1;continue
        y=f'{ys:04x} {ym:016x}';x=f'{xs:04x} {xm:016x}'
        if all(catalog.execute('SELECT 1 FROM operands WHERE op=?',(v,)).fetchone() for v in (y,x)):
            counts['corpus_possible_pair_holds']+=1;continue
        key=(op,*y.split(),*x.split())
        if key in prior or key in seen:counts['prior_or_repeated_pair_holds']+=1;continue
        seen.add(key);counts['selected_pairs']+=1
        pcs=(24,53,64) if kind in ('special-y','special-x','underflow-overflow','p1-joins','nan-priority',
            'underflow-rounding-surfaces','overflow-rounding-surfaces','documented-p1-endpoints','exact-subnormal-products') else (64,)
        for pc in pcs:
            for rc in ('rn','rd','ru','rz'):
                line=make_line(op,rc,pc,*pair);lines.append(line);categories[line.split()[0]]=kind
    del private;catalog.close();validate_inputs('\n'.join(lines));out.mkdir()
    (out/'inputs.txt').write_text('\n'.join(lines)+'\n');save(out/'categories.json',categories)
    (out/'sources').mkdir()
    sources=('model.py','log_model.c','prepare.py','prepare_challenge.py','rounding_bank.py','final_bank.py','capture.c','protocol.py','remote_guard.py')
    for name in sources:shutil.copyfile(SOURCE/name,out/'sources'/name)
    with (out/'inputs.txt').open('rb') as src,(out/'predictions.txt').open('xb') as dst:
        subprocess.run([str(a.candidate.resolve())],stdin=src,stdout=dst,check=True)
    assert len((out/'predictions.txt').read_text().splitlines())==len(lines)
    save(out/'MANIFEST.json',dict(status='FROZEN_DISCOVERY_UNOPENED',seed=a.seed,bank=a.bank,
        reference_host='45.32.204.118',expected_signature='00050654',expected_microcode='0x1',
        rows=len(lines),counts=dict(counts),policy=dataclasses.asdict(Policy()),
        files={name:digest(out/name) for name in ('inputs.txt','predictions.txt','categories.json')},
        source_pins={name:digest(SOURCE/name) for name in sources},
        candidate_binary_sha256=digest(a.candidate),public_rom_sha256=digest(ROOT/'data/pentium-rom/rom-constants.tsv'),
        history='Conservative local supplemental/public/corpus/prior-log pair exclusion; permanent remote tuple reservation required.',
        privacy='No private paths, hashes, records or membership exported',hardware_executed=False,
        limits='Source-guided discovery challenge; specials and range-boundary rules are still hypotheses.'))
    print(json.dumps(dict(status='FROZEN_DISCOVERY_UNOPENED',rows=len(lines),counts=dict(counts))),flush=True)


if __name__=='__main__':main()
