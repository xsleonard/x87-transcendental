#!/usr/bin/env python3
"""Independent integer/rational and compiler checks of the paired alternatives.

Reuses independently implemented numeric primitives/constants, not C helpers.
Software-only checks do not establish fresh paired hardware validation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import re
import subprocess
from collections import Counter
from fractions import Fraction
from pathlib import Path
import h1592_independent_integer_spec as integer
import h1601_paired_square_discriminator as old_pair
import h1634_independent_table_certificate as rational
import h1637_tiny_closed_form_audit as tiny
import h1710_build_paired_program as build
from h1709_paired_retained_census import digest, save, parse, SOURCE_SHA


def constants(root):
    text=(root/'src/p5_rom_constants.h').read_text()
    def value(sign,e,hi,lo):return (-1 if int(sign) else 1)*((int(hi,16)<<64)|int(lo,16))*rational.p2(int(e))
    for kind,size,i,sign,e,hi,lo in re.findall(r'P5([SC])([46])_(\d) = \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull',text):
        rational.C.setdefault(kind+size,{})[int(i)]=value(sign,e,hi,lo)
    rational.C['S4'][4]-=rational.p2(-25)
    pattern=r'\{ (\d+), \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \}, \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \} \}'
    for b,*fields in re.findall(pattern,text): rational.TABLE[int(b)]=value(*fields[:4]),value(*fields[4:])
    assert len(rational.TABLE)==8
    for key,c in [('S6',old_pair.SINE),('C6',integer.COEFFICIENTS)]:
        for i,v in c.items(): assert rational.C[key][i]==v.fraction()


def polynomial(r,policy):
    V=integer.Value
    x=V(r.numerator,1-r.denominator.bit_length())
    square=integer.mul(x,x,67)
    p,q=old_pair.SINE[6],integer.COEFFICIENTS[6]
    def step(v,c,cut):
        product=integer.exact_mul(v,square)
        if cut:product=integer.quantize(product,67,'chop')
        return integer.add(product,c,64,'rn')
    for i in (5,4,3,2,1):p=step(p,old_pair.SINE[i],policy=='all' or (policy=='last' and i==1))
    for i in (5,4,3,2):q=step(q,integer.COEFFICIENTS[i],policy=='all')
    q=step(q,integer.COEFFICIENTS[1],True)
    ps=integer.mul(p,square,64,'rn')
    stail=integer.mul(ps,x,67);ctail=integer.mul(q,square,67)
    return integer.exact_add(x,stail).fraction(),integer.exact_add(V(1,0),ctail).fraction()


def expected(operand,mode,policy,cache):
    info=[tiny.evaluate(operand,insn,mode) for insn in ('fsin','fcos')]
    if info[0]['output'] is not None:
        assert info[1]['output'] is not None
        if info[0]['output']=='C2':return None,None
        known=info[0]['C1'] is not None
        meta=('tiny' if known else 'special',int(known),info[0]['C1'] or 0,info[1]['C1'] or 0)
        return tuple(i['output'] for i in info),meta
    outputs=[];c1=[]
    for insn in ('fsin','fcos'):
        r,rs,cosine,negative,reduced=rational.external(operand,insn)
        path='polynomial' if r<Fraction(1,4) else 'table'
        key=policy,r,path
        if key not in cache:
            cache[key]=polynomial(r,policy) if path=='polynomial' else rational.table_graph(r,rational.table_lane(r))[0]
        value,increment=rational.final(cache[key][cosine],negative,mode)
        outputs.append(value);c1.append(increment)
    return tuple(outputs),(path,1,*c1)


def run(binary,mode,operands,trace=False):
    command=[str(binary),'--batch','--rc='+mode]
    if trace:command.append('--general-trace')
    proc=subprocess.run(command,input=''.join(x+'\n' for x in operands),text=True,capture_output=True,check=True)
    values=[parse(line)[0] for line in proc.stdout.splitlines()]; assert len(values)==len(operands)
    metadata={}
    for line in proc.stderr.splitlines():
        words=line.split();assert words[0]=='HPAIR' and len(words)==6
        i=int(words[1]);assert i not in metadata
        metadata[i]=(words[2],*map(int,words[3:]))
    return values,metadata


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    constants(root);source=build.source_string(root);out.mkdir(parents=True)
    rng=random.Random(0x1710);operands={'3ffc c060000000d78237','3ffc b400000004ea29f8'}
    for _ in range(768):
        e=rng.choice([-69,-68,-33,-32,-31,-4,-3,-2,-1,*range(63)])
        operands.add(f'{(rng.randrange(2)<<15)|(e+16383):04x} {rng.getrandbits(63)|(1<<63):016x}')
    for e in (-69,-68,-33,-32,-31,-4,-3,-2,-1,0,1,30,61,62,63):
        for sign in (0,0x8000):
            for s in (1<<63,(1<<63)+1,0xc90fdaa22168c233,0xc90fdaa22168c234,(1<<64)-1):
                operands.add(f'{sign|e+16383:04x} {s:016x}')
    for ef in (0,1,0x7ffe,0x7fff):
        for sign in (0,0x8000):
            for s in (0,1,(1<<63)-1,1<<63,(1<<63)+1,0xc000000000000000,(1<<64)-1):
                operands.add(f'{sign|ef:04x} {s:016x}')
    for q in (1,2,3,4,7,16,31,64,127,1024):
        v=q*rational.M66;w=v.bit_length();e=w-66;s=v>>(w-64)
        for d in (-1,0,1):
            for sign in (0,0x8000):operands.add(f'{sign|e+16383:04x} {s+d:016x}')
    operands=sorted(operands);save(out/'inputs.json',operands)
    configs={'O0':['-O0'],'O2':['-O2'],'O3':['-O3'],'ubsan':['-O2','-fsanitize=undefined','-fno-sanitize-recover=all']}
    binaries={};counts=Counter();cache={};contrasts=[];reference={}
    for policy,number in [('baseline',0),('last',1),('all',2)]:
        for label,flags in configs.items():
            binary=out/(policy+'_'+label)
            proc=subprocess.run(['cc',*flags,'-std=c11','-DG_H1710_PAIRED=1','-DG_H1710_MATERIALIZE='+str(number),
                '-I',str(root/'src'),'-I',str(root/'experiments'),'-x','c','-','-lm','-o',str(binary)],
                input=source,text=True,capture_output=True,check=True);assert not proc.stderr
            test=subprocess.run([str(binary),'--selftest'],text=True,capture_output=True,check=True)
            assert test.stdout=='SELFTEST: ok\n' and not test.stderr;binaries[binary.name]=digest(binary)
            for mode in ('rn','rd','ru','rz'):
                values,metadata=run(binary,mode,operands,True)
                for i,op in enumerate(operands):
                    value,meta=expected(op,mode,policy,cache)
                    assert (values[i],metadata.get(i))==(value,meta),(policy,label,mode,op,values[i],value,metadata.get(i),meta)
                    counts['compiler_instruction_rows']+=1
                    counts['independent_lane_outputs']+=2 if value is not None else 0
                    counts['independent_C1_indicators']+=2 if meta is not None and meta[1] else 0
                if label=='O2':reference[policy,mode]=values
            print(policy,label,'independent checks pass',flush=True)
    for mode in ('rn','rd','ru','rz'):
        for i,op in enumerate(operands):
            values={policy:reference[policy,mode][i] for policy in ('baseline','last','all')}
            if len({str(v) for v in values.values()})>1:contrasts.append(dict(operand=op,mode=mode,values=values))
    report=dict(experiment='h1710_verify_paired_program',status='PASS_INDEPENDENT_SOFTWARE',operands=len(operands),
        counts=dict(counts),contrasts=contrasts,hardware_execution='none',private_access='none',promotion=False,
        sha256=dict(script=digest(Path(__file__)),builder=digest(Path(build.__file__)),
            header=digest(root/'experiments/h1710_paired_program.h'),main_source=SOURCE_SHA,
            assembled_source=hashlib.sha256(source.encode()).hexdigest(),binaries=binaries,inputs=digest(out/'inputs.json'),
            independent_modules={str(Path(m.__file__).relative_to(root)):digest(Path(m.__file__)) for m in (integer,old_pair,rational,tiny)}))
    save(out/'report.json',report);print(report['status'],dict(counts),flush=True)


if __name__=='__main__':main()
