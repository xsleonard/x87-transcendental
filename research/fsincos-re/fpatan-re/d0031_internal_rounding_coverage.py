"""Measure selected internal rounding boundaries on the authenticated corpus.

This is a read-only, software-only coverage census, not a hardware campaign.
It covers reduction numerator/denominator cuts, the asymmetric square, and
the four restored architectural rounders. It does not pretend to cover every
polynomial node or to establish universal hardware agreement. Common exact
powers-of-two transports share a core key; observation counts stay separate.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import gzip
import json
from pathlib import Path
import sys
import time

from compressed_guard import digest
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
sys.path.insert(0, str(HERE / 'paper'))
from verify_pseudocode import load_pseudocode

SPEC = load_pseudocode()
ROM = SPEC['ROM']
two = SPEC['pow2']
exponent = SPEC['floor_log2']
T = SPEC['T']
N64 = SPEC['N64']
Raw80 = SPEC['Raw80']
classify = SPEC['classify']
RESTORATIONS = ('t', 'pi-t', 'pi/2-t', 'pi/2+t')


def normalized(raw):
    """Exact normalized finite magnitude, including exponent-zero inputs."""
    assert classify(raw) in ('normal', 'denormal', 'pseudo')
    shift = 64 - raw.sig.bit_length()
    return max(raw.se & 0x7fff, 1) - shift, raw.sig << shift


def core_key(y, x):
    a, b = sorted((normalized(y), normalized(x)))
    return a[0] - b[0], a[1], b[1]


def reduction(key):
    difference, ma, mb = key
    a, b = ma * two(difference), Q(mb)
    ratio = a / b
    if ratio < two(-40):
        return dict(path='tiny', cell=0, z=T(ratio, 67), ratio=ratio)
    if ratio <= Q(3, 64):
        return dict(path='direct', cell=0, z=T(ratio, 67), ratio=ratio)
    shifted = 32 * ratio - Q(1, 2)
    cell = -((-shifted.numerator) // shifted.denominator)
    c = Q(cell, 32)
    numerator, denominator = a - c * b, b + c * a
    z = T(T(numerator, 67) / T(denominator, 67), 67)
    return dict(path='table', cell=cell, z=z, ratio=ratio,
                numerator=numerator, denominator=denominator)


def kernel(z, table, square_policy='fixed'):
    """Explicit fixed graph with one analysis-only square substitution."""
    product = z * T(z, 64)
    if square_policy == 'symmetric':
        product = z * z
    if square_policy == 'ties-away' and product:
        unit = two(exponent(product) - 63)
        scaled = product / unit
        whole, rem = divmod(scaled.numerator, scaled.denominator)
        square = (whole + int(2 * rem >= scaled.denominator)) * unit
    else:
        square = N64(product)
    fourth = T(square * square, 67)
    if table:
        even = T(ROM[114] + T(fourth * ROM[116], 67), 67)
        odd = N64(ROM[115] + T(fourth * ROM[117], 67))
    else:
        odd = T(ROM[119] + T(fourth * N64(ROM[121] + T(fourth * ROM[123], 67)), 67), 67)
        even = T(ROM[118] + T(fourth * N64(ROM[120] + T(fourth * ROM[122], 67)), 67), 67)
    correction = N64(T(square * odd, 67) + even)
    return z + T(T(z * square, 67) * correction, 67)


def angles(state, square_policy='fixed'):
    path, z = state['path'], state['z']
    if path == 'tiny':
        angle = z
    else:
        angle = kernel(z, path == 'table', square_policy)
        if square_policy == 'fixed':
            assert angle == SPEC['kernel'](z, path == 'table')
        if path == 'table':
            angle = T(angle, 67) + ROM[124 + state['cell']]
    cut = T(angle, 67)
    return angle, ROM[19] - cut, ROM[20] - cut, ROM[20] + cut


def event(v, bits, minimum_exponent=None):
    """Exact pre-round remainder and distances, measured in local ulps."""
    if not v:
        return dict(relation='zero', parity=0, numerator=0, denominator=1,
                    distance_half=Q(1, 2), distance_integer=Q(0))
    e = exponent(abs(v))
    if minimum_exponent is not None:
        e = max(e, minimum_exponent)
    scaled = abs(v) / two(e - bits + 1)
    whole, rem = divmod(scaled.numerator, scaled.denominator)
    den = scaled.denominator
    relation = ('exact' if not rem else 'below' if 2 * rem < den else
                'tie' if 2 * rem == den else 'above')
    return dict(relation=relation, parity=whole & 1, numerator=rem, denominator=den,
                distance_half=Q(abs(2 * rem - den), 2 * den),
                distance_integer=Q(min(rem, den - rem), den))


def wire(v):
    """Compact exact dyadic state key, without arbitrary binade expansion."""
    if not v:
        return (0, 0)
    e = exponent(abs(v)) - 66
    m = v / two(e)
    assert m.denominator == 1
    return int(m), e


def endpoint_vector(values):
    return tuple(SPEC['pack_angle'](angle, mode)
                 for angle in values for mode in ('RN', 'RD', 'RU', 'RZ'))


def census_inputs():
    """Authenticate saved sources without opening hardware output labels."""
    reference = BASE / 'd0030-pseudocode-replay-v2.json'
    prior = json.loads(reference.read_text())
    assert prior['status'] == 'PASS'
    cores, totals, jobs = {}, Counter(), {}
    for name in sorted(prior['jobs']):
        job = BASE / name
        manifest = json.loads((job / 'MANIFEST.json').read_text())
        complete = json.loads((job / 'COMPLETE.json').read_text())
        assert complete['state'] == 'OBSERVED'
        assert digest(job / 'MANIFEST.json') == complete['manifest_sha256']
        zipped = (job / 'inputs.txt.gz').exists()
        inputs = job / ('inputs.txt.gz' if zipped else 'inputs.txt')
        hardware = job / ('hardware.txt.gz' if zipped else 'hardware.txt')
        assert digest(inputs) == manifest['files'][inputs.name]
        assert digest(hardware) == complete['hardware_gzip_sha256' if zipped else 'hardware_sha256']
        counts = Counter()
        with (gzip.open if zipped else open)(inputs, 'rt') as stream:
            for line in stream:
                _, rc, pc, ys, ym, xs, xm = line.split()
                y, x = Raw80(int(ys, 16), int(ym, 16)), Raw80(int(xs, 16), int(xm, 16))
                ky, kx = classify(y), classify(x)
                counts['rows'] += 1
                totals['rc:' + rc] += 1
                totals['pc:' + pc] += 1
                totals['classes:' + ky + '/' + kx] += 1
                if ky not in ('normal', 'denormal', 'pseudo') or kx not in ('normal', 'denormal', 'pseudo'):
                    counts['non_finite_or_zero_rows'] += 1
                    continue
                counts['finite_nonzero_rows'] += 1
                key = core_key(y, x)
                restore = 2 * int(normalized(y) > normalized(x)) + int(bool(x.se & 0x8000))
                if key not in cores:
                    cores[key] = dict(restorations=[0] * 4,
                                      example=[f'{y.se:04x}', f'{y.sig:016x}', f'{x.se:04x}', f'{x.sig:016x}'])
                cores[key]['restorations'][restore] += 1
        assert counts['rows'] == manifest['rows'] == complete['rows'] == prior['jobs'][name]['counts']['rows']
        jobs[name] = dict(counts=counts, inputs_sha256=digest(inputs), hardware_file_sha256=digest(hardware))
        totals.update(counts)
        print(name, 'rows', counts['rows'], 'distinct normalized cores', len(cores), flush=True)
    assert totals['rows'] == 2783208
    return cores, totals, jobs, digest(reference)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    assert not args.out.exists()
    started = time.time()
    pins = {str(p.relative_to(HERE.parent.parent)): digest(p) for p in
            (Path(__file__), HERE / 'PSEUDOCODE.md', HERE / 'fpatan_candidate.c',
             HERE / 'paper/verify_pseudocode.py')}
    save(args.out.with_suffix('.started.json'), dict(status='COVERAGE_RUNNING',
        started_unix=started, source_sha256=pins, hardware_executed=False))
    cores, totals, jobs, replay_sha = census_inputs()
    buckets, weighted, square_shapes, intersections = Counter(), Counter(), Counter(), Counter()
    ties, examples, shared = [], {}, {}
    shared_counts = Counter()
    near_threshold = Q(1, 4096)
    for number, (key, record) in enumerate(cores.items(), 1):
        state = reduction(key)
        path, cell, z = state['path'], state['cell'], state['z']
        count = sum(record['restorations'])
        buckets['path:' + path] += 1
        weighted['path:' + path] += count
        if path == 'table':
            for node in ('numerator', 'denominator'):
                measure = event(state[node], 67)
                label = f'{node}:{measure["relation"]}:parity{measure["parity"]}'
                buckets[label] += 1
                weighted[label] += count
        if path == 'tiny':
            square = None
        else:
            square = event(z * T(z, 64), 64)
            mantissa, _ = wire(z)
            label = f'{path}:square:{square["relation"]}:parity{square["parity"]}'
            buckets[label] += 1
            weighted[label] += count
            square_shapes[f'{path}:cell{cell}:low3={abs(mantissa) % 8}:{square["relation"]}:parity{square["parity"]}'] += 1
            if square['relation'] == 'tie':
                assert square['parity'] == 0, 'Contradicts the square tie restriction'
        values = angles(state)
        for restoration, value in enumerate(values):
            observations = record['restorations'][restoration]
            if not observations:
                continue
            final = event(value, 64, -16382)
            label = f'{path}:final:{RESTORATIONS[restoration]}:{final["relation"]}:parity{final["parity"]}'
            buckets[label] += 1
            weighted[label] += observations
            if square is not None:
                sn = square['distance_half'] <= near_threshold
                for boundary in ('half', 'integer'):
                    fn = final['distance_' + boundary] <= near_threshold
                    label = f'{path}:{RESTORATIONS[restoration]}:square_half_near{int(sn)}:final_{boundary}_near{int(fn)}'
                    intersections[label] += 1
                    if sn and fn and label not in examples:
                        examples[label] = dict(raw=record['example'], core=key,
                            square_distance=str(square['distance_half']),
                            final_distance=str(final['distance_' + boundary]))
        # Ignore trivial common scaling: distinct normalized operand cores
        # must collide here, and the numerator/denominator history must differ.
        retained = (path, cell, wire(z))
        history = None
        if path == 'table':
            history = tuple((event(state[node], 67)['numerator'],
                             event(state[node], 67)['denominator'])
                            for node in ('numerator', 'denominator'))
        if retained in shared:
            first_key, first_history = shared[retained]
            shared_counts['additional_cores_same_retained_state'] += 1
            if history != first_history:
                shared_counts['additional_cores_different_cut_remainders'] += 1
                if 'same-retained-different-history' not in examples:
                    examples['same-retained-different-history'] = dict(first_core=first_key,
                        second_core=key, retained=[path, cell, wire(z)],
                        first_history=first_history, second_history=history)
        else:
            shared[retained] = (key, history)
        if square is not None and square['relation'] == 'tie':
            baseline = endpoint_vector(values)
            away = endpoint_vector(angles(state, 'ties-away'))
            symmetric = endpoint_vector(angles(state, 'symmetric'))
            # Only quadrants actually represented in the saved corpus count
            # as observed separators. Hypothetical transports stay separate.
            changed = lambda other: [RESTORATIONS[i] for i in range(4)
                                     if baseline[4*i:4*i+4] != other[4*i:4*i+4]]
            ties.append(dict(core=key, raw=record['example'], path=path, cell=cell,
                z_wire=wire(z), observations_by_restoration=record['restorations'],
                ties_away_changed=changed(away), symmetric_changed=changed(symmetric)))
        if number % 10000 == 0:
            print('classified', number, '/', len(cores), 'seconds', round(time.time() - started, 1), flush=True)
    for name, expected in pins.items():
        assert digest(HERE.parent.parent / name) == expected
    save(args.out, dict(status='PASS_SELECTED_NODE_COVERAGE_CENSUS',
        scope='All saved inputs; selected reduction/square/final nodes only. Not a full graph coverage certificate.',
        source_sha256=pins, pseudocode_replay_sha256=replay_sha,
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False,
        counts=totals, jobs=jobs, distinct_normalized_finite_cores=len(cores),
        core_buckets=buckets, observation_weighted_buckets=weighted,
        square_shapes=square_shapes, near_distance_ulp=str(near_threshold),
        square_final_intersections=intersections, retained_state_collisions=shared_counts,
        exact_square_ties=ties, examples=examples, seconds=time.time() - started))
    print('PASS selected-node census;', len(cores), 'cores;', len(ties), 'exact square ties;',
          'seconds', round(time.time() - started, 1), flush=True)


if __name__ == '__main__':
    main()
