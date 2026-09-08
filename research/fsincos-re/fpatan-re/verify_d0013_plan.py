"""Integer-only proof of every frozen quotient-collision input relation.

No model arithmetic or new hardware result is read. Quotients and discarded
fractions are obtained directly by integer division of raw significands.
"""
import collections
from fractions import Fraction as F
import gzip
import json
from d0010_causal_intervals import BASE
from compressed_guard import digest
from prepare import save


def quotient(raw):
    ys,ym,xs,xm=raw;assert not xs&32768 and 0<(ys&32767)<32767 and 0<xs<32767
    assert 1<<63<=ym<1<<64 and 1<<63<=xm<1<<64
    d=(ys&32767)-xs;e=d-int(ym<xm)
    assert -40<=e<=-5 and d<0 and 64*ym<3*xm*(1<<(-d))
    q,rem=divmod(ym<<(66+d-e),xm)
    assert 1<<66<=q<1<<67
    return q,e,F(rem,xm)


def main():
    job=BASE/'d0013';h=json.loads((job/'STRUCTURAL-HYPOTHESIS.json').read_text())
    p=json.loads((BASE/'d0012-quotient-discriminators.json').read_text())
    assert digest(BASE/'d0012-quotient-discriminators.json')==h['plan_sha256']
    assert digest(job/'inputs.txt.gz')==h['input_sha256']
    lookup={tuple(x['raw']):(g,x) for g in p['groups'] for x in g['pairs']}
    groups=collections.defaultdict(set);rows=0
    with gzip.open(job/'inputs.txt.gz','rt') as f:
        for line in f:
            raw=tuple(int(t,16) for t in line.split()[3:]);g,x=lookup[raw]
            old=tuple(int(t,16) for t in g['anchor_input'].split()[3:])
            assert raw[0]==old[0] and raw[2]==old[2]
            assert raw[1]*old[3]!=old[1]*raw[3]
            q,e,rem=quotient(raw);oldq,olde,_=quotient(old)
            assert (q,e)==(oldq,olde) and rem==F(x['discarded_fraction'])
            z=F(q)*(F(2)**(e-66));assert z==F(g['z'])
            groups[g['index']].add(raw);rows+=1
    assert len(groups)==137 and all(len(v)==16 for v in groups.values())
    save(job/'STRUCTURAL-PROOF.json',dict(status='INTEGER_QUOTIENT_RELATION_PROOF_PASS',
        rows=rows,anchor_states=len(groups),distinct_new_pairs=sum(map(len,groups.values())),
        exact_ratio_changed=True,signs_and_exponents_unchanged=True,CHOP67_quotient_identical=True,
        discarded_fractions_independently_replayed=True,hypothesis_sha256=digest(job/'STRUCTURAL-HYPOTHESIS.json'),
        input_sha256=h['input_sha256'],new_hardware_labels_opened=False))
    print('PASS integer quotient proof',rows,'rows;',len(groups),'anchor states',flush=True)


if __name__=='__main__':main()
