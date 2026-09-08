"""Score the pre-frozen square-tie control and exact retained-state groups.

This reads the single authenticated D0033 observation, never recaptures it.
Report both baseline and control misses, even if the baseline is falsified.
Group definitions use the predeclared V7 residual, not newly observed labels.
"""
from collections import Counter, defaultdict
from functools import lru_cache
import gzip
import json
from pathlib import Path

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from prepare import save
from protocol import validate_output

BASE = Path(__file__).resolve().parent.parent / 'tmp/fpatan-re'


def main():
    job = BASE / 'd0033'
    hypothesis_path = job / 'STRUCTURAL-HYPOTHESIS.json'
    hypothesis = json.loads(hypothesis_path.read_text())
    dispatch = json.loads((job / 'DISPATCHED.json').read_text())
    complete = json.loads((job / 'COMPLETE.json').read_text())
    baseline_score = json.loads((job / 'SCORE.json').read_text())
    assert dispatch['structural_hypothesis_sha256'] == digest(hypothesis_path)
    assert digest(job / 'MANIFEST.json') == hypothesis['manifest_sha256'] == complete['manifest_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert digest(job / 'square-ties-away-predictions.txt.gz') == hypothesis['alternative_predictions_sha256']
    reduction = lru_cache(maxsize=2048)(audit.reduction)
    counts, coverage, groups = Counter(), Counter(), defaultdict(list)
    discrepant = []
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, gzip.open(job / 'hardware.txt.gz', 'rt') as hardware, gzip.open(job / 'predictions.txt.gz', 'rt') as base, gzip.open(job / 'square-ties-away-predictions.txt.gz', 'rt') as other, gzip.open(job / 'categories.tsv.gz', 'rt') as categories:
        for line, actual, fixed, control, category in zip(inputs, hardware, base, other, categories, strict=True):
            observed = validate_output(actual, line)
            ident, rc, pc, ys, ym, xs, xm = line.split()
            cid, family = category.rstrip().split('\t')
            assert fixed.split()[0] == control.split()[0] == cid == ident
            bv = tuple(int(word, 16) for word in fixed.split()[1:])
            av = tuple(int(word, 16) for word in control.split()[1:])
            hv = (observed['se'], observed['sig'], observed['C1'], observed['sw'] & 63, observed['before'] & 63)
            counts['rows'] += 1
            counts['baseline_union_misses'] += bv != hv
            counts['ties_away_output_misses'] += av[:2] != hv[:2]
            counts['ties_away_C1_misses'] += av[2] != hv[2]
            counts['ties_away_exception_misses'] += av[3:] != hv[3:]
            counts['ties_away_union_misses'] += av != hv
            counts['both_models_miss'] += av != hv and bv != hv
            counts['predicted_union_separators'] += av != bv
            if bv != hv:
                discrepant.append(dict(input=line.strip(), category=family,
                                       fixed=bv, ties_away=av, observed=hv))
            y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
            state = reduction(audit.core_key(y, x))
            if state['path'] != 'tiny':
                square = audit.event(state['z'] * audit.T(state['z'], 64), 64)
                if square['relation'] == 'tie':
                    coverage[f'{state["path"]}:cell{state["cell"]}:rc{rc}:pc{pc}'] += 1
                    counts['exact_square_tie_rows'] += 1
                    counts[state['path'] + '_exact_square_tie_rows'] += 1
            if ':same-z-scale' in family:
                restore = 2 * int(audit.normalized(y) > audit.normalized(x)) + bool(x.se & 32768)
                key = (state['cell'], audit.wire(state['z']), restore, bool(y.se & 32768), rc, pc)
                groups[key].append(hv)
    group_counts = Counter()
    for values in groups.values():
        if len(values) < 2:
            continue
        group_counts['multi_member_same_z_groups'] += 1
        group_counts[f'members{len(values)}'] += 1
        group_counts['hardware_endpoint_or_flag_splits'] += len(set(values)) > 1
    assert counts['rows'] == complete['rows'] == baseline_score['counts']['rows']
    assert counts['predicted_union_separators'] == hypothesis['counts']['union_separators']
    save(job / 'SQUARE-CONTROL-SCORE.json', dict(status='FROZEN_SQUARE_CONTROL_SCORED',
        counts=counts, exact_tie_observation_coverage=coverage,
        same_retained_state_groups=group_counts, baseline_misses=discrepant,
        hypothesis_sha256=digest(hypothesis_path), hardware_sha256=complete['hardware_sha256'],
        baseline_score_sha256=digest(job / 'SCORE.json'),
        script_sha256=digest(Path(__file__)), new_hardware_executed=False,
        numerical_model_changed=False, paper_changed=False,
        limits='One frozen challenge on the observed Skylake reference. No universal or cross-CPU proof.'))
    print(json.dumps(dict(counts=counts, same_retained_state_groups=group_counts), indent=2))


if __name__ == '__main__':
    main()
