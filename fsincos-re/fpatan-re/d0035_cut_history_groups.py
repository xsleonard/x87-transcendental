"""Construct nonzero same-z groups with different nonzero denominator cuts.

Use dyadic exact external ratios m/2**K near every table center. Pick d so
2**(-d) <= m/2**K < 2**(1-d), and raw significands
    y_sig=m*B, y_exp=16383-d; x_sig=B*2**(K-d), x_exp=16383.
Integer bounds on B guarantee both are full normal raw80 operands. Their
exact ratio is fixed, but the CHOP67 denominator remainder can differ.
Keep a group only after checking equal nonzero z and >=3 distinct nonzero
cut remainders. Thus exact-ratio equality alone never admits a group.
All input selection is software-only and independent of hardware labels.
"""
from collections import Counter, defaultdict
from fractions import Fraction as Q
import json
from pathlib import Path
import random

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def construct(cell, m, k, b):
    d = -audit.exponent(Q(m, 1 << k))
    raw = (16383 - d, m * b, 16383, b << (k - d))
    assert all(1 << 63 <= raw[i] < 1 << 64 for i in (1, 3))
    y, x = audit.Raw80(*raw[:2]), audit.Raw80(*raw[2:])
    assert audit.SPEC['decode'](y) / audit.SPEC['decode'](x) == Q(m, 1 << k)
    state = audit.reduction(audit.core_key(y, x))
    assert state['path'] == 'table' and state['cell'] == cell and state['z']
    assert audit.T(state['numerator'], 67) == state['numerator']
    event = audit.event(state['denominator'], 67)
    remainder = Q(event['numerator'], event['denominator'])
    return raw, state, remainder


def main():
    out = BASE / 'd0035-cut-history-groups'
    out.mkdir(exist_ok=False)
    sources = {name: digest(HERE / name) for name in
               ('d0035_cut_history_groups.py', 'd0031_internal_rounding_coverage.py',
                'PSEUDOCODE.md', 'fpatan_candidate.c')}
    save(out / 'STARTED.json', dict(status='SOFTWARE_CUT_HISTORY_MINING_RUNNING',
                                  source_sha256=sources, hardware_executed=False))
    rng = random.Random('fpatan-d0035-nonzero-cut-history-20260906')
    groups = defaultdict(dict)
    counts, cell_counts = Counter(), Counter()
    pool = out / 'candidate-pool.tsv'
    with pool.open('x') as target:
        target.write('cell m K B y_se y_sig x_se x_sig z_m z_e discarded_fraction\n')
        for cell in range(2, 33):
            for sign in (-1, 1):
                if cell == 32 and sign == 1:
                    continue
                for offset in (1, 7, 31, 63):
                    k, m = 12, cell * 128 + sign * offset
                    d = -audit.exponent(Q(m, 1 << k))
                    unit = 1 << (k - d)
                    lo = max(((1 << 63) + unit - 1) // unit, ((1 << 63) + m - 1) // m)
                    hi = min(((1 << 64) - 1) // unit, ((1 << 64) - 1) // m)
                    assert hi - lo > 512
                    candidates = {lo, lo + 1, hi - 1, hi}
                    candidates.update(rng.sample(range(lo + 2, hi - 1), 124))
                    for b in sorted(candidates):
                        raw, state, rem = construct(cell, m, k, b)
                        z = audit.wire(state['z'])
                        spelling = [f'{raw[0]:04x}', f'{raw[1]:016x}', f'{raw[2]:04x}', f'{raw[3]:016x}']
                        target.write(' '.join(map(str, (cell, m, k, b, *spelling, *z, rem))) + '\n')
                        counts['candidate_pairs'] += 1
                        cell_counts[f'cell{cell}:nonzero_cut{int(bool(rem))}'] += 1
                        if rem:
                            key = (cell, m, k, z)
                            groups[key].setdefault(rem, dict(raw=spelling, B=b, remainder=str(rem)))
    selected = []
    for (cell, m, k, z), by_remainder in sorted(groups.items()):
        counts['nonzero_z_cut_groups'] += 1
        if len(by_remainder) < 3:
            counts['groups_with_fewer_than_three_distinct_nonzero_remainders'] += 1
            continue
        fractions = sorted(by_remainder)
        chosen = sorted({fractions[0], fractions[len(fractions) // 2], fractions[-1]})
        assert len(chosen) == 3
        rows = [by_remainder[f] for f in chosen]
        # Independent complete published calls, not just a reduced-state key.
        values = []
        for row in rows:
            ys, ym, xs, xm = (int(v, 16) for v in row['raw'])
            values.append(audit.SPEC['finite_angle'](audit.Raw80(ys, ym), audit.Raw80(xs, xm)))
        assert len(set(values)) == 1
        selected.append(dict(id=len(selected), cell=cell, m=m, K=k, z_wire=z,
                             available_remainders=len(by_remainder), members=rows))
    counts['selected_three_member_groups'] = len(selected)
    counts['selected_pairs'] = 3 * len(selected)
    assert selected
    for name, expected in sources.items():
        assert digest(HERE / name) == expected
    save(out / 'REPORT.json', dict(status='SOFTWARE_CERTIFIED_NONZERO_CUT_HISTORY_GROUPS',
        counts=counts, cell_coverage=cell_counts, groups=selected, pool_sha256=digest(pool),
        source_sha256=sources, hardware_executed=False, hardware_labels_opened=False,
        capture_manifest_frozen=False, private_history_checked=False,
        limits='Bounded exact-ratio family; absent three-remainder groups are not general impossibility claims.'))
    print('PASS nonzero-cut same-z groups:', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
