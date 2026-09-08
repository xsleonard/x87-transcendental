"""Independently lift early/table polynomial halfways to genuine raw80 pairs.

Failed finite searches are UNKNOWN. Exact node events, downstream masking,
and actual output/C1 separation are separate quantities. No hardware labels
are read and no main numerical code changes.
"""
import argparse
from collections import Counter
import json
from math import isqrt
from pathlib import Path
import random
import subprocess
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored, traced_kernel
from prepare import save
from prepare_d0033 import neighbor

HERE = Path(__file__).resolve().parent
NODES = ('odd_inner_sum', 'even_inner_sum', 'odd_sum', 'correction_sum')
SEED = 'd0041-exact-inner-and-table-halfways-20260906'


def lift(z, table, rng):
    cells = [0]
    if table:
        cells = []
        for n in range(2, 33):
            center = audit.Q(n, 32)
            ratio = (center + z) / (1 - center * z)
            if not audit.Q(3, 64) < ratio <= 1:
                continue
            shifted = 32 * ratio - audit.Q(1, 2)
            selected = -((-shifted.numerator) // shifted.denominator)
            if selected == n:
                cells.append(n)
        rng.shuffle(cells)
        cells = cells[:2]
    for cell in cells:
        center = audit.Q(cell, 32)
        ratio = (center + z) / (1 - center * z) if table else z
        for _ in range(96):
            x = audit.Raw80(16383, (1 << 63) | rng.getrandbits(63))
            y, _ = audit.SPEC['pack_angle'](ratio * audit.SPEC['decode'](x), 'RN')
            for delta in (-1, 0, 1):
                a = audit.Raw80(*neighbor(y.se, y.sig, delta))
                state = audit.reduction(audit.core_key(a, x))
                if state['cell'] == cell and state['z'] == z:
                    return a, x, state
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    sources = {name: digest(HERE / name) for name in (
        'd0041_inner_tie_miner.c', 'd0041_inner_tie_preimages.py',
        'd0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
        'prepare_d0033.py', 'fpatan_candidate.c', 'PSEUDOCODE.md')}
    started = time.time()
    binary_sha = digest(args.binary)
    save(args.out / 'STARTED.json', dict(status='SOFTWARE_INVERSE_SEARCH_RUNNING',
        source_sha256=sources, binary_sha256=binary_sha, hardware_executed=False))
    miner = []
    squares = args.out / 'square-targets.tsv'
    with squares.open('xb') as target, (args.out / 'miner.log').open('x') as log:
        process = subprocess.Popen([str(args.binary.resolve())], stdout=target,
            stderr=subprocess.PIPE, text=True)
        for line in process.stderr:
            log.write(line)
            log.flush()
            print(line.rstrip(), flush=True)
            if line.startswith('{'):
                miner.append(json.loads(line))
        assert process.wait() == 0
    assert len(miner) == 4
    counts, parity_counts, masks, cells = Counter(), Counter(), Counter(), Counter()
    rng = random.Random(SEED)
    pool = args.out / 'candidate-pool.tsv'
    visible = []
    with squares.open() as source, pool.open('x') as target:
        for index, line in enumerate(source):
            node, ident, ue, um = line.split()
            node, ident, ue, um = int(node), int(ident), int(ue), int(um, 16)
            label = str(node)
            counts[label + ':square_targets'] += 1
            square = um * audit.two(ue - 63)
            root = isqrt(um << (69 + (ue & 1)))
            scale = ue // 2 - 66
            for m in range(root - 16, root + 17):
                zmag = m * audit.two(scale)
                if m.bit_length() != 67 or (node < 2 and zmag > audit.Q(3, 64)):
                    continue
                if audit.N64(zmag * audit.T(zmag, 64)) != square:
                    continue
                counts[label + ':square_preimages'] += 1
                for sign in ((1, -1) if node >= 2 else (1,)):
                    z = sign * zmag
                    value, records = traced_kernel(z, node >= 2)
                    record = next(r for r in records if r[0] == NODES[node])
                    assert record[1:4] == (64, 'RN', 'tie')
                    alternative, _ = traced_kernel(z, node >= 2,
                        (NODES[node], 'ties-away' if record[4] == 0 else 'ties-zero'))
                    counts[label + ':signed_internal_preimages'] += 1
                    counts[label + ':kernel_changed'] += value != alternative
                    result = lift(z, node >= 2, rng)
                    if result is None:
                        counts[label + ':external_lift_unknown'] += 1
                        continue
                    y, x, state = result
                    fixed_angles = restored(state, value)
                    other_angles = restored(state, alternative)
                    assert fixed_angles[0] == audit.SPEC['finite_angle'](y, x)
                    baseline = audit.endpoint_vector(fixed_angles)
                    other = audit.endpoint_vector(other_angles)
                    mask = sum((a != b) << i for i, (a, b) in enumerate(zip(baseline, other)))
                    raw = [f'{y.se:04x}', f'{y.sig:016x}', f'{x.se:04x}', f'{x.sig:016x}']
                    target.write(' '.join([str(node), str(ident), str(state['cell']), str(sign),
                        *raw, str(record[4]), f'{mask:04x}', f'{m:x}', str(scale)]) + '\n')
                    counts[label + ':rows'] += 1
                    counts[label + ':visible'] += bool(mask)
                    counts[label + ':after_anchor_changed'] += fixed_angles[0] != other_angles[0]
                    parity_counts[f'{node}:{record[4]}'] += 1
                    masks[f'{node}:{mask:04x}'] += 1
                    cells[f'{node}:{state["cell"]}:sign{sign}'] += 1
                    if mask:
                        visible.append(dict(node=node, raw=raw, mask=f'{mask:04x}', cell=state['cell']))
            if index % 128 == 0:
                print('Lifted square target', index, 'rows', sum(v for k, v in counts.items() if k.endswith(':rows')),
                      'seconds', round(time.time() - started, 1), flush=True)
    for row in miner:
        assert counts[str(row['node']) + ':square_targets'] == row['exact_ties']
    assert all(digest(HERE / name) == expected for name, expected in sources.items())
    assert digest(args.binary) == binary_sha
    save(args.out / 'REPORT.json', dict(status='EXACT_EARLY_AND_TABLE_HALF_PREIMAGES_VERIFIED',
        nodes=NODES, miner_counts=miner, counts=counts, parity_counts=parity_counts,
        endpoint_masks=masks, cell_coverage=cells, visible_witnesses=visible,
        source_sha256=sources, binary_sha256=binary_sha, pool_sha256=digest(pool),
        square_targets_sha256=digest(squares), log_sha256=digest(args.out / 'miner.log'),
        seconds=time.time() - started, hardware_executed=False, hardware_labels_opened=False,
        numerical_model_changed=False, capture_manifest_frozen=False,
        limits='Bounded local searches, not global monotonicity or unreachability proofs. Kernel changes and final endpoint discrimination are reported separately; non-visible ties do not validate a hidden tie rule.'))
    print('PASS exact external preimages', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
