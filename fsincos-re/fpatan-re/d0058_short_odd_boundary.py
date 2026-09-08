"""Exact necessary-boundary filter for the unresolved short odd RN64 tie.

Both choices at the odd addition must straddle a downstream H boundary to
change H. The even addend is a multiple of g=2^-68, and every H halfway is
also a multiple of g. Therefore the untruncated weighted-odd products must
straddle a multiple of g. This filter encloses those products as a function
of the exact-halfway target index. It changes no emulator or tie policy.

The smooth center is sqrt(T/C)*(B+T). A rational square-root bracket and a
bounded concave Taylor remainder enclose it on each index block. Exact
floor sums enumerate only possible boundary crossings. All retained ties,
including the ones subsequently masked, receive independent Fraction replay.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import json
from math import isqrt
from pathlib import Path
import random
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0045_tie_observability import target_and_correction
from d0049_algebraic_tie_preimages import (
    domains, invert_target, graph, fraction, target_event, expose,
)
from d0056_outer_boundary_lattice import candidate_offsets
from prepare import save

HERE = Path(__file__).resolve().parent
FIXED_BITS = 64
ROOT_BITS = 128


def ceil_fraction(value):
    return -((-value.numerator) // value.denominator)


def sqrt_bracket(value):
    """An integer-square-root certificate, never a floating approximation."""
    assert value > 0
    scale = 1 << ROOT_BITS
    root = isqrt((value.numerator << (2 * ROOT_BITS)) // value.denominator)
    low, high = Q(root, scale), Q(root + 1, scale)
    assert low * low <= value < high * high
    return low, high


def parameters(domain, exponent):
    assert exponent <= -13
    d = domain
    base, coefficient = audit.ROM[115], audit.ROM[117]
    first = d['first'] * audit.two(d['unit'])
    delta = d['modulus'] * audit.two(d['unit'])
    last = first + (d['count'] - 1) * delta
    u_max = d['u_high'] * audit.two(exponent - 63)
    v_max = d['v_high'] * audit.two(d['v_step'])
    target_ulp = audit.two(audit.exponent(v_max * coefficient) - 66)
    square_ulp = audit.two(d['v_step'])
    # The domain includes bounding targets. Their relaxed roots can lie
    # slightly outside the physical U domain, so bound them separately.
    u_min, _ = sqrt_bracket(first / coefficient)
    _, center_u_max = sqrt_bracket(last / coefficient)
    half_inner = audit.two(audit.exponent(base) - 64)
    grid = audit.two(-68)
    assert audit.exponent(base) == audit.exponent(base + last)
    assert 3 * last < base

    # E=T67(A+T67(v*K)) is negative throughout and has binade -2.
    # H's input E+T67(u*odd) also stays negative in binade -2. Consequently
    # E lies on grid, H halfways lie on 4*grid, and weighted-odd T67 has a
    # finer dyadic grid. A changed H therefore requires a raw product
    # crossing of some multiple of grid; its T67 cut cannot invent one.
    even_min = abs(audit.ROM[114])
    even_max = even_min + v_max * abs(audit.ROM[116])
    weighted_max = u_max * (base + last + half_inner)
    assert audit.exponent(even_min) == audit.exponent(even_max) == -2
    assert audit.exponent(even_min - weighted_max) == -2
    assert audit.exponent(weighted_max) - 66 < -68

    # T <= v*C < T+target_ulp and v <= u^2 < v+square_ulp.
    # Thus 0 <= u-sqrt(T/C) <= (target_ulp/C+square_ulp)/(2*u_min).
    # Either inner choice is B+T +/- half_inner. These errors bound the
    # raw products, so a product truncation error need not be added.
    root_error = (target_ulp / coefficient + square_ulp) / (2 * u_min)
    error_low = max(u_max, center_u_max) * half_inner / grid
    error_high = (u_max * half_inner + root_error * (base + last)) / grid
    return dict(base=base, coefficient=coefficient, first=first, delta=delta,
                grid=grid, error_low=error_low, error_high=error_high,
                target_ulp=target_ulp, square_ulp=square_ulp)


def block_enclosure(params, start, length):
    """Return a fixed-point line and certified asymmetric error margins."""
    assert start >= 0 and length > 0
    p = params
    target = p['first'] + start * p['delta']
    low_root, high_root = sqrt_bracket(target / p['coefficient'])
    base, grid, delta = p['base'], p['grid'], p['delta']
    intercept_low = low_root * (base + target) / grid
    intercept_high = high_root * (base + target) / grid
    slope_low = low_root * (base + 3 * target) * delta / (2 * target * grid)
    slope_high = high_root * (base + 3 * target) * delta / (2 * target * grid)
    # f''(j)=sqrt(T/C)*(3*T-B)*delta^2/(4*T^2*grid) < 0.
    # sqrt(T/C)/T^2 decreases with T. Dropping -3*T only increases the
    # absolute bound. The Taylor remainder is in [-curvature, 0].
    extent = length - 1
    curvature = high_root * base * delta * delta * extent * extent / (8 * target * target * grid)
    lower = p['error_low'] + curvature
    upper = (p['error_high'] + intercept_high - intercept_low
             + (slope_high - slope_low) * extent)
    modulus = 1 << FIXED_BITS
    intercept = int(intercept_low * modulus)
    slope = int(slope_low * modulus)
    # Flooring both fixed-point coefficients lowers the line by less than
    # (1+s)/modulus. Put that entire error on the upper side.
    return dict(modulus=modulus, slope=slope, intercept=intercept,
                lower=ceil_fraction(lower * modulus),
                upper=ceil_fraction(upper * modulus) + length)


def filtered_indices(params, start, length):
    p = block_enclosure(params, start, length)
    for offset in candidate_offsets(length, p['modulus'], p['slope'], p['intercept'],
                                    p['lower'], p['upper']):
        yield start + offset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exponent', type=int, default=-13)
    parser.add_argument('--blocks', type=int, required=True)
    parser.add_argument('--block-bits', type=int, default=10)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.exponent <= -13 and args.blocks > 0 and 0 <= args.block_bits <= 24
    args.out.mkdir(exist_ok=False)
    choices = domains(2, args.exponent)
    bounds = [parameters(d, args.exponent) for d in choices]
    names = ('d0058_short_odd_boundary.py', 'd0056_outer_boundary_lattice.py',
             'd0049_algebraic_tie_preimages.py', 'd0045_tie_observability.py',
             'd0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
             'fpatan_candidate.c', 'PSEUDOCODE.md')
    pins = {name: digest(HERE / name) for name in names}
    save(args.out / 'STARTED.json', dict(status='SHORT_ODD_HALF_AND_H_GRID_SEARCH',
        node=2, exponent=args.exponent, blocks=args.blocks, block_bits=args.block_bits,
        domains=choices, boundary_parameters=[{k: str(v) for k, v in p.items()} for p in bounds],
        source_sha256=pins, hardware_executed=False))
    rng = random.Random(f'd0058:2:{args.exponent}:{args.blocks}:{args.block_bits}')
    lift_rng = random.Random('d0058-external-lifts')
    counts, propagation = Counter(), Counter()
    seen, witnesses = set(), []
    width, started = 1 << args.block_bits, time.monotonic()
    with (args.out / 'blocks.tsv').open('x') as blocks, (args.out / 'targets.tsv').open('x') as stream:
        for block in range(args.blocks):
            domain_index = block % len(choices)
            d, p = choices[domain_index], bounds[domain_index]
            start = rng.randrange((d['count'] + width - 1) // width) * width
            length = min(width, d['count'] - start)
            candidates = list(filtered_indices(p, start, length))
            blocks.write(f'{domain_index} {start} {length} {len(candidates)}\n')
            counts['sampled_blocks'] += 1
            counts['target_index_occurrences_in_blocks'] += length
            counts['boundary_candidate_indices'] += len(candidates)
            for j in candidates:
                term = d['first'] + j * d['modulus']
                for um in invert_target(d, term):
                    if um in seen:
                        counts['duplicate_U'] += 1
                        continue
                    seen.add(um)
                    target, h, _ = graph(2, (um, args.exponent - 63))
                    same_target, other, _ = graph(2, (um, args.exponent - 63), True)
                    assert target == same_target
                    parity = target_event(target)
                    counts['ties'] += 1
                    counts[f'parity{parity}'] += 1
                    counts['H_changed'] += h != other
                    stream.write(f'T 2 {block} {args.exponent} {um:016x} {parity} {int(h != other)} 1\n')
                    ft, fh = target_and_correction(2, um * audit.two(args.exponent - 63))
                    _, fo = target_and_correction(2, um * audit.two(args.exponent - 63), True)
                    assert (fraction(target), fraction(h), fraction(other)) == (ft, fh, fo)
                    counts['all_retained_ties_fraction_replayed'] += 1
                    if h != other:
                        expose(2, args.exponent, um, block, parity, stream, propagation, witnesses, lift_rng)
            if block % 4096 == 0:
                stream.flush()
                blocks.flush()
                print('PROGRESS', block, dict(counts), 'seconds', round(time.monotonic() - started, 2), flush=True)
    assert all(digest(HERE / name) == sha for name, sha in pins.items())
    report = dict(status='VERIFIED_SHORT_ODD_BOUNDARY_FILTERED_SEARCH', node=2,
        square_exponent=args.exponent, counts=counts, propagation=propagation,
        witnesses=witnesses, elapsed_seconds=time.monotonic() - started, source_sha256=pins,
        blocks_sha256=digest(args.out / 'blocks.tsv'), target_sha256=digest(args.out / 'targets.tsv'),
        hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='Sampled index blocks, possibly overlapping; target-index counts are occurrences, not unique external inputs. Every retained tie is independently Fraction-replayed. Excluded indices have a necessary H-grid-boundary exclusion in the fixed graph, not a hardware label or global all-input proof.')
    save(args.out / 'REPORT.json', report)
    print('PASS', json.dumps(dict(counts=counts, propagation=propagation, witnesses=witnesses)), flush=True)


if __name__ == '__main__':
    main()
