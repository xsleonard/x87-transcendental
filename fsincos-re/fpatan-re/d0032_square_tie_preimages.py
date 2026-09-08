"""Construct exact external square-tie preimages and mine visible challenges.

For odd 2**32 < v < sqrt(2**65), z=v*2**(E-32) is an exact
RN64(z*CHOP64(z)) halfway with even retained parity. The direct preimage
is (v, 2**(32-E)). For cell n/32 the table inverse is the integer pair
(n*2**L + 32*s*v, 32*2**L - n*s*v), L=32-E, s in {-1,+1}.
The completed reduction sums recover exactly s*z. We independently check
external representability, selected cell, both cuts and the square remainder.

This script creates a SOFTWARE-ONLY candidate pool, not an admitted/frozen
capture manifest. No hardware labels or private histories are read. The
unchanged numerical implementation remains the baseline. Ties-away is a
deliberately wrong analysis control, never a promoted alternative.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
from functools import lru_cache
import gzip
import json
from math import isqrt
from pathlib import Path
import random
import time

from compressed_guard import digest
from prepare import save
import d0031_internal_rounding_coverage as audit

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
SPEC, ROM = audit.SPEC, audit.ROM
two, exponent = audit.two, audit.exponent
Raw80 = audit.Raw80


def exact_raw(value):
    assert value > 0
    e = exponent(value)
    significand = Q(value) / two(e - 63)
    assert significand.denominator == 1
    raw = Raw80(e + 16383, int(significand))
    assert 0 < raw.se < 0x7fff and 1 << 63 <= raw.sig < 1 << 64
    assert SPEC['decode'](raw) == value
    return raw


def construct(v, e, cell=0, sign=1, multiplier=1):
    assert v & 1 and 1 << 32 < v and v * v < 1 << 65
    z = sign * v * two(e - 32)
    length = 32 - e
    if not cell:
        assert sign == 1
        a, b = v, 1 << length
    else:
        a = (cell << length) + 32 * sign * v
        b = (32 << length) - cell * sign * v
        assert a > 0 and b > 0
        c = Q(cell, 32)
        # These identities prove the inverse independently of the model.
        assert Q(a) - c * b == Q(sign * v * (1024 + cell * cell), 32)
        assert Q(b) + c * a == (1024 + cell * cell) * two(length - 5)
        assert (Q(a) - c * b) / (Q(b) + c * a) == z
    y, x = exact_raw(a * multiplier), exact_raw(b * multiplier)
    key = audit.core_key(y, x)
    state = audit.reduction(key)
    if (state['cell'] != cell or state['path'] != ('table' if cell else 'direct') or
            SPEC['decode'](y) > SPEC['decode'](x)):
        return None
    assert state['z'] == z
    if cell:
        assert audit.T(state['numerator'], 67) == state['numerator']
        assert audit.T(state['denominator'], 67) == state['denominator']
    event = audit.event(z * audit.T(z, 64), 64)
    assert event['relation'] == 'tie' and event['parity'] == 0
    assert audit.T(z, 64) == z
    return y, x, state, (a, b)


def spelling(y, x):
    return [f'{y.se:04x}', f'{y.sig:016x}', f'{x.se:04x}', f'{x.sig:016x}']


def changed_fields(fixed, other):
    differences = []
    for i, (left, right) in enumerate(zip(fixed, other, strict=True)):
        if left != right:
            differences.append(dict(restoration=audit.RESTORATIONS[i // 4],
                rc=('RN', 'RD', 'RU', 'RZ')[i % 4],
                baseline=[f'{left[0].se:04x}', f'{left[0].sig:016x}', left[1]],
                ties_away=[f'{right[0].se:04x}', f'{right[0].sig:016x}', right[1]]))
    return differences


def generate(direct_count, table_count):
    # Sampling is by an independent, explicit seed; no captured labels are
    # used to choose v. Every scanned base pair is retained in the pool.
    rng = random.Random('fpatan-d0032-exact-square-ties-20260906')
    limit = (isqrt((1 << 65) - 1) - (1 << 32)) // 2
    chosen = rng.sample(range(limit), max(direct_count, table_count))
    for number, index in enumerate(chosen):
        v = (1 << 32) + 2 * index + 1
        if number < direct_count:
            for e in (-5, -6):
                yield v, e, 0, 1
        if number < table_count:
            for e in (-7, -8):
                for cell in range(2, 33):
                    for sign in (-1, 1):
                        yield v, e, cell, sign


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--direct-count', type=int, default=65536)
    parser.add_argument('--table-count', type=int, default=128)
    args = parser.parse_args()
    assert args.direct_count > 0 and args.table_count > 0
    args.out.mkdir(exist_ok=False)
    started = time.time()
    pins = {p.name: digest(p) for p in
            (Path(__file__), HERE / 'd0031_internal_rounding_coverage.py',
             HERE / 'PSEUDOCODE.md', HERE / 'fpatan_candidate.c')}
    save(args.out / 'STARTED.json', dict(status='SOFTWARE_TIE_MINING_RUNNING',
        started_unix=started, source_sha256=pins,
        direct_v_count=args.direct_count, table_v_count=args.table_count,
        hardware_executed=False, private_history_checked=False))
    # Repeated table cells can share the same exact residual. This is only
    # a local cost optimization, not a numerical cache in the production C.
    audit.kernel = lru_cache(maxsize=4096)(audit.kernel)
    counts, cells, visible, controls = Counter(), Counter(), [], {}
    pool_path = args.out / 'candidate-pool.tsv.gz'
    with gzip.open(pool_path, 'xt', compresslevel=6) as pool:
        pool.write('id v E cell residual_sign y_se y_sig x_se x_sig endpoint_differences\n')
        for v, e, cell, sign in generate(args.direct_count, args.table_count):
            counts['attempted_base_constructions'] += 1
            made = construct(v, e, cell, sign)
            if made is None:
                counts['outside_intended_dispatch'] += 1
                continue
            y, x, state, integers = made
            baseline_values = audit.angles(state)
            alternate_values = audit.angles(state, 'ties-away')
            fixed = audit.endpoint_vector(baseline_values)
            alternate = audit.endpoint_vector(alternate_values)
            differences = changed_fields(fixed, alternate)
            ident = counts['verified_base_pairs']
            counts['verified_base_pairs'] += 1
            cells[f'cell{cell}:E{e}:sign{sign}'] += 1
            raw = spelling(y, x)
            pool.write(' '.join(map(str, (ident, v, e, cell, sign, *raw, len(differences)))) + '\n')
            record = dict(id=ident, v=v, E=e, cell=cell, residual_sign=sign,
                          raw=raw, z_wire=audit.wire(state['z']), differences=differences)
            if differences:
                visible.append(record)
                counts['endpoint_visible_base_pairs'] += 1
                counts['endpoint_visible_positive_restoration_rc_rows'] += len(differences)
            label = f'cell{cell}:E{e}:sign{sign}'
            if label not in controls:
                variants = []
                a, b = integers
                # Table integers fit within 64 bits. Populate high low-word
                # density while preserving the same exactly certified z.
                if cell:
                    largest = ((1 << 64) - 1) // max(a, b)
                    largest -= int(not (largest & 1))
                    for multiplier in sorted({1, 3, largest}):
                        my, mx, check, _ = construct(v, e, cell, sign, multiplier)
                        assert check['z'] == state['z']
                        variants.append(dict(multiplier=multiplier, raw=spelling(my, mx)))
                record['exact_same_z_variants'] = variants
                controls[label] = record
            if counts['verified_base_pairs'] % 10000 == 0:
                print('verified', counts['verified_base_pairs'], 'visible', len(visible),
                      'seconds', round(time.time() - started, 1), flush=True)
    for name, expected in pins.items():
        assert digest(HERE / name) == expected
    save(args.out / 'REPORT.json', dict(status='SOFTWARE_CERTIFIED_NOT_FRESHNESS_CLEARED',
        counts=counts, coverage=cells, endpoint_visible=visible,
        structural_controls=list(controls.values()), source_sha256=pins,
        pool_sha256=digest(pool_path), seconds=time.time() - started,
        hardware_executed=False, hardware_labels_opened=False,
        private_history_checked=False, capture_manifest_frozen=False,
        numerical_algorithm_changed=False,
        bounds='Every retained pair is exact raw80. Counts are base pairs, before sign/swap/RC/PC expansion. No hardware correctness claim.'))
    print('PASS constructive exact-tie pool:', dict(counts), 'seconds',
          round(time.time() - started, 1), flush=True)


if __name__ == '__main__':
    main()
