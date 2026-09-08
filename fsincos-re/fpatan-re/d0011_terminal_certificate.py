"""Independent integer certificate against V5's final tail multiplication.

Reads authenticated original D0009 inputs/results, not the derived frontier.
Does not import the model, graph, inverse-rounding or lattice implementations.
For one exact observed endpoint, consecutive 67-bit predecessor products
straddle the required tail. No choice of earlier coefficients can fill this
gap. The claim is conditional on V5's fixed lead and final arithmetic.
"""
import gzip
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path
from protocol import validate_output
from prepare import save

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'
RAW=('5aeb','d8233ece2695fae0','5af1','f72cbc2401e70d7a')


def two(e):return Fraction(2**e) if e>=0 else Fraction(1,2**(-e))


def decompose(v,p):
    assert v>0
    e=v.numerator.bit_length()-v.denominator.bit_length()
    if v<two(e):e-=1
    unit=two(e-p+1);integer=(v/unit).__floor__()
    assert 2**(p-1)<=integer<2**p
    return integer,unit


def trunc(v,p):
    integer,unit=decompose(v,p)
    return integer*unit


def main():
    job=BASE/'d0009';receipt=json.loads((job/'COMPLETE.json').read_text())
    manifest=json.loads((job/'MANIFEST.json').read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(job/'MANIFEST.json')==receipt['manifest_sha256']
    assert digest(job/'inputs.txt.gz')==manifest['files']['inputs.txt.gz']
    assert digest(job/'hardware.txt.gz')==receipt['hardware_gzip_sha256']
    sha=hashlib.sha256();rows=[];count=0
    with gzip.open(job/'inputs.txt.gz','rt') as inputs,gzip.open(job/'hardware.txt.gz','rt') as hardware:
        for inp,out in itertools.zip_longest(inputs,hardware):
            assert inp is not None and out is not None
            sha.update(out.encode());count+=1;parsed=validate_output(out,inp)
            t=inp.split()
            if t[2]=='64' and tuple(t[3:])==RAW:rows.append((inp.strip(),out.strip(),parsed))
    assert count==receipt['rows'] and sha.hexdigest()==receipt['hardware_sha256']
    assert len(rows)==4 and {i.split()[1] for i,_,_ in rows}=={'rn','rd','ru','rz'}
    assert len({(o['se'],o['sig']) for _,_,o in rows})==1
    assert all(o['C1']==0 for _,_,o in rows)
    result=rows[0][2];assert result['se']<32768 and 0<result['se']<32767
    endpoint=result['sig']*two(result['se']-16383-63)
    ys,ym,xs,xm=(int(v,16) for v in RAW);assert 0<ys<xs<32767
    ratio=Fraction(ym,xm)*two(ys-xs);lead=trunc(ratio,67);outer=trunc(lead,64)
    target=lead-endpoint;assert target>0 and trunc(target,67)==target
    low=trunc(target/outer,67);n,unit=decompose(low,67);high=(n+1)*unit
    # Adjacent p-bit products, including a possible power-of-two transition.
    assert trunc(high,67)==high and low<target/outer<high
    low_tail=trunc(low*outer,67);high_tail=trunc(high*outer,67)
    assert low_tail<target<high_tail
    target_n,target_unit=decompose(target,67)
    report=dict(status='VERIFIED_EXACT_TERMINAL_GAP_CERTIFICATE',raw_input=RAW,
        authenticated_rows=count,hardware_sha256=sha.hexdigest(),
        original_rows=[dict(input=i,hardware=o) for i,o,_ in rows],
        ratio=str(ratio),lead_chop67=str(lead),outer_chop64=str(outer),endpoint=str(endpoint),
        required_tail=str(target),consecutive_first_products=[str(low),str(high)],
        resulting_tails=[str(low_tail),str(high_tail)],
        tail_ulp_distances=[str((target-low_tail)/target_unit),str((high_tail-target)/target_unit)],
        proof='Monotone CHOP67(p*CHOP64(z)) skips the required tail between consecutive CHOP67 p values.',
        assumptions=['z=CHOP67(y/x)','same RC-independent prevalue with ordinary final RC rounding',
                     'prevalue=z-CHOP67(p*CHOP64(z))','p positive and representable in 67 significand bits'],
        conclusion='No earlier polynomial, coefficient or p-producing graph can repair this terminal schedule.',
        hardware_executed=False)
    save(BASE/'d0011-terminal-certificate.json',report)
    print(report['status'],'authenticated',count,'rows; tail gaps',report['tail_ulp_distances'],flush=True)


if __name__=='__main__':main()
