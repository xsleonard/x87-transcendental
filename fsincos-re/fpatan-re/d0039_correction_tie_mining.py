"""Construct and independently verify reachable correction-sum halfway cases.

The C search inverts the final direct-kernel RN64 sum, then the asymmetric
square, then lifts the retained ratio to raw80 operands. All candidates are
rechecked by the exact published reference and a separate named-node trace.
No hardware, labels, admission or capture manifest is involved in this step.
Bounded searches which find no witness make no unreachability claim.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored, traced_kernel
from prepare import save

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    assert args.binary.is_file()
    args.out.mkdir(exist_ok=False)
    sources = {name: digest(HERE / name) for name in (
        'd0039_correction_tie_miner.c', 'd0039_correction_tie_mining.py',
        'd0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
        'PSEUDOCODE.md', 'fpatan_candidate.c', 'paper/verify_pseudocode.py')}
    binary_sha = digest(args.binary)
    started = time.time()
    save(args.out / 'STARTED.json', dict(status='SOFTWARE_INVERSE_SEARCH_RUNNING',
        source_sha256=sources, binary_sha256=binary_sha, started_unix=started,
        hardware_executed=False))
    pool = args.out / 'candidate-pool.tsv'
    native_counts = None
    with pool.open('xb') as destination, (args.out / 'miner.log').open('x') as log:
        process = subprocess.Popen([str(args.binary.resolve())], stdout=destination,
                                   stderr=subprocess.PIPE, text=True)
        for line in process.stderr:
            log.write(line)
            log.flush()
            print(line.rstrip(), flush=True)
            if line.startswith('{'):
                native_counts = json.loads(line)
        assert process.wait() == 0
    assert native_counts is not None
    counts, parities, masks, searches = Counter(), Counter(), Counter(), set()
    visible = []
    with pool.open() as stream:
        for line in stream:
            ident, uexp, usig, zm, zs, ys, ym, xs, xm, mask = line.split()
            y = audit.Raw80(int(ys, 16), int(ym, 16))
            x = audit.Raw80(int(xs, 16), int(xm, 16))
            state = audit.reduction(audit.core_key(y, x))
            assert state['path'] == 'direct'
            assert state['z'] == int(zm, 16) * audit.two(int(zs))
            value, records = traced_kernel(state['z'], False)
            nodes = {record[0]: record for record in records}
            assert nodes['square'][-1] == int(usig, 16) * audit.two(int(uexp) - 63)
            correction = nodes['correction_sum']
            assert correction[1:4] == (64, 'RN', 'tie')
            parity = correction[4]
            other, _ = traced_kernel(state['z'], False,
                ('correction_sum', 'ties-away' if parity == 0 else 'ties-zero'))
            fixed = audit.endpoint_vector(restored(state, value))
            alternative = audit.endpoint_vector(restored(state, other))
            verified_mask = sum((a != b) << i for i, (a, b) in enumerate(zip(fixed, alternative)))
            assert verified_mask == int(mask, 16)
            assert value == audit.SPEC['finite_angle'](y, x)
            parities[str(parity)] += 1
            masks[mask] += 1
            searches.add(int(ident))
            counts['rows'] += 1
            counts['visible'] += bool(verified_mask)
            if verified_mask:
                visible.append(dict(search=int(ident), raw=[ys, ym, xs, xm],
                    z_wire=[zm, int(zs)], u=[int(uexp), usig], parity=parity,
                    endpoint_difference_mask=mask))
            if counts['rows'] % 4096 == 0:
                print('Independently verified', counts['rows'], 'visible', counts['visible'], flush=True)
    assert counts['rows'] == native_counts['rows']
    assert counts['visible'] == native_counts['visible']
    assert all(digest(HERE / name) == expected for name, expected in sources.items())
    assert digest(args.binary) == binary_sha
    save(args.out / 'REPORT.json', dict(status='INDEPENDENTLY_VERIFIED_CORRECTION_SUM_TIES',
        miner_counts=native_counts, verified_counts=counts,
        searches_with_lifted_pairs=len(searches), parity_counts=parities,
        endpoint_masks=masks, visible_witnesses=visible,
        pool_sha256=digest(pool), log_sha256=digest(args.out / 'miner.log'),
        source_sha256=sources, binary_sha256=binary_sha, seconds=time.time() - started,
        hardware_executed=False, hardware_labels_opened=False,
        capture_manifest_frozen=False, numerical_model_changed=False,
        limits='Exact external witnesses are verified. Bounded inverse/lift failures are UNKNOWN, not UNSAT. The bisection does not establish global monotonicity. Endpoint differences compare only a local opposite-halfway decision, not a new model.'))
    print('PASS inverse correction ties', json.dumps(dict(counts=counts, parities=parities)), flush=True)


if __name__ == '__main__':
    main()
