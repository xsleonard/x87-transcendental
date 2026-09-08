"""Prepare new exception-staging tuples with conservative local history exclusions.

Unary operands must be absent from known history. Binary pairs must contain
at least one absent operand, which also proves the ordered pair is new. Fixed
zero/infinity operands therefore do not forbid a new binary pair. No tuple is
executed here. Remote public-history clearance and a durable reservation follow.
Private evidence is used only by the existing in-memory exclusion function.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT/'research/fsincos-re'
sys.path[:0]=[str(RESEARCH/'experiments'),str(RESEARCH/'tmp/verification-expansion/coverage')]
from h1725_select_full import private_signatures
from generator_membership import possible


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args();out=args.output
    out.mkdir(parents=True,exist_ok=False)
    private,_=private_signatures()
    histories=[sqlite3.connect('file:'+str(RESEARCH/'tmp/ledger33/current/h1725_full_campaign'/h/'possible-history.sqlite')+'?mode=ro',uri=True) for h in ('skylake','i7')]
    corpus=sqlite3.connect('file:'+str(RESEARCH/'corpus-suite/corpus-v1/catalog.sqlite')+'?mode=ro',uri=True)
    rng=random.Random('x87trans-exception-staging-20260907-v1')
    counts=Counter();fresh=set();cases=[]
    def new(kind):
        for attempt in range(10000):
            sig=rng.getrandbits(63)|(1<<63);se=0x3ffc
            if kind=='negative':se=0xbffc
            elif kind=='large':se=0x403e
            elif kind=='max':se=0x7ffe
            elif kind=='tiny':se=0;sig=(1<<40)|rng.getrandbits(40)
            elif kind=='denormal':se=0;sig&=(1<<63)-1
            elif kind=='pseudo':se=0
            elif kind=='minnormal':se=1
            elif kind=='snan':se=0x7fff;sig=(sig&~(1<<62))|1
            elif kind=='qnan':se=0x7fff;sig|=1<<62
            elif kind=='unsupported':se=0x4123;sig&=(1<<63)-1
            elif kind=='nearone':se=0x3fff;sig=(1<<63)|rng.getrandbits(40)|1
            elif kind=='biglog':se=0x401f
            text=f'{se:04x} {sig:016x}'
            if sig in private or not sig&2047 or possible(se,sig):
                counts['local_holds']+=1;continue
            if corpus.execute('SELECT 1 FROM operands WHERE op=?',(text,)).fetchone() or any(db.execute('SELECT 1 FROM possible WHERE op=?',(text,)).fetchone() for db in histories):
                counts['local_holds']+=1;continue
            if text in fresh:continue
            fresh.add(text);return text
        raise RuntimeError('Could not construct a fresh operand')
    zero='0000 0000000000000000';one='3fff 8000000000000000';inf='7fff 8000000000000000'
    for op in ('fsincos','fptan','f2xm1'):
        for kind in ('normal','negative','tiny','denormal','pseudo','minnormal','snan','qnan','unsupported'):
            cases.append(dict(op=op,family=kind,x=new(kind),y=zero))
        if op!='f2xm1':cases.append(dict(op=op,family='range',x=new('large'),y=zero))
    for op in ('fpatan','fyl2x','fyl2xp1'):
        families=[('ordinary','normal','normal'),('tiny-input','tiny','normal'),
                  ('tiny-y','normal','tiny'),('pseudo-input','pseudo','normal'),
                  ('pseudo-y','normal','pseudo'),('tiny-product','tiny','minnormal'),
                  ('snan-x','snan','normal'),('snan-y','normal','snan'),
                  ('qnan-snan','qnan','snan'),('snan-qnan','snan','qnan'),
                  ('unsupported-qnan','unsupported','qnan'),('qnan-denormal','qnan','denormal'),
                  ('snan-denormal','snan','denormal'),('negative-denormal','negative','denormal')]
        if op=='fpatan':families += [('ratio-underflow','max','minnormal'),('reverse-ratio','minnormal','max')]
        if op=='fyl2x':families += [('multiply-overflow','biglog','max'),('near-one-underflow','nearone','tiny')]
        if op=='fyl2xp1':families += [('large-y','normal','max'),('negative-tiny','negative','tiny')]
        for family,xk,yk in families:
            cases.append(dict(op=op,family=family,x=new(xk),y=new(yk)))
        for family,x,y in [('zero-x',zero,new('denormal')),('zero-y',new('denormal'),zero),
                            ('inf-y',new('denormal'),inf),('one-x',one,new('denormal'))]:
            if op=='fyl2xp1' and x==one:continue
            cases.append(dict(op=op,family=family,x=x,y=y))
    del private
    for db in histories+[corpus]:db.close()
    with gzip.open(out/'proposals.txt.gz','xt') as stream:stream.write('\n'.join(sorted(fresh))+'\n')
    # Numeric predictions are deliberately generated only after this freeze.
    (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    counts['families']=len(cases);counts['fresh_operands']=len(fresh)
    (out/'LOCAL-CLEARANCE.json').write_text(json.dumps(dict(status='LOCAL_CLEAR_REMOTE_PENDING',counts=counts,
        private_details_exported=False,hardware_executed=False,
        cases_sha256=hashlib.sha256((out/'cases.json').read_bytes()).hexdigest(),
        proposals_sha256=hashlib.sha256((out/'proposals.txt.gz').read_bytes()).hexdigest(),
        binary_policy='At least one historically absent operand proves the ordered pair is absent; no known binary pair is reused.',
        limits='Conservative known generator, local public indexes and private-significand exclusions. Remote public history is still required; unknown historical seeds are not claimed covered.'),indent=2)+'\n')
    print(dict(counts))


if __name__=='__main__':main()
