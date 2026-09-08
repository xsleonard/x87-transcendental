"""Census every explicit kernel rounder on the current authenticated corpus.

The exact-rational trace is analysis-only and is checked against the published
program at every distinct normalized finite core. No hardware labels are
opened and no main-program behavior changes. Missing event buckets are
measured gaps, not proofs of unreachability.
"""
from collections import Counter
from fractions import Fraction as Q
import gzip
import json
from pathlib import Path
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
ROM = audit.ROM


def traced_kernel(z, table, substitution=None):
    """Every named cut is explicit; substitutions are local test controls."""
    records = []

    def op(name, value, bits=67, mode='RZ'):
        if not value:
            records.append((name, bits, mode, 'zero', 0, 0, 1, Q(0), Q(0)))
            return Q(0)
        scale = audit.exponent(abs(value)) - bits + 1
        n, d = abs(value.numerator), value.denominator
        if scale < 0:
            n <<= -scale
        else:
            d <<= scale
        whole, rem = divmod(n, d)
        relation = 'exact' if not rem else 'below' if 2 * rem < d else 'tie' if 2 * rem == d else 'above'
        inc = mode == 'RN' and (2 * rem > d or (2 * rem == d and whole & 1))
        if substitution is not None and substitution[0] == name and relation == 'tie':
            assert mode == 'RN'
            assert substitution[1] in ('ties-away', 'ties-zero')
            inc = substitution[1] == 'ties-away'
        result = (-1 if value < 0 else 1) * (whole + int(inc)) * audit.two(scale)
        records.append((name, bits, mode, relation, whole & 1, rem, d, value, result))
        return result

    narrow_z = op('square_operand', z, 64)
    square = op('square', z * narrow_z, 64, 'RN')
    fourth = op('fourth', square * square)
    if table:
        even_product = op('even_product', fourth * ROM[116])
        even = op('even_sum', ROM[114] + even_product)
        odd_product = op('odd_product', fourth * ROM[117])
        odd = op('odd_sum', ROM[115] + odd_product, 64, 'RN')
    else:
        odd_inner_product = op('odd_inner_product', fourth * ROM[123])
        odd_inner = op('odd_inner_sum', ROM[121] + odd_inner_product, 64, 'RN')
        even_inner_product = op('even_inner_product', fourth * ROM[122])
        even_inner = op('even_inner_sum', ROM[120] + even_inner_product, 64, 'RN')
        odd_product = op('odd_product', fourth * odd_inner)
        odd = op('odd_sum', ROM[119] + odd_product)
        even_product = op('even_product', fourth * even_inner)
        even = op('even_sum', ROM[118] + even_product)
    weighted_odd = op('weighted_odd', square * odd)
    correction = op('correction_sum', weighted_odd + even, 64, 'RN')
    cubic = op('cubic', z * square)
    tail = op('tail', cubic * correction)
    value = z + tail
    if substitution is None:
        assert value == audit.SPEC['kernel'](z, table)
    return value, records


def restored(state, kernel_value):
    angle = kernel_value
    if state['path'] == 'table':
        angle = audit.T(angle, 67) + ROM[124 + state['cell']]
    cut = audit.T(angle, 67)
    return angle, ROM[19] - cut, ROM[20] - cut, ROM[20] + cut


def read_cores(catalog_path):
    catalog = json.loads(catalog_path.read_text())
    corpus = catalog_path.parent
    cores, counts = {}, Counter()
    for name, pack in catalog['packs'].items():
        path = corpus / pack['path']
        assert digest(path) == pack['sha256']
        rows = 0
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                _, rc, pc, ys, ym, xs, xm = line.split()
                y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
                rows += 1
                classes = (audit.classify(y), audit.classify(x))
                if not all(c in ('normal', 'denormal', 'pseudo') for c in classes):
                    counts['non_finite_or_zero_rows'] += 1
                    continue
                counts['finite_nonzero_rows'] += 1
                key = audit.core_key(y, x)
                quadrant = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
                if key not in cores:
                    cores[key] = dict(quadrants=[0] * 4, example=[ys, ym, xs, xm])
                cores[key]['quadrants'][quadrant] += 1
        assert rows == pack['counts']['rows']
        counts['rows'] += rows
        print('Input pack', name, rows, 'normalized cores', len(cores), flush=True)
    assert counts['rows'] == catalog['counts']['rows'] == 3655928
    return cores, counts


def main():
    output = BASE / 'd0037-polynomial-node-census'
    output.mkdir(exist_ok=False)
    catalog = HERE / 'corpus-v1/CATALOG-D0036.json'
    pins = {name: digest(HERE / name) for name in
            ('d0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
             'PSEUDOCODE.md', 'fpatan_candidate.c')}
    started = time.time()
    save(output / 'STARTED.json', dict(status='POLYNOMIAL_CENSUS_RUNNING',
        source_sha256=pins, catalog_sha256=digest(catalog), hardware_executed=False))
    cores, counts = read_cores(catalog)
    histograms, weighted, thresholds = Counter(), Counter(), Counter()
    closest, exact_examples, ties = {}, {}, []
    for number, (key, metadata) in enumerate(cores.items(), 1):
        state = audit.reduction(key)
        if state['path'] == 'tiny':
            counts['tiny_cores_no_polynomial'] += 1
            continue
        counts['polynomial_cores'] += 1
        path = state['path']
        kernel, records = traced_kernel(state['z'], path == 'table')
        total = sum(metadata['quadrants'])
        for node, bits, mode, relation, parity, rem, den, before, after in records:
            stage = path + ':' + node
            label = f'{stage}:{relation}:parity{parity}'
            histograms[label] += 1
            weighted[label] += total
            if relation in ('tie', 'exact') and label not in exact_examples:
                exact_examples[label] = dict(core=key, raw=metadata['example'], cell=state['cell'])
            if rem and relation != 'tie':
                if mode == 'RN':
                    distance_n, distance_d = abs(2 * rem - den), 2 * den
                else:
                    distance_n, distance_d = min(rem, den - rem), den
                for threshold in (12, 20, 32):
                    if (distance_n << threshold) <= distance_d:
                        thresholds[f'{stage}:within_2^-{threshold}_ulp'] += 1
                current = closest.get(stage)
                if current is None or distance_n * current[1] < current[0] * distance_d:
                    closest[stage] = (distance_n, distance_d, key, metadata['example'], state['cell'])
            if mode == 'RN' and relation == 'tie':
                rule = 'ties-away' if parity == 0 else 'ties-zero'
                mutated, _ = traced_kernel(state['z'], path == 'table', (node, rule))
                fixed = audit.endpoint_vector(restored(state, kernel))
                other = audit.endpoint_vector(restored(state, mutated))
                changed = [audit.RESTORATIONS[q] for q in range(4)
                           if fixed[4*q:4*q+4] != other[4*q:4*q+4]]
                observed_changed = [audit.RESTORATIONS[q] for q in range(4)
                    if metadata['quadrants'][q] and fixed[4*q:4*q+4] != other[4*q:4*q+4]]
                ties.append(dict(node=stage, core=key, raw=metadata['example'],
                    cell=state['cell'], z_wire=audit.wire(state['z']), parity=parity,
                    opposite_tie_rule=rule, changed_quadrants=changed,
                    observed_changed_quadrants=observed_changed,
                    observation_counts=metadata['quadrants']))
        if number % 10000 == 0:
            print('Traced', number, '/', len(cores), 'tie events', len(ties),
                  'seconds', round(time.time() - started, 1), flush=True)
    for name, expected in pins.items():
        assert digest(HERE / name) == expected
    save(output / 'REPORT.json', dict(status='PASS_ALL_EXPLICIT_POLYNOMIAL_NODE_CENSUS',
        counts=counts, normalized_finite_cores=len(cores), core_histograms=histograms,
        observation_weighted_histograms=weighted, near_boundary_counts=thresholds,
        closest_nonboundary={stage: dict(distance=str(Q(n, d)), core=key, raw=raw, cell=cell)
                             for stage, (n, d, key, raw, cell) in closest.items()},
        exact_event_examples=exact_examples, rn_halfway_events=ties,
        source_sha256=pins, catalog_sha256=digest(catalog), seconds=time.time() - started,
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False,
        limits='Coverage of the saved input corpus, not reachability proof. Positive/negative RC endpoint equivalence uses all four modes; only observed quadrants count as existing discrimination.'))
    print('PASS polynomial census:', json.dumps(counts), '; exact RN ties', len(ties), flush=True)


if __name__ == '__main__':
    main()
