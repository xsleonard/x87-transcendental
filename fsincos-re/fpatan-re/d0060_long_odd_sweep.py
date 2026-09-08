"""Sequential long-odd target-lattice sweep with checked native floor sums.

The D0056 analytic filter is unchanged. Only its exact residue enumeration
is accelerated; every retained tie still receives the independent Fraction
graph and every changed H is propagated through the actual external graph.
Sequential blocks have no within-run target-index overlaps. Completion of
a specified interval is not a claim about other square binades or hardware.
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
from d0049_algebraic_tie_preimages import domains, invert_target, graph, fraction, target_event, expose
from d0056_outer_boundary_lattice import parameters, filtered_indices
from d0060_fast_offsets import FastOffsets
from prepare import save

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--first-block', type=int, default=0)
    parser.add_argument('--blocks', type=int, required=True)
    parser.add_argument('--check-every', type=int, default=4096)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.first_block >= 0 and args.blocks > 0 and args.check_every > 0
    args.out.mkdir(exist_ok=False)
    choices = domains(0, -9)
    assert len(choices) == 1
    domain = choices[0]
    bounds = parameters(0, domain)
    width = 1 << 20
    assert args.first_block + args.blocks <= (domain['count'] + width - 1) // width
    fast = FastOffsets(args.library.resolve())
    names = ('d0060_long_odd_sweep.py', 'd0060_fast_offsets.py', 'd0060_boundary_offsets.c',
             'd0056_outer_boundary_lattice.py', 'd0049_algebraic_tie_preimages.py',
             'd0045_tie_observability.py', 'd0037_polynomial_node_census.py',
             'd0031_internal_rounding_coverage.py', 'fpatan_candidate.c', 'PSEUDOCODE.md')
    pins = {name: digest(HERE / name) for name in names}
    library_sha = digest(args.library)
    verified = HERE.parent / 'tmp/fpatan-re/d0060-offsets-verification/REPORT.json'
    prior = json.loads(verified.read_text())
    assert prior['status'] == 'PASS_EXACT_OFFSETS_PYTHON_C_SANITIZER'
    assert prior['evidence_sha256'][str(args.library)] == library_sha
    save(args.out / 'STARTED.json', dict(status='SEQUENTIAL_LONG_ODD_TARGET_INTERVAL_RUNNING',
        node=0, exponent=-9, first_block=args.first_block, blocks=args.blocks, block_bits=20,
        domain=domain, boundary_parameters=bounds, source_sha256=pins,
        library_path=str(args.library), library_sha256=library_sha,
        offsets_verification_sha256=digest(verified), hardware_executed=False))
    counts, checks, propagation = Counter(), Counter(), Counter()
    witnesses, last_word = [], None
    rng = random.Random(f'd0060-lifts:{args.first_block}:{args.blocks}')
    started = time.monotonic()
    with (args.out / 'blocks.tsv').open('x') as blocks, (args.out / 'targets.tsv').open('x') as stream:
        for block in range(args.first_block, args.first_block + args.blocks):
            start = block * width
            length = min(width, domain['count'] - start)
            candidates = fast.long_indices(bounds, start, length)
            if (block - args.first_block) % args.check_every == 0:
                assert candidates == list(filtered_indices(bounds, start, length))
                checks['complete_block_offset_comparisons'] += 1
            blocks.write(f'0 {start} {length} {len(candidates)}\n')
            counts['sequential_blocks'] += 1
            counts['distinct_target_indices_in_interval'] += length
            counts['boundary_candidate_indices'] += len(candidates)
            for index in candidates:
                term = domain['first'] + index * domain['modulus']
                for word in invert_target(domain, term):
                    # Product target intervals are ordered and disjoint.
                    # Enforce that invariant instead of accumulating a huge
                    # duplicate set during a sequential complete interval.
                    assert last_word is None or word > last_word
                    last_word = word
                    target, h, outer = graph(0, (word, -72))
                    same_target, alternate, other_outer = graph(0, (word, -72), True)
                    assert target == same_target
                    parity = target_event(target)
                    counts['ties'] += 1
                    counts[f'parity{parity}'] += 1
                    counts['first_outer_changed'] += outer != other_outer
                    counts['H_changed'] += h != alternate
                    stream.write(f'T 0 {block} -9 {word:016x} {parity} {int(h != alternate)} {int(outer != other_outer)}\n')
                    ft, fh = target_and_correction(0, word * audit.two(-72))
                    _, fo = target_and_correction(0, word * audit.two(-72), True)
                    assert (fraction(target), fraction(h), fraction(alternate)) == (ft, fh, fo)
                    checks['all_retained_ties_fraction_replayed'] += 1
                    if h != alternate:
                        expose(0, -9, word, block, parity, stream, propagation, witnesses, rng)
            if (block - args.first_block) % 4096 == 0:
                stream.flush()
                blocks.flush()
                print('PROGRESS', block, dict(counts), dict(propagation),
                      'seconds', round(time.monotonic() - started, 2), flush=True)
    assert digest(args.library) == library_sha
    assert all(digest(HERE / name) == sha for name, sha in pins.items())
    save(args.out / 'REPORT.json', dict(status='VERIFIED_SEQUENTIAL_LONG_ODD_INTERVAL',
        node=0, square_exponent=-9, first_block=args.first_block, blocks=args.blocks,
        counts=counts, checks=checks, propagation=propagation, witnesses=witnesses,
        elapsed_seconds=time.monotonic() - started, source_sha256=pins,
        library_path=str(args.library), library_sha256=library_sha,
        offsets_verification_sha256=digest(verified),
        blocks_sha256=digest(args.out / 'blocks.tsv'), target_sha256=digest(args.out / 'targets.tsv'),
        hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='Complete exact necessary-condition exclusion on the specified sequential target interval, and full Fraction replay of all retained ties. No within-run target-index overlap; prior sampled searches may overlap it. Not other binades, not hardware rule identification without separating observations.'))
    print('PASS', json.dumps(dict(counts=counts, propagation=propagation, witnesses=witnesses)), flush=True)


if __name__ == '__main__':
    main()
