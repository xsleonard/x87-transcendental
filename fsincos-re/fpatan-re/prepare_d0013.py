"""Freeze a quotient-state discriminator, not a claimed solution challenge.

The fresh external operands were proved to share each anchor's CHOP67 lead
while spanning its discarded remainder. Existing observations are anchors,
never re-captured. The generic frozen V4 predictions are retained as a
known-incomplete baseline; the separate invariant prediction is the test.
"""
import gzip
import json
from d0010_causal_intervals import BASE
from d0012_quotient_discriminators import SEED
from freeze_stream import freeze
from compressed_guard import digest
from model import cut,F,pow2
from prepare import save

PLAN=BASE/'d0012-quotient-discriminators.json'


def generate():
    data=json.loads(PLAN.read_text());assert data['status']=='GENERATED_NOT_CLEARED_OR_CAPTURED'
    for group in data['groups']:
        for i,pair in enumerate(group['pairs']):yield tuple(pair['raw']),f'quotient-state-{group["index"]:03d}-fraction-{i:02d}'


def main():
    plan=json.loads(PLAN.read_text());assert plan['seed']==SEED and not plan['hardware_executed']
    freeze('d0013',SEED,generate,('prepare_d0013.py','d0012_quotient_discriminators.py'),
           purpose='Structural quotient-state discrimination: fresh exact ratios sharing known failing C67 leads; V4 baseline is already falsified')
    job=BASE/'d0013';lookup={tuple(p['raw']):(g,p) for g in plan['groups'] for p in g['pairs']}
    predictions=[];groups={};extra_pc=0
    with gzip.open(job/'inputs.txt.gz','rt') as f:
        for line in f:
            t=line.split();raw=tuple(int(v,16) for v in t[3:]);group,pair=lookup[raw]
            ys,ym,xs,xm=raw;r=F(ym,xm)*pow2((ys&32767)-(xs&32767))
            assert str(cut(r,'chop67'))==group['z']
            if t[2]!='64':extra_pc+=1;continue
            anchor=next(r for r in group['anchor_rows'] if r['rc']==t[1])
            predictions.append(dict(input=line.strip(),group=group['index'],z=group['z'],
                discarded_fraction=pair['discarded_fraction'],anchor_input=anchor['input'],
                expected_output=[anchor['se'],anchor['sig'],anchor['C1']]))
            groups.setdefault(group['index'],set()).add(raw)
    assert len(predictions)>0 and all(len(v)==16 for v in groups.values()) and len(groups)==137
    save(job/'STRUCTURAL-HYPOTHESIS.json',dict(status='FROZEN_QUOTIENT_INVARIANCE_UNOPENED',
        manifest_sha256=digest(job/'MANIFEST.json'),input_sha256=digest(job/'inputs.txt.gz'),
        plan_sha256=digest(PLAN),source_frontier_sha256=plan['source_frontier_sha256'],
        hypothesis='Normal direct FPATAN output/C1 depends only on CHOP67(y/x), signs and architectural controls; no discarded quotient state is consumed.',
        anchor_states=len(groups),fresh_PC64_rows=len(predictions),additional_PC_rows=extra_pc,
        predictions=predictions,hardware_executed=False,
        limits='Matching this bank does not prove universal quotient sufficiency; any split falsifies this hypothesis. V4 baseline scores are not closure claims.'))
    print('FROZEN structural predictions',len(predictions),'fresh PC64 rows;',len(groups),'anchor states',flush=True)


if __name__=='__main__':main()
