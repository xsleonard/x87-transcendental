"""Score frozen sparse node controls without recapturing any input."""
from collections import Counter
import gzip
import json
from pathlib import Path

from compressed_guard import digest
from prepare import save
from protocol import validate_output

BASE = Path(__file__).resolve().parent.parent / 'tmp/fpatan-re'


def main():
    job = BASE / 'd0042'
    hypothesis = json.loads((job / 'STRUCTURAL-HYPOTHESIS.json').read_text())
    dispatch = json.loads((job / 'DISPATCHED.json').read_text())
    complete = json.loads((job / 'COMPLETE.json').read_text())
    baseline = json.loads((job / 'SCORE.json').read_text())
    assert dispatch['structural_hypothesis_sha256'] == digest(job / 'STRUCTURAL-HYPOTHESIS.json')
    assert digest(job / 'MANIFEST.json') == complete['manifest_sha256'] == hypothesis['manifest_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert digest(job / 'CONTROL-DIFFERENCES.jsonl.gz') == hypothesis['sparse_predictions_sha256']
    overrides = {}
    with gzip.open(job / 'CONTROL-DIFFERENCES.jsonl.gz', 'rt') as source:
        for line in source:
            row = json.loads(line)
            key = row['id'], row['node']
            assert key not in overrides
            overrides[key] = tuple(row['alternative'])
    counts, families = Counter(), Counter()
    consumed = set()
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'predictions.txt.gz', 'rt') as predictions, \
         gzip.open(job / 'hardware.txt.gz', 'rt') as hardware, \
         gzip.open(job / 'categories.tsv.gz', 'rt') as categories:
        for line, fixed, actual, category in zip(inputs, predictions, hardware, categories, strict=True):
            observed = validate_output(actual, line)
            reference = tuple(int(word, 16) for word in fixed.split()[1:])
            value = observed['se'], observed['sig'], observed['C1'], observed['sw'] & 63, observed['before'] & 63
            ident = line.split()[0]
            cid, family = category.rstrip().split('\t')
            assert ident == cid == fixed.split()[0]
            counts['rows'] += 1
            counts['baseline_union_misses'] += reference != value
            families[family.split(':')[0]] += 1
            for node in range(4):
                key = ident, node
                other = overrides.get(key, reference)
                if key in overrides:
                    consumed.add(key)
                counts[f'node{node}:union_misses'] += other != value
                counts[f'node{node}:predicted_separators'] += other != reference
    assert consumed == set(overrides)
    assert counts['rows'] == complete['rows'] == baseline['counts']['rows']
    for node in range(4):
        assert counts[f'node{node}:predicted_separators'] == hypothesis['counts'].get(f'node{node}:union_separators', 0)
    save(job / 'NODE-CONTROL-SCORE.json', dict(status='FROZEN_NODE_CONTROLS_SCORED',
        counts=counts, family_observations=families,
        controls_with_no_endpoint_discrimination=[n for n in range(4) if not counts[f'node{n}:predicted_separators']],
        hypothesis_sha256=digest(job / 'STRUCTURAL-HYPOTHESIS.json'),
        hardware_sha256=complete['hardware_sha256'], baseline_score_sha256=digest(job / 'SCORE.json'),
        source_sha256=digest(Path(__file__)), hardware_executed=False, numerical_model_changed=False,
        limits='A passing baseline does not distinguish an alternative with zero predicted separators. These tests add reachable-node and neighborhood coverage, not a proof of hidden tie semantics.'))
    print(json.dumps(dict(counts=counts, families=families), indent=2), flush=True)


if __name__ == '__main__':
    main()
