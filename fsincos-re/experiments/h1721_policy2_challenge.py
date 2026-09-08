#!/usr/bin/env python3
"""New full-precision policy-2 challenges and independent frozen predictions.

Selection uses only software, not hardware labels. Exact stage margins refer
to the fixed graph, not to unknown silicon internals. Reduction transports
are called brackets unless the residual is exactly preserved.
"""
import argparse
import json
import random
from collections import Counter,defaultdict
from fractions import Fraction
from pathlib import Path
import h1710_verify_paired_program as I
from h1714_rounding_challenge import prediction as standalone_prediction,c_predictions
from h1719_run_saved_suite import PINS,digest,save

SCAN='tmp/ledger33/current/h1720_policy2_scan'
MASK=(1<<64)-1
SEED=0x2026090500001717


def mix(v):
    v=(v+0x9e3779b97f4a7c15)&MASK
    v=((v^(v>>30))*0xbf58476d1ce4e5b9)&MASK
    v=((v^(v>>27))*0x94d049bb133111eb)&MASK
    return v^(v>>31)


def possible_old_generator(op):
    # Exclude ALL counters of the observed public full-width generator's
    # default seed. No run length or actual execution of that binary is
    # assumed. Our candidates are normal finite nonunit inputs only, so its
    # denormal/special branches cannot produce them. Unknown override seeds
    # and unavailable records remain an explicit historical-visibility limit.
    se,sig=(int(w,16) for w in op.split());ef=se&0x7fff
    assert 0<ef<0x7fff and sig>>63 and not (ef==0x3fff and sig==1<<63)
    aa={sig,sig^(1<<63)}
    if ef==0x3ffe:
        lo=1<<63 if sig<0xc90fdaa22168c234 else 0xc90fdaa22168c234
        width=0xc90fdaa22168c234-lo if lo==1<<63 else MASK-lo
        aa.update(range(sig-lo,1<<64,width))
    for a in aa:
        b=mix(a+SEED);c=mix(b^((SEED<<1)&MASK));pick=c%1000
        candidate_sig=a|(1<<63)
        if pick<60:e=1+b%0x3fde
        elif pick<80:continue
        elif pick<430:e=0x3fdf+b%30
        elif pick<560:
            e=0x3ffd if b&1 else 0x3ffe
            if not b&1:candidate_sig=(1<<63)+a%(0xc90fdaa22168c234-(1<<63))
        elif pick<960:
            k=b%65;e=0x3ffe+k
            if not k:candidate_sig=0xc90fdaa22168c234+a%(MASK-0xc90fdaa22168c234)
        elif pick<985:e=0x403f+b%(0x7ffe-0x403f+1)
        else:continue
        if (e|(((c>>20)&1)<<15),candidate_sig)==(se,sig):return True
    return False


def stage_certificate(r):
    R=I.rational;rn=[];chop=[]
    def rounded(x,bits,mode,label):
        u=R.p2(R.top(abs(x))-bits+1);f=(abs(x)/u)%1
        item=dict(stage=label,precision=bits,fraction=str(f),margin_ulps=str(abs(f-Fraction(1,2)) if mode=='rn' else min(f,1-f)))
        (rn if mode=='rn' else chop).append(item)
        return R.rnd(x,bits,mode)[0]
    s=rounded(r*r,67,'chop','square');p=R.C['S6'][6];q=R.C['C6'][6]
    for k in (5,4,3,2,1):
        p=rounded(p*s,67,'chop',f'sine_K{k}_product');p=rounded(p+R.C['S6'][k],64,'rn',f'sine_K{k}_add')
        q=rounded(q*s,67,'chop',f'cosine_K{k}_product');q=rounded(q+R.C['C6'][k],64,'rn',f'cosine_K{k}_add')
    ps=rounded(p*s,64,'rn','sine_ps')
    st=rounded(ps*r,67,'chop','sine_tail');ct=rounded(q*s,67,'chop','cosine_tail')
    pre=(r+st,1+ct);assert pre==I.polynomial(r,'all')
    final=[]
    for lane,x in zip(('sine','cosine'),pre):
        f=(x/R.p2(R.top(x)-63))%1
        for kind in ('half','integer'):final.append(dict(stage=lane+'_final_'+kind,precision=64,
            fraction=str(f),margin_ulps=str(abs(f-Fraction(1,2)) if kind=='half' else min(f,1-f))))
    assert (len(rn),len(chop),len(final))==(11,13,4)
    return rn+chop+final


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    for name,sha in PINS.items():assert digest(root/name)==sha
    prepared=json.loads((root/SCAN/'prepared.json').read_text())
    for name,sha in prepared['sha256']['evidence'].items():assert digest(root/name)==sha,name
    assert (root/SCAN/'scan.stderr').read_text().endswith('DONE software_operands=12000000 proposals=840\n')
    I.constants(root);R=I.rational;kinds=defaultdict(set);certs=[];relations=[]
    def add(op,kind):
        se,sig=(int(w,16) for w in op.split())
        for sign in (0,0x8000):
            if sig&2047 and (1<<63)<=sig<1<<64:kinds[f'{(se&0x7fff)|sign:04x} {sig:016x}'].add(kind)
    seeds=set()
    for line in (root/SCAN/'proposals.txt').read_text().splitlines():
        se,sig,b,slot,key=line.split();op=se+' '+sig;seeds.add(op)
        certificate=stage_certificate(R.external(op,'fsin')[0])[int(slot)]
        certs.append(dict(operand=op,binade=int(b)-32,slot=int(slot),ranking_key=int(key),**certificate))
        for delta in (-1,0,1):add(f'{se} {int(sig,16)+delta:016x}','stage_'+certificate['stage'])
    # A bounded, reproducible panel around dispatch/table boundaries and
    # every reduced-input exponent supplements the mined direct-polynomial
    # cuts. Exact endpoints already in history are not deliberately recaptured.
    rng=random.Random(0x1721a11c67)
    for e in (-69,-68,-33,-32,-3,-2,-1,*range(63)):
        for _ in range(4):add(f'{e+16383:04x} {rng.getrandbits(64)|(1<<63):016x}','stratified_exponent_control')
    for se,sig in [(0x3fdf,1<<63),(0x3ffd,1<<63),(0x3ffe,0xc90fdaa22168c234),
                   *[(0x3ffd,(1<<63)+k*(1<<61)) for k in range(1,4)],
                   *[(0x3ffe,(1<<63)+k*(1<<61)) for k in range(2)]]:
        for delta in (-1,1):
            for _ in range(4):add(f'{se:04x} {sig+delta*rng.randrange(1,1<<18):016x}','dispatch_or_table_boundary_neighbourhood')
    # Use one target seed per binade (the sine K2 RN add), in both residual
    # directions, at several external exponents. These are arithmetic inverse
    # relations; when lattice rounding changes D they remain brackets.
    lift_seeds=sorted({c['operand'] for c in certs if c['stage']=='sine_K2_add'})
    for seed in lift_seeds:
        r=R.external(seed,'fsin')[0];scaled=r*R.p2(65);center=scaled.numerator//scaled.denominator
        for e in (0,4,16,32,48,62):
            modulus=1<<(e+2);inv=pow(R.M66,-1,modulus)
            for direction in (-1,1):
                for delta in (0,*[s*k for k in range(1,257) for s in (-1,1)]):
                    d=direction*(center+delta);q0=(-d*inv)%modulus
                    lower=((1<<63)*modulus-d+R.M66-1)//R.M66
                    upper=(((1<<64)-1)*modulus-d)//R.M66
                    q=q0+max(0,(lower-q0+modulus-1)//modulus)*modulus
                    if q>upper:continue
                    sig=(q*R.M66+d)//modulus
                    if not sig&2047:continue
                    op=f'{e+16383:04x} {sig:016x}';actual=R.external(op,'fsin')[0]
                    assert actual==abs(d)*R.p2(-65)
                    exact=actual==r;add(op,'exact_reduction_preimage' if exact else 'reduction_bracket')
                    relations.append(dict(seed=seed,operand=op,q=q,signed_D=str(d),exact_residual=exact,distance=str(actual-r)))
                    break
    old={op for op in kinds if possible_old_generator(op)}
    # Reject sign siblings too, to keep the signed panel balanced.
    old_sigs={op.split()[1] for op in old}
    rows=[dict(operand=op,kinds=sorted(ks),predictions={}) for op,ks in sorted(kinds.items()) if op.split()[1] not in old_sigs]
    print('proposals',len(rows),'conservative default-generator exclusions',len(kinds)-len(rows),flush=True)
    cache={};ops=[r['operand'] for r in rows];counts=Counter()
    for insn in ('fsin','fcos','fsincos'):
        for mode in ('rn','rd','ru','rz'):
            actual=c_predictions(root/'src/fsincos_skylake',insn,mode,ops)
            for row,got in zip(rows,actual):
                if insn=='fsincos':
                    value,meta=I.expected(row['operand'],mode,'all',cache)
                    expected=dict(outputs=list(value) if value else None,path=meta[0] if meta else 'range',C1=meta[3] if meta and meta[1] else None)
                else:expected=standalone_prediction(row['operand'],insn,mode,cache)
                assert expected==got,(insn,mode,row['operand'],expected,got)
                row['predictions'].setdefault(insn,{})[mode]=expected;counts['independent_instruction_rows']+=1
                counts['independent_lane_outputs']+=len(expected['outputs'] or [])
            print(insn,mode,'independent predictions PASS',flush=True)
    out.mkdir(parents=True,exist_ok=False)
    save(out/'boundary_certificate.json',dict(stages=certs,relations=relations,
        scope='Exact independent graph margins. Selection key is truncated; zero key is not a tie claim.'))
    evidence={**prepared['sha256']['evidence'],SCAN+'/prepared.json':digest(root/SCAN/'prepared.json'),
        SCAN+'/proposals.txt':digest(root/SCAN/'proposals.txt'),SCAN+'/scan.stderr':digest(root/SCAN/'scan.stderr'),
        'src/fsincos_skylake':digest(root/'src/fsincos_skylake')}
    for module in (I,I.integer,I.old_pair,R,I.tiny):evidence[str(Path(module.__file__).relative_to(root))]=digest(module.__file__)
    save(out/'bank.json',dict(experiment='h1721_policy2_challenge',capture_state='SOFTWARE_ONLY_NOT_FROZEN',
        candidate_changed=False,hardware_execution='none',operands=rows,counts=dict(counts),
        software_screened_operands=12000000,default_generator_all_counter_excluded_operands=len(kinds)-len(rows),
        generated_history_limit='Known binary64 domain excluded; all counters of public raw80 generator default seed excluded. Unknown override seeds or unavailable records are not claimed audited.',
        sha256=dict(evidence=evidence,script=digest(Path(__file__)),certificate=digest(out/'boundary_certificate.json'))))
    print(json.dumps(dict(operands=len(rows),counts=dict(counts))),flush=True)


if __name__=='__main__':main()
