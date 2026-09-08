#!/usr/bin/env python3
"""Separate rational graph/reduction/raw replay for the fixed H1633 table.

Standard library only: no producer, quantizer, graph or parser imports.
Shared pinned native constants are not independently recovered silicon data.
Also tests the tempting but different RN64(T67(product)) substitution.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import re
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

PARENT = 'tmp/ledger33/current/h1633_shared_table_audit/'
LOCKS = {
    'src/fsincos_skylake.c': '0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b',
    'src/p5_rom_constants.h': '2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97',
    'experiments/h1633_shared_table.h': '238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b',
    'experiments/h1633_shared_table_audit.py': '3f23458fff3cc1b4965215554874eb011d53283ab18c93a6fa8fce933bbf864b',
}
M66 = 0x3243f6a8885a308d3
C, TABLE = {}, {}


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def p2(e): return Fraction(1<<e) if e>=0 else Fraction(1,1<<-e)
def top(x):
    assert x>0 and x.denominator & (x.denominator-1)==0
    return x.numerator.bit_length()-x.denominator.bit_length()
def precision(x):
    n=abs(x.numerator)
    return (n//(n&-n)).bit_length() if n else 0


def rnd(x,bits,policy='chop'):
    if not x: return Fraction(0),0
    unit=p2(top(abs(x))-bits+1); scaled=abs(x)/unit
    q,r=divmod(scaled.numerator,scaled.denominator)
    inc=int((policy=='away' and r!=0) or (policy=='rn' and
        (r*2>scaled.denominator or (r*2==scaled.denominator and q&1))))
    return (-1 if x<0 else 1)*(q+inc)*unit,inc


def multiply(x,y,bits=67,policy='chop',identity=False):
    xp,yp=rnd(x,67)[0],rnd(y,64)[0]
    if identity: assert xp==x and yp==y
    return rnd(xp*yp,bits,policy)[0]
def add(x,y): return rnd(x+y,64,'rn')[0]


@lru_cache(maxsize=None)
def table_graph(r,b):
    a=r-Fraction(b,64)
    assert abs(a)<=Fraction(1,16) and precision(a)<=61
    def m(x,y,bits=67,policy='chop'): return multiply(x,y,bits,policy,True)
    s=m(a,a)
    def horner(c): return add(c[1],m(s,add(c[2],m(s,add(c[3],m(s,c[4]))))))
    p,q=horner(C['S4']),horner(C['C4'])
    sine=add(a,m(m(s,p),a))
    cosine=m(s,q,64,'rn')
    double=rnd(m(s,q),64,'rn')[0]
    tsin,tcos=TABLE[b]
    def terminals(t):
        return (tsin+rnd(m(tcos,sine)+m(tsin,t),67)[0],
                tcos+rnd(-m(tsin,sine)+m(tcos,t),67)[0])
    correct=terminals(cosine)
    altered=terminals(double) if double!=cosine else correct
    assert all(x>0 for x in (*correct,*altered))
    return correct,altered,cosine!=double,precision(a),int(a<0),int(a==0)


@lru_cache(maxsize=None)
def polynomial_graph(x,cosine):
    c=C['C6' if cosine else 'S6']; m=multiply
    s=m(x,x); f=m(s,s)
    n=add(c[1],m(f,add(c[3],m(f,c[5]))))
    p=add(c[2],m(f,add(c[4],m(f,c[6]))))
    l,r=m(s,n),m(f,p)
    return 1+rnd(l+r,67)[0] if cosine else x+m(x,add(l,r))


def external(operand,instruction):
    se,sig=(int(w,16) for w in operand.split()); sign=se>>15; e=(se&0x7fff)-16383
    phase=int(instruction=='fcos')
    reduced=e>=0 or (e==-1 and sig>=0xc90fdaa22168c234)
    if not reduced: r=sig*p2(e-63); rs=sign; n=phase
    else:
        assert -1<=e<=62
        a=sig<<(e+2); q,rem=divmod(a,M66); assert rem*2!=M66
        q+=int(rem*2>M66); d=a-q*M66
        assert abs(d)<=M66//2
        r=abs(d)*p2(-65); rs=sign^int(d<0); n=(-q if sign else q)+phase
    cosine=n&1; negative=((n>>1)&1)^(0 if cosine else rs)
    return r,rs,cosine,negative,reduced


def table_lane(r):
    if r<Fraction(1,2): return 18+4*int((r-Fraction(1,4))*16)
    return 36+8*min(2,int((r-Fraction(1,2))*8))


def final(pre,negative,mode):
    policy='rn' if mode=='rn' else 'away' if (negative and mode=='rd') or (not negative and mode=='ru') else 'chop'
    x,c1=rnd(pre,64,policy); exponent=top(x); sig=x/p2(exponent-63)
    assert sig.denominator==1
    return f'{exponent+16383+(0x8000 if negative else 0):04x}:{int(sig):016x}',c1


def raw(line,with_status):
    words=line.lower().split()
    if words[0]=='c2':
        assert not with_status or (len(words)==3 and words[1]=='sw' and int(words[2],16)&0x400)
        return 'C2',int(words[2],16) if with_status else None
    assert len(words)==(5 if with_status else 3) and words[0]=='ok'
    assert len(words[1])==4 and len(words[2])==16
    value=f'{int(words[1],16):04x}:{int(words[2],16):016x}'
    sw=None
    if with_status:
        assert words[3]=='sw'; sw=int(words[4],16)
        if sw&0x400: value='C2'
    return value,sw


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--parent-sha256',required=True)
    args=parser.parse_args(); root,output=args.root.resolve(),args.output_dir.resolve()
    assert not output.exists()
    evidence={**LOCKS,PARENT+'report.json':args.parent_sha256}
    for name,expected in evidence.items(): assert digest(root/name)==expected,name
    parent=json.loads((root/PARENT/'report.json').read_text())
    assert not parent['remaining_banks']
    assert digest(root/PARENT/'prepared.json')==parent['sha256']['prepared']
    prepared=json.loads((root/PARENT/'prepared.json').read_text())
    for name,expected in parent['sha256']['evidence'].items(): assert digest(root/name)==expected,name
    rom=(root/'src/p5_rom_constants.h').read_text()
    def constant(sign,e,hi,lo): return (-1 if int(sign) else 1)*((int(hi,16)<<64)|int(lo,16))*p2(int(e))
    for kind,size,index,sign,e,hi,lo in re.findall(r'P5([SC])([46])_(\d) = \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull',rom):
        C.setdefault(kind+size,{})[int(index)]=constant(sign,e,hi,lo)
    C['S4'][4]-=p2(-25) # Source coefficient payload bit60 at scale2^-85.
    row_pattern=r'\{ (\d+), \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \}, \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \} \}'
    for b,*fields in re.findall(row_pattern,rom): TABLE[int(b)]=constant(*fields[:4]),constant(*fields[4:])
    assert len(TABLE)==8 and len(C)==4
    widths={k:{str(i):precision(v) for i,v in c.items()} for k,c in C.items()}
    assert widths['S4']['4']<=64 and widths['C4']['4']<=64
    assert all(precision(v)<=67 for c in C.values() for v in c.values())
    assert all(precision(v)<=67 for pair in TABLE.values() for v in pair)
    assert Fraction(M66//2,1<<65)<Fraction(13,16)
    counts,routing,banks,examples=Counter(),Counter(),[],[]
    for bank,inventory in zip(parent['banks'],prepared['inventories']):
        assert bank['bank']==inventory['tag']; directory=root/PARENT/bank['bank']; local=Counter()
        for name,expected in bank['sha256'].items(): assert digest(directory/name)==expected,name
        operands=(root/inventory['inputs']).read_text().splitlines()
        for mode,capture in inventory['captures'].items():
            actual=(root/capture).read_text().splitlines()
            with gzip.open(directory/(mode+'_candidate.stdout.gz'),'rt') as f: values=f.read().splitlines()
            with gzip.open(directory/(mode+'_metadata.jsonl.gz'),'rt') as f: rows=[json.loads(line) for line in f]
            metadata={r['index']:r for r in rows}; assert len(rows)==len(metadata)
            assert len(actual)==len(values)==len(operands)==inventory['count']
            for index,(op,observed,predicted) in enumerate(zip(operands,actual,values)):
                hardware,sw=raw(observed,True); value,_=raw(predicted,False)
                assert hardware==value
                meta=metadata.get(index); lane=meta['lane'] if meta else 'fallback'; local[lane+'_rows']+=1
                if not meta: continue
                r,rs,cosine,negative,reduced=external(op,inventory['instruction'])
                s,e,word=meta['magnitude'].split(':')
                assert s=='0' and r==int(word,16)*p2(int(e))
                assert (rs,cosine,negative,top(r))==(meta['residual_sign'],meta['cosine'],meta['negative'],meta['top'])
                routing[lane+('.reduced' if reduced else '.direct')]+=1
                routing[lane+('.negative' if negative else '.positive')]+=1
                routing[lane+('.cosine' if cosine else '.sine')]+=1
                if lane=='table':
                    assert Fraction(1,4)<=r<=Fraction(M66//2,1<<65)
                    b=table_lane(r); assert b==meta['b'] and b!=60
                    pre,altered,changed,ap,an,az=table_graph(r,b)
                    assert ap==meta['precision']<=61
                    prevalue=pre[cosine]
                    expected_alt,altc1=final(altered[cosine],negative,mode)
                    local['double_rounding_intermediate_changed_rows']+=changed
                    local['double_rounding_output_misses']+=expected_alt!=hardware
                    local['double_rounding_C1_misses']+=altc1!=(sw>>9)&1
                    local['table_65bit_residual_rows']+=precision(r)==65
                    local['table_negative_offset_rows']+=an; local['table_zero_offset_rows']+=az
                    routing['table.b'+str(b)]+=1
                    if (expected_alt!=hardware or altc1!=(sw>>9)&1) and len(examples)<32:
                        examples.append(dict(bank=bank['bank'],index=index,instruction=inventory['instruction'],mode=mode,operand=op,
                            hardware=hardware,hardware_C1=(sw>>9)&1,double_rounded_output=expected_alt,double_rounded_C1=altc1))
                else:
                    assert -32<=top(r)<=-3 and precision(r)==meta['precision']<=64
                    if reduced: assert precision(r)<=63
                    prevalue=polynomial_graph(r,cosine)
                expected,c1=final(prevalue,negative,mode)
                assert expected==value and c1==meta['C1']==(sw>>9)&1
                local[lane+'_independent_output_C1_checks']+=1
        for lane in ('table','polynomial','fallback'): assert local[lane+'_rows']==bank['counts'].get(lane+'_rows',0)
        counts.update(local); banks.append(dict(bank=bank['bank'],counts=dict(local)))
        print(bank['bank'],'PASS',dict(local),flush=True)
    certificate=dict(status='NUMERICAL_PROGRAM_EQUIVALENCE_NOT_SILICON_PROOF',coefficient_widths=widths,
        reduced_grid='r=D*2^-65; each center b/64 is also on that grid. Table lane offsets satisfy |a|<=2^-4, hence |a*2^65|<=2^61 and significant width<=61, including power-of-two endpoints.',
        direct_grid='Direct table exponents -2/-1 have input grids2^-65/2^-64 and offset bounds2^-5/2^-4, respectively; significant offset width<=60.',
        reachability='M66 centered residual is less than13/16; b=60 is unreachable. Existing native table cells, not fitted error-state partitions.',
        port_induction='a<=61 bits; square and products<=67; c4 and Horner sums<=64; sine state/cosine tail<=64; table ROM<=67. With square on X and Horner values on Y, ALL table input cuts are identity. Commuting exact products is numerical equality, not physical port evidence.',
        arithmetic='M=T67(T67(x)*T64(y)); MR=RN64(T67(x)*T64(y)); A=RN64(x+y); S=T67(x+y). MR is not RN64(M).',
        constants='Pinned native ROM with existing P6 S4_4 correction, not independent constant recovery.',
        scope='Source-backed numerical reasoning and exhaustive replay of these finite retained records; not full C formal verification, all-input hardware correctness, physical opcodes, or complete architectural status.')
    result=dict(experiment='h1634_independent_table_certificate',status='PASS',counts=dict(counts),routing=dict(routing),banks=banks,
        table_graph_cache_keys=table_graph.cache_info().currsize,polynomial_graph_cache_keys=polynomial_graph.cache_info().currsize,
        double_rounding_counterexamples=examples,certificate=certificate,hardware_execution='none',private_ledger_access='none',canonical_default_or_paper_change='none',
        sha256=dict(script=digest(Path(__file__)),evidence=evidence))
    output.mkdir(parents=True)
    with (output/'report.json').open('x') as f: json.dump(result,f,indent=2,sort_keys=True); f.write('\n')
    print('PASS',dict(counts),flush=True)


if __name__=='__main__': main()
