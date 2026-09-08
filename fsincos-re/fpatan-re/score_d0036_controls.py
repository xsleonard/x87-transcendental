"""Score frozen restoration controls and nonzero discarded-history groups.

No hardware retry is possible here: only the authenticated saved D0036
observation is read. Groups are defined from pre-frozen source parameters,
retained state and mode, never from newly observed result agreement.
"""
from collections import Counter, defaultdict
from contextlib import ExitStack
from fractions import Fraction as Q
import gzip
import json
from pathlib import Path

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from prepare import save
from prepare_d0036 import CONTROLS
from protocol import validate_output

BASE = Path(__file__).resolve().parent.parent / 'tmp/fpatan-re'


def main():
    job = BASE / 'd0036'
    hypothesis_path = job / 'STRUCTURAL-HYPOTHESIS.json'
    hypothesis = json.loads(hypothesis_path.read_text())
    dispatch = json.loads((job / 'DISPATCHED.json').read_text())
    complete = json.loads((job / 'COMPLETE.json').read_text())
    baseline_score = json.loads((job / 'SCORE.json').read_text())
    assert dispatch['structural_hypothesis_sha256'] == digest(hypothesis_path)
    assert digest(job / 'MANIFEST.json') == hypothesis['manifest_sha256'] == complete['manifest_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    for name in CONTROLS:
        assert digest(job / (name + '.txt.gz')) == hypothesis['prediction_sha256'][name]
    counts = {name: Counter() for name in CONTROLS}
    rows, base_misses = 0, []
    histories = defaultdict(dict)
    families = Counter()
    with ExitStack() as stack:
        streams = [stack.enter_context(gzip.open(job / name, 'rt')) for name in
                   ('inputs.txt.gz', 'hardware.txt.gz', 'predictions.txt.gz', 'categories.tsv.gz')]
        streams += [stack.enter_context(gzip.open(job / (name + '.txt.gz'), 'rt')) for name in CONTROLS]
        for line, actual, fixed, category, *alternatives in zip(*streams, strict=True):
            observed = validate_output(actual, line)
            ident, rc, pc, ys, ym, xs, xm = line.split()
            cid, family = category.rstrip().split('\t')
            assert fixed.split()[0] == cid == ident
            baseline = tuple(int(word, 16) for word in fixed.split()[1:])
            hardware = (observed['se'], observed['sig'], observed['C1'], observed['sw'] & 63, observed['before'] & 63)
            rows += 1
            families[family.split(':')[0]] += 1
            if baseline != hardware:
                base_misses.append(dict(input=line.strip(), category=family,
                                        baseline=baseline, hardware=hardware))
            for name, prediction in zip(CONTROLS, alternatives, strict=True):
                assert prediction.split()[0] == ident
                alternate = tuple(int(word, 16) for word in prediction.split()[1:])
                counts[name]['rows'] += 1
                counts[name]['output_misses'] += alternate[:2] != hardware[:2]
                counts[name]['C1_misses'] += alternate[2] != hardware[2]
                counts[name]['exception_misses'] += alternate[3:] != hardware[3:]
                counts[name]['union_misses'] += alternate != hardware
                counts[name]['both_models_miss'] += alternate != hardware and baseline != hardware
                counts[name]['predicted_union_separators'] += alternate != baseline
            if family.startswith('nonzero-cut-history:'):
                group = int(family.split(':')[1][5:])
                y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
                state = audit.reduction(audit.core_key(y, x))
                assert state['path'] == 'table' and state['z']
                event = audit.event(state['denominator'], 67)
                remainder = Q(event['numerator'], event['denominator'])
                assert remainder
                q = 2 * int(audit.normalized(y) > audit.normalized(x)) + bool(x.se & 32768)
                key = (group, q, bool(y.se & 32768), rc, pc)
                raw = tuple(line.split()[3:])
                assert raw not in histories[key]
                histories[key][raw] = dict(result=hardware, remainder=remainder,
                                           state=(state['cell'], audit.wire(state['z'])))
    assert rows == complete['rows'] == baseline_score['counts']['rows']
    for name in CONTROLS:
        assert counts[name]['predicted_union_separators'] == hypothesis['counts'][name]['union_separators']
    group_counts = Counter()
    split_groups = []
    for key, members in histories.items():
        values = list(members.values())
        group_counts[f'observed_members{len(values)}'] += 1
        assert len({v['state'] for v in values}) == 1
        assert len({v['remainder'] for v in values}) == len(values)
        if len(values) < 2:
            continue
        group_counts['multi_member_equal_nonzero_z_different_cut_groups'] += 1
        split = len({v['result'] for v in values}) > 1
        group_counts['hardware_result_or_flag_splits'] += split
        if split:
            split_groups.append(dict(group=key, raw_members=list(members)))
    save(job / 'RESTORATION-CONTROL-SCORE.json', dict(status='FROZEN_RESTORATION_AND_CUT_HISTORY_SCORED',
        rows=rows, baseline_union_misses=len(base_misses), baseline_misses=base_misses,
        controls=counts, family_observations=families,
        same_retained_state_groups=group_counts, split_groups=split_groups,
        hypothesis_sha256=digest(hypothesis_path), hardware_sha256=complete['hardware_sha256'],
        baseline_score_sha256=digest(job / 'SCORE.json'), script_sha256=digest(Path(__file__)),
        new_hardware_executed=False, numerical_model_changed=False, paper_changed=False,
        limits='A bounded prospective test on the observed Skylake context, not exhaustive hardware equivalence.'))
    print(json.dumps(dict(rows=rows, baseline_union_misses=len(base_misses),
                         controls=counts, same_retained_state_groups=group_counts), indent=2), flush=True)


if __name__ == '__main__':
    main()
