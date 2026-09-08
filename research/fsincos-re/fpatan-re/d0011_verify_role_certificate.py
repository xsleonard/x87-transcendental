"""Independently replay the two-point final-role obstruction.

Uses original authenticated hardware rows and a separate integer rounding
implementation. No graph, inverse interval, reachable-state or role-solver
implementation is imported. ROM values alone are shared public input data.
"""
import gzip
import argparse
import hashlib
import itertools
import json
from fractions import Fraction as F
from d0011_terminal_certificate import BASE,two,decompose
from model import ROM
from protocol import validate_output
from prepare import save


def rounded(v,fmt):
    if fmt=='exact' or v==0:return v
    mode='chop' if fmt.startswith('chop') else 'rn';bits=int(fmt[len(mode):])
    n,unit=decompose(abs(v),bits);fraction=abs(v)/unit-n
    up=mode=='rn' and (fraction>F(1,2) or (fraction==F(1,2) and n&1))
    return (-1 if v<0 else 1)*(n+up)*unit


def matches(v,observations,check_c1=True):
    assert v>0
    for row in observations:
        rc=row['rc'];negative=bool(int(row['input'].split()[3],16)&32768)
        if negative:rc={'rd':'ru','ru':'rd'}.get(rc,rc)
        if rc=='rn':q=rounded(v,'rn64')
        else:
            n,unit=decompose(v,64);q=(n+int(rc=='ru' and v!=n*unit))*unit
        expected=row['sig']*two((row['se']&32767)-16383-63)
        if q!=expected or (check_c1 and int(q>v)!=row['C1']) or bool(row['se']&32768)!=negative:return False
    return True


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='d0011-role-certificate-verification.json');args=ap.parse_args()
    assert args.out.startswith('d0011-') and '/' not in args.out
    certificate_path=BASE/'d0011-fixed-role-certificate.json';report=json.loads(certificate_path.read_text())
    core=report['two_point_final_role_obstruction'];assert len(core)==2
    wanted={r['input'].split()[0]:r for p in core for g in p['rows'] for r in g['observations']}
    job=BASE/'d0009';receipt=json.loads((job/'COMPLETE.json').read_text());manifest=json.loads((job/'MANIFEST.json').read_text())
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest(job/'MANIFEST.json')==receipt['manifest_sha256']
    assert digest(job/'inputs.txt.gz')==manifest['files']['inputs.txt.gz']
    sha=hashlib.sha256();found={};count=0
    with gzip.open(job/'inputs.txt.gz','rt') as inputs,gzip.open(job/'hardware.txt.gz','rt') as hardware:
        for inp,out in itertools.zip_longest(inputs,hardware):
            assert inp is not None and out is not None
            count+=1;sha.update(out.encode());actual=validate_output(out,inp);ident=inp.split()[0]
            if ident in wanted:
                expected=wanted[ident];assert inp.strip()==expected['input']
                assert all(actual[k]==expected[k] for k in ('se','sig','C1'))
                found[ident]=out.strip()
    assert count==receipt['rows'] and sha.hexdigest()==receipt['hardware_sha256'] and found.keys()==wanted.keys()
    policies=list(itertools.product(('exact','chop64','rn64'),
        ('chop64','rn64','chop67','rn67','chop69','rn69'),
        ('chop64','rn64','chop67','rn67','chop69','rn69')))
    assert [list(p) for p in policies]==report['policies']
    results=[];allowed_sets=[]
    for p in core:
        first=p['rows'][0]['observations'][0]['input'].split();ys,ym,xs,xm=(int(v,16) for v in first[3:])
        ratio=F(ym,xm)*two((ys&32767)-(xs&32767));z=rounded(ratio,'chop67')
        u=rounded(z*rounded(z,'chop64'),'rn64');cube=rounded(z*u,'chop67')
        assert str(z)==p['z'] and str(u)==p['u']
        states={ROM[123]};counts=[]
        for k in range(122,118,-1):
            states={rounded(ROM[k]+rounded(u*rounded(h,hr),m),a)
                    for h in states for hr,m,a in policies}
            counts.append(len(states))
        assert states=={F(h) for h in p['all_reachable_h119']}
        observations=[r for g in p['rows'] for r in g['observations']];accepted=[];values=set();output_only=[]
        for i,(hr,m,a) in enumerate(policies):
            for h in states:
                hlast=rounded(ROM[118]+rounded(u*rounded(h,hr),m),a)
                if matches(z+rounded(cube*hlast,'chop67'),observations):
                    accepted.append(i);values.add(hlast);break
        assert accepted==p['allowed_final_policies']
        assert values=={F(h) for h in p['allowed_h118']}
        for i,(hr,m,a) in enumerate(policies):
            for h in states:
                hlast=rounded(ROM[118]+rounded(u*rounded(h,hr),m),a)
                if matches(z+rounded(cube*hlast,'chop67'),observations,check_c1=False):
                    output_only.append(i);break
        assert output_only==accepted,'The obstruction depends on C1; report the distinction'
        allowed_sets.append(set(accepted))
        results.append(dict(input=' '.join(first),reachable_state_counts=counts,
            accepted_policy_count=len(accepted),required_add_modes=sorted({policies[i][2] for i in accepted}),
            output_only_policy_indices=output_only,
            accepted_policy_indices=accepted,observed_rows=[found[r['input'].split()[0]] for r in observations]))
    assert not set.intersection(*allowed_sets)
    save(BASE/args.out,dict(status='INDEPENDENT_INTEGER_REPLAY_PASS',
        source_certificate_sha256=digest(certificate_path),hardware_sha256=sha.hexdigest(),
        authenticated_rows=count,core_hardware_rows=len(found),core=results,
        conclusion='No single last Horner operation policy in the stated family can satisfy both inputs.',
        obstruction_persists_without_C1=True,
        hardware_executed=False))
    print('PASS independent final-role replay;',len(found),'authenticated core observations;',
          [r['required_add_modes'] for r in results],flush=True)


if __name__=='__main__':main()
