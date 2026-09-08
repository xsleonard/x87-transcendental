"""Compare frozen tie-rule predictions with a single completed capture."""
from collections import Counter
import gzip
import json
from pathlib import Path

from compressed_guard import digest
from prepare import save
from protocol import validate_output

HERE = Path(__file__).resolve().parent
JOB = HERE.parent / 'tmp/fpatan-re/d0046'


def main():
    hypothesis = json.loads((JOB / 'STRUCTURAL-HYPOTHESIS.json').read_text())
    complete = json.loads((JOB / 'COMPLETE.json').read_text())
    baseline_score = json.loads((JOB / 'SCORE.json').read_text())
    dispatch = json.loads((JOB / 'DISPATCHED.json').read_text())
    assert digest(JOB / 'STRUCTURAL-HYPOTHESIS.json') == dispatch['structural_hypothesis_sha256']
    assert digest(JOB / 'MANIFEST.json') == complete['manifest_sha256'] == hypothesis['manifest_sha256']
    assert digest(JOB / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert digest(JOB / 'CONTROL-DIFFERENCES.jsonl.gz') == hypothesis['sparse_predictions_sha256']
    overrides = {}
    with gzip.open(JOB / 'CONTROL-DIFFERENCES.jsonl.gz', 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            key = row['id'], row['node']
            assert key not in overrides
            overrides[key] = row
    counts, consumed, examples = Counter(), set(), []
    with gzip.open(JOB / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(JOB / 'predictions.txt.gz', 'rt') as predictions, \
         gzip.open(JOB / 'hardware.txt.gz', 'rt') as hardware:
        for line, fixed, actual in zip(inputs, predictions, hardware, strict=True):
            observed = validate_output(actual, line)
            ident = line.split()[0]
            assert fixed.split()[0] == ident
            baseline = tuple(int(word, 16) for word in fixed.split()[1:])
            value = observed['se'], observed['sig'], observed['C1'], observed['sw'] & 63, observed['before'] & 63
            counts['rows'] += 1
            counts['baseline_union_misses'] += baseline != value
            for node in range(4):
                row = overrides.get((ident, node))
                opposite = tuple(row['alternative']) if row else baseline
                if row:
                    consumed.add((ident, node))
                    counts[f'node{node}:separators:parity{row["parity"]}'] += 1
                    if len(examples) < 12:
                        examples.append(dict(input=line.strip(), node=node, parity=row['parity'],
                            baseline=baseline, opposite=opposite, observed=value))
                for rule in ('nearest-even', 'nearest-odd', 'ties-away', 'ties-zero'):
                    use_opposite = row and (rule == 'nearest-odd' or
                        (rule == 'ties-away' and row['parity'] == 0) or
                        (rule == 'ties-zero' and row['parity'] == 1))
                    prediction = opposite if use_opposite else baseline
                    counts[f'node{node}:{rule}:union_misses'] += prediction != value
                    counts[f'node{node}:{rule}:output_misses'] += prediction[:2] != value[:2]
                    counts[f'node{node}:{rule}:C1_misses'] += prediction[2] != value[2]
    assert consumed == set(overrides)
    assert counts['rows'] == complete['rows'] == baseline_score['counts']['rows']
    for node in range(4):
        for parity in (0, 1):
            key = f'node{node}:separators:parity{parity}'
            assert counts[key] == hypothesis['counts'].get(key, 0)
    save(JOB / 'TIE-RULE-SCORE.json', dict(status='FROZEN_FOUR_TIE_RULES_SCORED',
        counts=counts, examples=examples, hypothesis_sha256=digest(JOB / 'STRUCTURAL-HYPOTHESIS.json'),
        baseline_score_sha256=digest(JOB / 'SCORE.json'), hardware_sha256=complete['hardware_sha256'],
        scorer_sha256=digest(Path(__file__)), hardware_executed=False, numerical_model_changed=False,
        limits='A rule with no separating observations is not identified. Results distinguish these fixed rules at exposed nodes within the unchanged graph, not arbitrary state-dependent silicon behavior.'))
    print(json.dumps(counts, indent=2), flush=True)


if __name__ == '__main__':
    main()
