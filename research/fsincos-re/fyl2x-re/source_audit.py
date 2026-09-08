"""Reproduce logarithm constant provenance from pinned public source files.

This is a static audit and a high-precision mathematical derivation. It does
not read any hardware result, candidate output or private research source.
"""
import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import re
from model import ROOT

PINS = {
    'listing':'46fb61bfaf174765c117de65b036b73ae4433b9c2b9871d5289fd02d4867067e',
    'rom':'87b9ee93e0c7a1f988906d8fd79d886590aa41a7368d06ef1954be8d5aca14db',
}
URLS = {
    'listing':'https://github.com/chip-red-pill/uCodeDisasm/blob/ffc9070233a6e7a26dbabe723289259f087ee20b/ucode/ucode_glm.txt',
    'rom':'https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/dumps/rom.txt',
    'p5':'https://www.righto.com/2025/01/pentium-floating-point-ROM.html',
}


def derive(rows, precision):
    result={}
    with localcontext() as ctx:
        ctx.prec=precision
        for i in range(32):
            a,b=rows[206+i],rows[238+i]
            exact=(1+Decimal(1+2*i)/64).ln()/Decimal(2).ln()
            top_step=Decimal(2)**(int(a['exp'],16)-65535-39)
            top=(exact/top_step).to_integral_value()*top_step
            remainder=exact-top
            low_step=Decimal(2)**(int(b['exp'],16)-65535-66)
            result[206+i]=int(top/(top_step/Decimal(2)**27))
            result[238+i]=int((abs(remainder)/low_step).to_integral_value())
            assert int(remainder<0)==int(b['sign'])
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--listing',type=Path,required=True)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    for name in PINS:
        assert hashlib.sha256(getattr(a,name).read_bytes()).hexdigest()==PINS[name]
    with (ROOT/'data/pentium-rom/rom-constants.tsv').open() as f:
        rows={int(r['row']):r for r in csv.DictReader(f,delimiter='\t')}
    derived=derive(rows,128);assert derived==derive(rows,192)
    projection=[int(s,16) for s in a.rom.read_text().splitlines()]
    corrections=[];matches=[]
    for i in range(193,270):
        original=int(rows[i]['sig68'],16)
        sig=derived.get(i,original)
        if sig!=original:
            corrections.append(dict(p5_row=i,original=f'{original:017x}',derived=f'{sig:017x}'))
        k=({193:0x30,194:0x31,195:0x3e,196:0x32}.get(i)
           if i<197 else (0x33+i-197 if i<=205 else (0xb5+i-206 if i<=237 else 0xd5+i-238)))
        assert sig >> 3 == projection[k],(i,k)
        matches.append(dict(p5_row=i,goldmont_row=k,projected_sig=f'{sig>>3:016x}'))
    assert [r['p5_row'] for r in corrections]==[207,245,259,268]
    slices={}
    for name,low,high in (('direct',0x6cb5,0x6ce2),('table',0x6e8c,0x6ec2),('p1_tiny',0x5b64,0x5b72)):
        records=[]
        for line in a.listing.read_text().splitlines():
            m=re.match(r'U([0-9a-f]+): ([0-9a-f]{12})\s+(.*)',line)
            if not m or not low<=int(m[1],16)<=high:continue
            w=int(m[2],16)
            records.append(dict(address=m[1],word=m[2],opcode=f'{(w>>32)&4095:03x}',
                destination=(w>>12)&63,source1=(w>>6)&63,source0=w&63,immediate=(w>>24)&255))
        slices[name]=records
    report=dict(status='PUBLIC_LOGARITHM_SOURCE_AUDIT_COMPLETE',sources=URLS,source_sha256=PINS,
        projection_matches=len(matches),matches=matches,corrections=corrections,slices=slices,
        derivation='RN40(log2(1+n/64)), followed by signed RN67 of the residual; independent Decimal precisions 128 and 192 agree.',
        limits='Goldmont is not Skylake. Its ROM dump exposes only upper-64-bit significand projections, not signs, exponents or low bits. Operation semantics and dispatch remain hypotheses until independently tested on Skylake.')
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],projection_matches=len(matches),corrections=corrections)),flush=True)


if __name__=='__main__':main()
