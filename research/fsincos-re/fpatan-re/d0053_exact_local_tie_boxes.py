"""Exhaust all exact target ties in an explicit retained-square U interval.

The algebraic inverse makes local boxes decidable by enumerating every
halfway target, without an SMT relaxation or sampling. This is an exact
finite-box result, never an all-domain exclusion or a silicon tie rule.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0045_tie_observability import target_and_correction
from d0049_algebraic_tie_preimages import (domains, invert_target, graph,
    fraction, target_event, expose, ROM, COEFFICIENTS)
from prepare import save


def local_domains(node, exponent, low, high):
    result = []
    for original in domains(node, exponent):
        d = dict(original)
        d['u_low'], d['u_high'] = max(low, d['u_low']), min(high, d['u_high'])
        if d['u_low'] > d['u_high']:
            continue
        d['v_low'] = max(d['v_low'], d['u_low'] ** 2 >> d['drop'])
        d['v_high'] = min(d['v_high'], d['u_high'] ** 2 >> d['drop'])
        if d['v_low'] > d['v_high']:
            continue
        alignment = d['unit'] - d['v_step'] - d['coefficient_step']
        first = d['v_low'] * d['coefficient'] >> alignment
        last = (d['v_high'] * d['coefficient'] >> alignment) + 1
        first += (d['first'] - first) % d['modulus']
        d['first'], d['count'] = first, (last - first) // d['modulus'] + 1
        # The constant and maximum possible product stay in one RN binade.
        # Consequently the halfway congruence used above is constant here.
        base = abs(fraction(ROM[COEFFICIENTS[node][0]]))
        product_bound = d['v_high'] * d['coefficient'] * audit.two(
            d['v_step'] + d['coefficient_step'])
        assert audit.exponent(base) == audit.exponent(base + product_bound)
        if d['count'] > 0:
            result.append(d)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', type=int, choices=(0, 1, 2), required=True)
    parser.add_argument('--center', type=lambda x: int(x, 16), required=True)
    parser.add_argument('--radius-bits', type=int, required=True)
    parser.add_argument('--exponent', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert 0 <= args.radius_bits <= 45
    radius = (1 << args.radius_bits) - 1
    low = max(1 << 63, args.center - radius)
    high = min(9 << 60 if args.exponent == -9 else (1 << 64) - 1, args.center + radius)
    assert low <= high
    args.out.mkdir(exist_ok=False)
    source = Path(__file__).resolve()
    pins = {name: digest(source.with_name(name)) for name in
        ('d0053_exact_local_tie_boxes.py', 'd0049_algebraic_tie_preimages.py',
         'd0045_tie_observability.py', 'PSEUDOCODE.md', 'fpatan_candidate.c')}
    choices = local_domains(args.node, args.exponent, low, high)
    save(args.out / 'STARTED.json', dict(status='EXACT_LOCAL_BOX_RUNNING',
        node=args.node, exponent=args.exponent, low=f'{low:016x}', high=f'{high:016x}',
        domains=choices, source_sha256=pins, hardware_executed=False))
    counts, seen, witnesses = Counter(), set(), []
    rng, started = random.Random('d0053-exact-local-lifts'), time.monotonic()
    with (args.out / 'targets.tsv').open('x') as stream:
        for d in choices:
            for j in range(d['count']):
                counts['target_searches'] += 1
                term = d['first'] + j * d['modulus']
                for um in invert_target(d, term):
                    if um in seen:
                        counts['duplicate_U'] += 1
                        continue
                    seen.add(um)
                    target, h, outer = graph(args.node, (um, args.exponent - 63))
                    other_target, other, other_outer = graph(args.node, (um, args.exponent - 63), True)
                    assert target == other_target
                    parity = target_event(target)
                    counts['ties'] += 1
                    counts[f'parity{parity}'] += 1
                    counts['H_changed'] += h != other
                    counts['first_outer_changed'] += outer != other_outer
                    stream.write(f'T {args.node} {counts["target_searches"]} {args.exponent} {um:016x} '
                                 f'{parity} {int(h != other)} {int(outer != other_outer)}\n')
                    if outer != other_outer or counts['ties'] % 4096 == 1:
                        t, fh = target_and_correction(args.node, um * audit.two(args.exponent - 63))
                        _, fo = target_and_correction(args.node, um * audit.two(args.exponent - 63), True)
                        assert (fraction(target), fraction(h), fraction(other)) == (t, fh, fo)
                        counts['fraction_checks'] += 1
                    if h != other:
                        expose(args.node, args.exponent, um, counts['target_searches'],
                               parity, stream, counts, witnesses, rng)
    assert counts['target_searches'] == sum(d['count'] for d in choices)
    assert all(digest(source.with_name(name)) == sha for name, sha in pins.items())
    report = dict(status='EXHAUSTIVE_LOCAL_TIE_BOX', node=args.node,
        square_exponent=args.exponent, low=f'{low:016x}', high=f'{high:016x}',
        domains=choices, counts=counts, witnesses=witnesses,
        elapsed_seconds=time.monotonic() - started, source_sha256=pins,
        target_sha256=digest(args.out / 'targets.tsv'), hardware_executed=False,
        numerical_model_changed=False, goal_complete=False,
        limits='All halfway-target lattice points and all their integer U preimages in the stated box were enumerated. The box is not the full polynomial domain. External lifting remains bounded and is not an unreachability proof.')
    save(args.out / 'REPORT.json', report)
    print(json.dumps(dict(node=args.node, low=report['low'], high=report['high'],
                         counts=counts, witnesses=witnesses)), flush=True)


if __name__ == '__main__':
    main()
