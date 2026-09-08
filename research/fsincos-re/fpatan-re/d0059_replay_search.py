"""Independent optimized/sanitized C replay of a frozen filtered search.

All retained T rows are replayed, not merely the successful witnesses.
Every Z and W propagation row is re-evaluated by the Fraction kernel.
No native FPATAN or hardware observation is performed by this program.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored, traced_kernel
from d0045_tie_observability import replay_z
from d0049_algebraic_tie_preimages import graph, fraction
from prepare import save

HERE = Path(__file__).resolve().parent
NODES = ('odd_inner_sum', 'even_inner_sum', 'odd_sum')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--search', type=Path, required=True)
    parser.add_argument('--optimized', type=Path, required=True)
    parser.add_argument('--sanitized', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    report = json.loads((args.search / 'REPORT.json').read_text())
    assert report['status'] in ('VERIFIED_TRUNCATED_SHORT_ODD_BOUNDARY_SEARCH',
                                'VERIFIED_BOUNDARY_FILTERED_TIE_SEARCH')
    node, exponent = report['node'], report['square_exponent']
    pins = {}
    for name, key in (('targets.tsv', 'target_sha256'), ('blocks.tsv', 'blocks_sha256')):
        path = args.search / name
        assert digest(path) == report[key]
        pins[str(path)] = report[key]
    for name, sha in report['source_sha256'].items():
        assert digest(HERE / name) == sha
        pins[str(HERE / name)] = sha
    pins[str(args.search / 'REPORT.json')] = digest(args.search / 'REPORT.json')
    counts, cases = Counter(), {}
    inputs = args.out / 'inputs.txt'
    with (args.search / 'targets.tsv').open() as stream, inputs.open('x') as target_inputs:
        for line in stream:
            row = line.split()
            assert int(row[1]) == node and int(row[3]) == exponent
            word, parity = int(row[4], 16), int(row[5])
            counts[row[0] + '_rows'] += 1
            if row[0] == 'T':
                assert word not in cases
                cases[word] = (parity, int(row[6]), int(row[7]))
                target_inputs.write(f'{word:016x}\n')
                continue
            assert word in cases and cases[word][1] == 1
            m, step = int(row[6], 16), int(row[7])
            z, value, alternate, checked_parity = replay_z(node, m, step)
            assert checked_parity == parity
            assert audit.N64(z * audit.T(z, 64)) == word * audit.two(exponent - 63)
            if row[0] == 'Z':
                changed = audit.T(value, 67) != audit.T(alternate, 67)
                assert int(changed) == int(row[8])
                counts['cut_changes'] += changed
                continue
            assert row[0] == 'W'
            sign, cell, mask = int(row[8]), int(row[9]), int(row[10], 16)
            state = dict(path='table' if cell else 'direct', cell=cell)
            a = audit.endpoint_vector(restored(state, sign * value))
            b = audit.endpoint_vector(restored(state, sign * alternate))
            assert mask == sum((first != second) << i for i, (first, second) in enumerate(zip(a, b)))
            counts['endpoint_masks_nonzero'] += bool(mask)
    assert counts['T_rows'] == report['counts']['ties']
    assert counts['Z_rows'] == report['propagation'].get('square_preimages_after_H_change', 0)
    assert counts['W_rows'] == report['propagation'].get('cell_proposals', 0)
    assert counts['cut_changes'] == report['propagation'].get('pre_anchor_cut_changed', 0)
    assert counts['endpoint_masks_nonzero'] == report['propagation'].get('internal_endpoint_separators', 0)
    outputs = []
    for label, binary in (('optimized', args.optimized), ('sanitized', args.sanitized)):
        output = args.out / f'{label}.txt'
        errors = args.out / f'{label}.stderr'
        pins[str(binary)] = digest(binary)
        with inputs.open() as source, output.open('x') as target, errors.open('x') as log:
            run = subprocess.run([str(binary.resolve()), 'replay', str(node), str(exponent)],
                                 stdin=source, stdout=target, stderr=log)
        assert run.returncode == 0 and errors.stat().st_size == 0, (label, run.returncode)
        assert digest(binary) == pins[str(binary)]
        outputs.append(output)
        pins[str(output)] = digest(output)
        pins[str(errors)] = digest(errors)
    assert digest(outputs[0]) == digest(outputs[1])
    seen = set()
    with outputs[0].open() as source:
        for line in source:
            row = line.split()
            assert row[0] == 'R' and len(row) == 11
            word = int(row[1], 16)
            assert word not in seen
            seen.add(word)
            assert cases[word] == tuple(map(int, row[2:5]))
            actual = tuple(int(row[i], 16) * audit.two(int(row[i + 1])) for i in (5, 7, 9))
            target, h, _ = graph(node, (word, exponent - 63))
            same_target, alternate, _ = graph(node, (word, exponent - 63), True)
            assert target == same_target
            assert actual == (fraction(target), fraction(h), fraction(alternate))
            counts['C_dyadic_replays'] += 1
            counts['H_changes'] += h != alternate
    assert seen == set(cases)
    assert counts['H_changes'] == report['counts']['H_changed']
    for row in report['witnesses']:
        if row['status'] == 'EXTERNAL_LIFT_UNKNOWN':
            counts['bounded_lift_UNKNOWN_preserved'] += 1
            continue
        assert row['status'] == 'EXACT_EXTERNAL_ENDPOINT_SEPARATOR'
        ys, ym, xs, xm = (int(word, 16) for word in row['raw'])
        y, x = audit.Raw80(ys, ym), audit.Raw80(xs, xm)
        state = audit.reduction(audit.core_key(y, x))
        assert state['cell'] == row['cell']
        assert state['z'] == row['sign'] * int(row['z_sig'], 16) * audit.two(row['z_step'])
        first, records = traced_kernel(state['z'], bool(state['cell']))
        event = next(r for r in records if r[0] == NODES[node])
        assert event[3:5] == ('tie', row['parity'])
        second, _ = traced_kernel(state['z'], bool(state['cell']),
            (NODES[node], 'ties-away' if row['parity'] == 0 else 'ties-zero'))
        first_angles = restored(state, first)
        second_angles = restored(state, second)
        assert first_angles[0] == audit.SPEC['finite_angle'](y, x)
        a, b = audit.endpoint_vector(first_angles), audit.endpoint_vector(second_angles)
        mask = sum((v != w) << i for i, (v, w) in enumerate(zip(a, b)))
        assert mask == int(row['endpoint_mask'], 16) and mask
        counts['exact_external_witnesses'] += 1
    for name in ('d0059_replay_search.py', 'd0055_fast_tie_miner.c', 'fpatan_candidate.c', 'PSEUDOCODE.md'):
        pins[str(HERE / name)] = digest(HERE / name)
    pins[str(inputs)] = digest(inputs)
    save(args.out / 'REPORT.json', dict(status='PASS_FULL_FILTERED_SEARCH_C_AND_PROPAGATION_REPLAY',
        counts=counts, source_directory=str(args.search), evidence_sha256=pins,
        hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='All retained ties and saved propagation rows independently replayed, plus exact external witness checks. Does not identify a hardware rule without discriminating observations.'))
    print('PASS', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
