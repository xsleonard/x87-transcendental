"""Construct joint inner-halfway/outer-carry candidates by exact floor sums.

The halfway target index gives a quadratic real outer expression. On each
index block, a linear enclosure with rigorously bounded curvature and cut
errors excludes indices that cannot cross an outer rounding boundary.
Only the remaining indices need square preimage inversion. This is a
necessary-condition filter, not an empirical selector or a hardware rule.
"""
import argparse
from collections import Counter
import json
from math import lcm
from pathlib import Path
import random
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0045_tie_observability import target_and_correction
from d0049_algebraic_tie_preimages import (domains, invert_target, graph, fraction,
    target_event, expose, COEFFICIENTS, ROM)
from prepare import save

HERE = Path(__file__).resolve().parent


def floor_sum(n, modulus, slope, intercept):
    """Sum floor((slope*i + intercept)/modulus), 0 <= i < n, exactly."""
    assert n >= 0 and modulus > 0 and slope >= 0 and intercept >= 0
    total = 0
    while True:
        if slope >= modulus:
            total += (n - 1) * n * (slope // modulus) // 2
            slope %= modulus
        if intercept >= modulus:
            total += n * (intercept // modulus)
            intercept %= modulus
        maximum = slope * n + intercept
        if maximum < modulus:
            return total
        n, intercept = divmod(maximum, modulus)
        modulus, slope = slope, modulus


def below_count(n, modulus, slope, intercept, width):
    if width <= 0:
        return 0
    if width >= modulus:
        return n
    return n - (floor_sum(n, modulus, slope, intercept + modulus - width)
                - floor_sum(n, modulus, slope, intercept))


def candidate_offsets(n, modulus, slope, intercept, lower_margin, upper_margin):
    """Find residues <= lower_margin or >= modulus-upper_margin, inclusively."""
    slope, intercept = slope % modulus, intercept % modulus
    assert lower_margin >= 0 and upper_margin >= 0
    if lower_margin + upper_margin + 1 >= modulus:
        yield from range(n)
        return

    def count(start, length):
        b = (intercept + slope * start) % modulus
        low = below_count(length, modulus, slope, b, lower_margin + 1)
        high = length - below_count(length, modulus, slope, b, modulus - upper_margin)
        return low + high

    stack = [(0, n)]
    while stack:
        start, length = stack.pop()
        if not length or not count(start, length):
            continue
        if length <= 32:
            for i in range(start, start + length):
                r = (intercept + slope * i) % modulus
                if r <= lower_margin or r >= modulus - upper_margin:
                    yield i
        else:
            left = length // 2
            stack.append((start + left, length - left))
            stack.append((start, left))


def parameters(node, domain):
    assert node in (0, 1)
    d = domain
    base = abs(fraction(ROM[COEFFICIENTS[node][0]]))
    coefficient = abs(fraction(ROM[COEFFICIENTS[node][1]]))
    anchor = abs(fraction(ROM[119 if node == 0 else 118]))
    vmax = d['v_high'] * audit.two(d['v_step'])
    tmax = vmax * coefficient
    inner_half = audit.two(audit.exponent(base) - 64)
    outer_unit = audit.two(audit.exponent(anchor) - 66)
    assert audit.exponent(base) == audit.exponent(base + tmax)
    assert audit.exponent(anchor) == audit.exponent(anchor + vmax * (base + tmax + inner_half))
    target_product_ulp = audit.two(audit.exponent(tmax) - 66)
    outer_product_ulp = audit.two(audit.exponent(vmax * (base + tmax + inner_half)) - 66)

    # For exact target T, actual v is in [T/C, (T+ulp_target)/C).
    # Either inner decision is B+T +/- half_inner. The outer product's
    # truncation can only reduce its magnitude by less than ulp_outer.
    # Thus S(T)=A+(T/C)*(B+T) encloses both pre-cut magnitudes with these
    # conservative, block-independent errors. Signed node 1 uses magnitudes.
    error_low = (vmax * inner_half + outer_product_ulp) / outer_unit
    error_high = (vmax * inner_half + target_product_ulp / coefficient
                  * (base + tmax + inner_half)) / outer_unit
    first = d['first'] * audit.two(d['unit'])
    delta = d['modulus'] * audit.two(d['unit'])
    alpha = delta * delta / coefficient / outer_unit
    beta = delta * (base + 2 * first) / coefficient / outer_unit
    gamma = (anchor + first * (base + first) / coefficient) / outer_unit
    values = alpha, beta, gamma, error_low, error_high
    denominator = lcm(*(v.denominator for v in values))
    integers = [int(v * denominator) for v in values]
    assert all(audit.Q(n, denominator) == v for n, v in zip(integers, values))
    return dict(modulus=denominator, alpha=integers[0], beta=integers[1], gamma=integers[2],
                error_low=integers[3], error_high=integers[4],
                proof_errors=dict(lower=str(error_low), upper=str(error_high),
                                  outer_unit=str(outer_unit), target_product_ulp=str(target_product_ulp),
                                  outer_product_ulp=str(outer_product_ulp)))


def filtered_indices(params, start, length):
    p = params
    slope = 2 * p['alpha'] * start + p['beta']
    intercept = p['alpha'] * start * start + p['beta'] * start + p['gamma']
    # Positive curvature is in [0, alpha*(length-1)^2] on this block.
    upper = p['error_high'] + p['alpha'] * (length - 1) ** 2
    for offset in candidate_offsets(length, p['modulus'], slope, intercept,
                                    p['error_low'], upper):
        yield start + offset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', type=int, choices=(0, 1), required=True)
    parser.add_argument('--exponent', type=int, default=-9)
    parser.add_argument('--blocks', type=int, required=True)
    parser.add_argument('--block-bits', type=int, default=20)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.exponent <= -9 and args.blocks > 0 and 0 <= args.block_bits <= 28
    args.out.mkdir(exist_ok=False)
    choices = domains(args.node, args.exponent)
    bounds = [parameters(args.node, d) for d in choices]
    names = ('d0056_outer_boundary_lattice.py', 'd0049_algebraic_tie_preimages.py',
             'd0045_tie_observability.py', 'fpatan_candidate.c', 'PSEUDOCODE.md')
    pins = {n: digest(HERE / n) for n in names}
    save(args.out / 'STARTED.json', dict(status='JOINT_HALF_AND_OUTER_BOUNDARY_SEARCH',
        node=args.node, exponent=args.exponent, blocks=args.blocks, block_bits=args.block_bits,
        domains=choices, boundary_parameters=bounds, source_sha256=pins, hardware_executed=False))
    rng = random.Random(f'd0056:{args.node}:{args.exponent}:{args.blocks}:{args.block_bits}')
    lift_rng = random.Random('d0056-lifts')
    counts, checks, propagation = Counter(), Counter(), Counter()
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
                    t, h, outer = graph(args.node, (um, args.exponent - 63))
                    other_t, other, alternate_outer = graph(args.node, (um, args.exponent - 63), True)
                    assert t == other_t
                    parity = target_event(t)
                    counts['ties'] += 1
                    counts[f'parity{parity}'] += 1
                    counts['first_outer_changed'] += outer != alternate_outer
                    counts['H_changed'] += h != other
                    stream.write(f'T {args.node} {block} {args.exponent} {um:016x} {parity} '
                                 f'{int(h != other)} {int(outer != alternate_outer)}\n')
                    ft, fh = target_and_correction(args.node, um * audit.two(args.exponent - 63))
                    _, fo = target_and_correction(args.node, um * audit.two(args.exponent - 63), True)
                    assert (fraction(t), fraction(h), fraction(other)) == (ft, fh, fo)
                    checks['all_retained_ties_fraction_replayed'] += 1
                    if h != other:
                        expose(args.node, args.exponent, um, block, parity, stream, propagation, witnesses, lift_rng)
            if block % 128 == 0:
                stream.flush()
                blocks.flush()
                print('PROGRESS', block, dict(counts), 'seconds', round(time.monotonic() - started, 2), flush=True)
    assert all(digest(HERE / name) == sha for name, sha in pins.items())
    report = dict(status='VERIFIED_BOUNDARY_FILTERED_TIE_SEARCH', node=args.node,
        square_exponent=args.exponent, counts=counts, checks=checks, propagation=propagation,
        witnesses=witnesses, elapsed_seconds=time.monotonic() - started, source_sha256=pins,
        blocks_sha256=digest(args.out / 'blocks.tsv'), target_sha256=digest(args.out / 'targets.tsv'),
        hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='Randomly selected index blocks with exact necessary-condition filtering inside each block. Block target counts include possible overlaps, not unique inputs. Every retained tie receives Fraction replay. Discarded indices have an outer-boundary exclusion, not a hardware label; no global all-index search is claimed.')
    save(args.out / 'REPORT.json', report)
    print('PASS', json.dumps(dict(counts=counts, propagation=propagation, witnesses=witnesses)), flush=True)


if __name__ == '__main__':
    main()
