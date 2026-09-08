"""Exact width certificate for the fixed graph's table-reduction numerator.

Normalize both finite nonzero raw80 magnitudes as M*2**(E-63), including
subnormals and pseudo-denormals by exact left shifts. On the table path,
3/64 < a/b <= 1, hence d=E_b-E_a is in 0..5. Write n=odd*2**t and
j=max(d,5-t). Then a-(n/32)b is a power of two times the integer
N=M_a*2**(j-d)-odd*M_b*2**(j-(5-t)). Nearest-cell selection gives
|a-(n/32)b| <= b/64, so |N| <= M_b*2**(j-6) < 2**63.

The finite exact polygon certificate below independently checks all 186
cell/exponent-separation regions. It relaxes strict boundaries outward and
enumerates every vertex of each bounded rational polygon. This is a theorem
of the stated reduction graph, not a silicon width decode or permission to
truncate an intermediate product before cancellation.
"""
from fractions import Fraction as Q
from itertools import combinations
import json
from pathlib import Path

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
LOW, HIGH = 1 << 63, (1 << 64) - 1


def vertices(constraints):
    answer = set()
    for (a, b, c), (d, e, f) in combinations(constraints, 2):
        det = a * e - b * d
        if not det:
            continue
        x, y = Q(c * e - b * f, det), Q(a * f - c * d, det)
        if all(p * x + q * y <= r for p, q, r in constraints):
            answer.add((x, y))
    return sorted(answer)


def build():
    regions = []
    largest = Q(0)
    for n in range(2, 33):
        t = (n & -n).bit_length() - 1
        odd = n >> t
        for d in range(6):
            # Continuous outer relaxation of all normalized integer operands.
            constraints = [(1, 0, HIGH), (-1, 0, -LOW),
                           (0, 1, HIGH), (0, -1, -LOW),
                           (1, -(1 << d), 0),
                           (-64, (2 * n - 1) << d, 0),
                           (64, -((2 * n + 1) << d), 0)]
            points = vertices(constraints)
            j = max(d, 5 - t)
            p, q = 1 << (j - d), odd << (j - (5 - t))
            maximum = max((abs(p * x - q * y) for x, y in points), default=Q(0))
            assert maximum < 1 << 63
            largest = max(largest, maximum)
            regions.append(dict(cell=n, exponent_separation=d, alignment=j,
                numerator_coefficients=[p, -q], constraints=constraints,
                feasible=bool(points), vertices=[[str(x), str(y)] for x, y in points],
                max_absolute_aligned_numerator=str(maximum)))
    # A valid table-path witness with an odd 63-bit numerator proves that
    # lowering the exactness statement to 62 significant bits would be false.
    y = audit.Raw80(16383 - 5, (15 << 60) + 1)
    x = audit.Raw80(16383, 5 << 61)
    state = audit.reduction(audit.core_key(y, x))
    assert state['path'] == 'table' and state['cell'] == 2
    numerator = state['numerator']
    n = abs(numerator.numerator)
    significant = n.bit_length() - ((n & -n).bit_length() - 1)
    assert significant == 63
    assert audit.T(numerator, 63) == numerator and audit.T(numerator, 62) != numerator
    # Exact normalization covers the architectural exponent-zero encodings.
    for raw in (audit.Raw80(0, 1), audit.Raw80(0, 3), audit.Raw80(0, (1 << 63) - 1),
                audit.Raw80(0, 1 << 63), audit.Raw80(32766, HIGH)):
        e, m = audit.normalized(raw)
        assert LOW <= m <= HIGH
        assert m * audit.two(e - 16383 - 63) == abs(audit.SPEC['decode'](raw))
    return dict(status='PROVED_TABLE_NUMERATOR_AT_MOST_63_SIGNIFICANT_BITS',
        scope='All finite nonzero normal/subnormal/pseudo raw80 operands entering the fixed nearest-cell table reduction, after magnitude ordering.',
        region_count=len(regions), feasible_regions=sum(r['feasible'] for r in regions),
        largest_relaxed_absolute_numerator=str(largest), regions=regions,
        sharpness_witness=dict(y=[f'{y.se:04x}', f'{y.sig:016x}'],
            x=[f'{x.se:04x}', f'{x.sig:016x}'], significant_bits=significant),
        consequence='The completed numerator is exact at 63 or more significant bits. It has no CHOP67 rounding remainder in this graph.',
        warning='Intermediate products can require more bits before cancellation. This does not justify cutting those products early, identify silicon widths, or prove hardware equivalence.',
        source_sha256={name:digest(HERE/name) for name in
                      ('d0038_numerator_width_certificate.py','d0031_internal_rounding_coverage.py',
                       'PSEUDOCODE.md','fpatan_candidate.c')},
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False)


if __name__ == '__main__':
    report = build()
    save(BASE / 'd0038-numerator-width-certificate.json', report)
    print('PASS exact numerator width certificate:', report['region_count'], 'regions;',
          report['feasible_regions'], 'nonempty; sharp 63-bit bound; no hardware', flush=True)
