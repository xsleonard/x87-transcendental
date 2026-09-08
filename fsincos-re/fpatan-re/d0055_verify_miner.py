"""Cross-check optimized/sanitized C dyads against independent exact replay."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0045_tie_observability import target_and_correction
from d0049_algebraic_tie_preimages import graph, fraction
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--optimized', type=Path, required=True)
    parser.add_argument('--sanitized', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    pins, counts, cases = {}, Counter(), {n: {} for n in range(3)}
    for node in range(3):
        directory = BASE / f'd0045-node{node}-upper'
        report = json.loads((directory / 'REPORT.json').read_text())
        assert digest(directory / 'miner.tsv') == report['target_sha256']
        pins[str(directory / 'REPORT.json')] = digest(directory / 'REPORT.json')
        with (directory / 'miner.tsv').open() as stream:
            for line in stream:
                p = line.split()
                if p[0] == 'T':
                    cases[node][int(p[4], 16)] = (int(p[3]), int(p[5]), int(p[6]))
                    counts['prior_GMP_target_occurrences'] += 1
    assert counts['prior_GMP_target_occurrences'] == 93678
    for name in ('d0052-wide-masking.json', 'd0052-expanded-masking.json'):
        path = BASE / name
        data = json.loads(path.read_text())
        for source, sha in data['artifact_sha256'].items():
            assert digest(Path(source)) == sha
        pins[str(path)] = digest(path)
        for result in data['results'].values():
            for row in result['selected_states']:
                node, um = row['node'], int(row['square_sig'], 16)
                case = row['square_exponent'], row['parity'], int(audit.Q(row['changes']['H']) != 0)
                if um in cases[node]:
                    assert cases[node][um] == case
                cases[node][um] = case
    for node in range(3):
        exponent = -13 if node == 2 else -9
        inputs = args.out / f'node{node}-inputs.txt'
        with inputs.open('x') as stream:
            for word, (e, _, _) in cases[node].items():
                assert e == exponent
                stream.write(f'{word:016x}\n')
        outputs = []
        for label, binary in (('optimized', args.optimized), ('sanitized', args.sanitized)):
            output = args.out / f'node{node}-{label}.txt'
            errors = args.out / f'node{node}-{label}.stderr'
            with inputs.open() as source, output.open('x') as target, errors.open('x') as log:
                run = subprocess.run([str(binary.resolve()), 'replay', str(node), str(exponent)],
                                     stdin=source, stdout=target, stderr=log)
            assert run.returncode == 0, (node, label, errors)
            assert errors.stat().st_size == 0
            outputs.append(output)
            pins[str(binary)] = digest(binary)
            pins[str(output)] = digest(output)
            pins[str(errors)] = digest(errors)
        assert digest(outputs[0]) == digest(outputs[1])
        seen = set()
        with outputs[0].open() as stream:
            for line in stream:
                p = line.split()
                assert p[0] == 'R' and len(p) == 11
                um, parity, changed, outer_changed = int(p[1], 16), *map(int, p[2:5])
                assert um not in seen
                seen.add(um)
                assert cases[node][um][1:] == (parity, changed)
                actual = tuple(int(p[i], 16) * audit.two(int(p[i + 1])) for i in (5, 7, 9))
                t, h, outer = graph(node, (um, exponent - 63))
                same_t, other, alternate_outer = graph(node, (um, exponent - 63), True)
                assert t == same_t and (outer != alternate_outer) == bool(outer_changed)
                target, fh = target_and_correction(node, um * audit.two(exponent - 63))
                _, fo = target_and_correction(node, um * audit.two(exponent - 63), True)
                assert actual == (fraction(t), fraction(h), fraction(other)) == (target, fh, fo)
                counts[f'node{node}:distinct_replayed'] += 1
                counts[f'node{node}:changed_H'] += changed
                counts[f'node{node}:changed_outer'] += outer_changed
        assert seen == set(cases[node])
        pins[str(inputs)] = digest(inputs)
        print('PASS full dyadic/Fraction and sanitized replay node', node, len(seen), flush=True)
    for name in ('d0055_verify_miner.py', 'd0055_fast_tie_miner.c', 'd0055_fast_tie_search.py',
                 'd0045_tie_observability.py', 'd0049_algebraic_tie_preimages.py',
                 'fpatan_candidate.c', 'PSEUDOCODE.md'):
        pins[str(HERE / name)] = digest(HERE / name)
    save(args.out / 'REPORT.json', dict(status='PASS_C_DYADIC_FRACTION_SANITIZER_REPLAY',
        counts=counts, evidence_sha256=pins, hardware_executed=False,
        numerical_model_changed=False, goal_complete=False,
        limits='Complete replay of the specified historical targets and saved carry fixtures; not an all-input proof of C helpers or a hardware tie identification.'))


if __name__ == '__main__':
    main()
