"""Score the frozen correction-halfway control against saved one-shot data."""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from prepare import save
from prepare_d0040 import CONTROL, positive_values
from protocol import validate_output

BASE = Path(__file__).resolve().parent.parent / 'tmp/fpatan-re'


def main():
    job = BASE / 'd0040'
    hypothesis = json.loads((job / 'STRUCTURAL-HYPOTHESIS.json').read_text())
    dispatch = json.loads((job / 'DISPATCHED.json').read_text())
    complete = json.loads((job / 'COMPLETE.json').read_text())
    baseline_score = json.loads((job / 'SCORE.json').read_text())
    assert dispatch['structural_hypothesis_sha256'] == digest(job / 'STRUCTURAL-HYPOTHESIS.json')
    assert hypothesis['manifest_sha256'] == complete['manifest_sha256'] == digest(job / 'MANIFEST.json')
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert digest(job / (CONTROL + '.txt.gz')) == hypothesis['alternative_predictions_sha256']
    counts, families, mode_separators = Counter(), Counter(), Counter()
    parity_separators = Counter()
    groups = defaultdict(dict)
    misses = []
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'hardware.txt.gz', 'rt') as actual, \
         gzip.open(job / 'predictions.txt.gz', 'rt') as fixed, \
         gzip.open(job / (CONTROL + '.txt.gz'), 'rt') as other, \
         gzip.open(job / 'categories.tsv.gz', 'rt') as categories:
        for line, observation, baseline, alternative, category in zip(inputs, actual, fixed, other, categories, strict=True):
            observed = validate_output(observation, line)
            ident, rc, pc, ys, ym, xs, xm = line.split()
            cid, family = category.rstrip().split('\t')
            assert cid == ident == baseline.split()[0] == alternative.split()[0]
            reference = tuple(int(word, 16) for word in baseline.split()[1:])
            control = tuple(int(word, 16) for word in alternative.split()[1:])
            hardware = observed['se'], observed['sig'], observed['C1'], observed['sw'] & 63, observed['before'] & 63
            counts['rows'] += 1
            counts['baseline_union_misses'] += reference != hardware
            counts['control_output_misses'] += control[:2] != hardware[:2]
            counts['control_C1_misses'] += control[2] != hardware[2]
            counts['control_exception_misses'] += control[3:] != hardware[3:]
            counts['control_union_misses'] += control != hardware
            counts['predicted_union_separators'] += reference != control
            counts['both_models_miss'] += reference != hardware and control != hardware
            families[family.split(':')[0]] += 1
            mode_separators[rc] += reference != control
            if reference != control:
                y = audit.Raw80(int(ys, 16), int(ym, 16))
                x = audit.Raw80(int(xs, 16), int(xm, 16))
                _, _, tie, parity = positive_values(audit.core_key(y, x))
                assert tie
                parity_separators[str(parity)] += 1
            if reference != hardware:
                misses.append(dict(input=line.strip(), family=family, reference=reference, hardware=hardware))
            if family.startswith('visible-correction-scale:'):
                y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
                state = audit.reduction(audit.core_key(y, x))
                q = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
                key = family.split(':')[1], q, bool(y.se & 32768), rc, pc
                raw = tuple(line.split()[3:])
                assert raw not in groups[key]
                groups[key][raw] = (audit.wire(state['z']), hardware)
    assert counts['rows'] == complete['rows'] == baseline_score['counts']['rows']
    assert counts['predicted_union_separators'] == hypothesis['counts']['union_separators']
    invariance, split_groups = Counter(), []
    for key, group in groups.items():
        invariance[f'groups_with_{len(group)}_members'] += 1
        assert len({v[0] for v in group.values()}) == 1
        if len(group) < 2:
            continue
        invariance['multi_member_scale_groups'] += 1
        split = len({v[1] for v in group.values()}) > 1
        invariance['hardware_splits'] += split
        if split:
            split_groups.append(dict(group=key, members=list(group)))
    save(job / 'CORRECTION-CONTROL-SCORE.json', dict(status='FROZEN_CORRECTION_HALF_CONTROL_SCORED',
        counts=counts, baseline_misses=misses, family_observations=families,
        mode_separators=mode_separators, exact_scale_groups=invariance, split_groups=split_groups,
        parity_separators=parity_separators,
        hypothesis_sha256=digest(job / 'STRUCTURAL-HYPOTHESIS.json'),
        hardware_sha256=complete['hardware_sha256'], baseline_score_sha256=digest(job / 'SCORE.json'),
        script_sha256=digest(Path(__file__)), new_hardware_executed=False,
        numerical_model_changed=False, paper_changed=False,
        limits='A bounded prospective test on the guest-reported Skylake context. Exact ties at this node do not cover the remaining polynomial additions or all raw80 inputs.'))
    print(json.dumps(dict(counts=counts, scales=invariance, families=families), indent=2), flush=True)


if __name__ == '__main__':
    main()
