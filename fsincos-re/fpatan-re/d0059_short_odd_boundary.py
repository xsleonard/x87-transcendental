"""Corrected short-odd boundary filter, retaining D0058's failed version.

D0058 omitted a necessary downward allowance for the weighted-product
truncation. A raw product above a grid point can truncate exactly onto it;
RN equality/parity then distinguishes it from another product above the
point. D0059 encloses the *truncated* products. A changed H requires their
closed interval to contain a grid point, including either endpoint.

The existing rational-root/Taylor/floor-sum machinery is reused unchanged.
This is software-only candidate generation, never a hardware selector.
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
from d0049_algebraic_tie_preimages import (
    domains, invert_target, graph, fraction, target_event, expose,
)
import d0058_short_odd_boundary as previous
from d0058_short_odd_boundary import sqrt_bracket, block_enclosure, filtered_indices
from prepare import save

HERE = Path(__file__).resolve().parent


def parameters(domain, exponent):
    p = previous.parameters(domain, exponent)
    d = domain
    maximum_target = p['first'] + (d['count'] - 1) * p['delta']
    half_inner = audit.two(audit.exponent(p['base']) - 64)
    u_max = d['u_high'] * audit.two(exponent - 63)
    product_max = u_max * (p['base'] + maximum_target + half_inner)
    product_ulp = audit.two(audit.exponent(product_max) - 66)
    # T67(product) lies in (product-product_ulp, product]. Keeping closed
    # bounds is conservative and includes equality cases at H halfways.
    p['error_low'] += product_ulp / p['grid']
    p['weighted_product_ulp'] = product_ulp
    return p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exponent', type=int, default=-13)
    parser.add_argument('--blocks', type=int, required=True)
    parser.add_argument('--block-bits', type=int, default=8)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.exponent <= -13 and args.blocks > 0 and 0 <= args.block_bits <= 24
    args.out.mkdir(exist_ok=False)
    choices = domains(2, args.exponent)
    bounds = [parameters(d, args.exponent) for d in choices]
    names = ('d0059_short_odd_boundary.py', 'd0058_short_odd_boundary.py',
             'd0056_outer_boundary_lattice.py', 'd0049_algebraic_tie_preimages.py',
             'd0045_tie_observability.py', 'd0037_polynomial_node_census.py',
             'd0031_internal_rounding_coverage.py', 'fpatan_candidate.c', 'PSEUDOCODE.md')
    pins = {name: digest(HERE / name) for name in names}
    save(args.out / 'STARTED.json', dict(status='SHORT_ODD_TRUNCATED_WEIGHTED_H_GRID_SEARCH',
        node=2, exponent=args.exponent, blocks=args.blocks, block_bits=args.block_bits,
        domains=choices, boundary_parameters=[{k: str(v) for k, v in p.items()} for p in bounds],
        source_sha256=pins, hardware_executed=False))
    rng = random.Random(f'd0059:2:{args.exponent}:{args.blocks}:{args.block_bits}')
    lift_rng = random.Random('d0059-external-lifts')
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
    report = dict(status='VERIFIED_TRUNCATED_SHORT_ODD_BOUNDARY_SEARCH', node=2,
        square_exponent=args.exponent, counts=counts, propagation=propagation,
        witnesses=witnesses, elapsed_seconds=time.monotonic() - started, source_sha256=pins,
        blocks_sha256=digest(args.out / 'blocks.tsv'), target_sha256=digest(args.out / 'targets.tsv'),
        hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='Sampled index blocks, possibly overlapping; target-index counts are occurrences, not unique external inputs. Every retained tie is independently Fraction-replayed. The corrected exclusion includes weighted-product truncation and equality cases. No all-input hardware proof.')
    save(args.out / 'REPORT.json', report)
    print('PASS', json.dumps(dict(counts=counts, propagation=propagation, witnesses=witnesses)), flush=True)


if __name__ == '__main__':
    main()
