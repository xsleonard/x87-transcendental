"""Score the frozen quotient-invariance relation, separately from V4.

Authenticates every captured row and the prediction hash pinned before
dispatch. A split is evidence against a quotient-only state, not permission
to fit a new operand selector. All mismatches and inputs are retained.
"""
import collections
import gzip
import hashlib
import itertools
import json
from d0010_causal_intervals import BASE
from compressed_guard import digest
from protocol import validate_output
from prepare import save


def main():
    job=BASE/'d0013';m=json.loads((job/'MANIFEST.json').read_text());c=json.loads((job/'COMPLETE.json').read_text())
    h=json.loads((job/'STRUCTURAL-HYPOTHESIS.json').read_text());d=json.loads((job/'DISPATCHED.json').read_text())
    assert digest(job/'STRUCTURAL-HYPOTHESIS.json')==d['structural_hypothesis_sha256']
    assert digest(job/'MANIFEST.json')==c['manifest_sha256']==h['manifest_sha256']
    assert digest(job/'inputs.txt.gz')==m['files']['inputs.txt.gz']==h['input_sha256']
    assert digest(job/'hardware.txt.gz')==c['hardware_gzip_sha256']
    predictions={p['input'].split()[0]:p for p in h['predictions']};counts=collections.Counter();misses=[];split_states=set();split_pairs=set()
    values=collections.defaultdict(set);sha=hashlib.sha256()
    with gzip.open(job/'inputs.txt.gz','rt') as inputs,gzip.open(job/'hardware.txt.gz','rt') as hardware:
        for line,out in itertools.zip_longest(inputs,hardware):
            assert line is not None and out is not None
            sha.update(out.encode());counts['authenticated_rows']+=1;o=validate_output(out,line);t=line.split()
            if t[2]!='64':counts['additional_PC_rows']+=1;continue
            p=predictions[t[0]];assert line.strip()==p['input'];got=(o['se'],o['sig'],o['C1']);want=tuple(p['expected_output'])
            counts['structural_rows']+=1;output_miss=got[:2]!=want[:2];c1_miss=got[2]!=want[2]
            counts['output_splits']+=output_miss;counts['C1_splits']+=c1_miss;counts['union_splits']+=output_miss or c1_miss
            values[p['group'],t[1]].add(got)
            if output_miss or c1_miss:
                split_states.add(p['group']);split_pairs.add(tuple(t[3:]))
                misses.append(dict(**p,observed=got,output_split=output_miss,C1_split=c1_miss,hardware_row=out.strip()))
    assert counts['authenticated_rows']==c['rows']==m['rows'] and sha.hexdigest()==c['hardware_sha256']
    assert counts['structural_rows']==h['fresh_PC64_rows']==len(predictions)
    counts['anchor_states']=h['anchor_states'];counts['split_anchor_states']=len(split_states);counts['split_operand_pairs']=len(split_pairs)
    counts['fresh_group_RC_variations']=sum(len(v)>1 for v in values.values())
    save(job/'STRUCTURAL-SCORE.json',dict(status='QUOTIENT_INVARIANCE_FALSIFIED' if misses else 'QUOTIENT_INVARIANCE_SUPPORTED_ON_THIS_BANK_ONLY',
        counts=dict(counts),misses=misses,hardware_sha256=sha.hexdigest(),
        hypothesis_sha256=d['structural_hypothesis_sha256'],frozen_before_dispatch=True,paper_changed=False,
        limits='This is a state-observability test, not validation or promotion of V4, V5, or any new FPATAN algorithm.'))
    print(json.dumps(dict(counts),indent=2),flush=True)


if __name__=='__main__':main()
