"""Authenticate endpoint witnesses from a completed prefix of a live scan.

The ongoing scan is neither stopped nor labelled complete. Its immutable
newline-terminated prefix is copied and hashed locally. Selected W records
are independently replayed and lifted; this does not depend on the scan's
unfinished in-memory witness list. No hardware capture is performed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import subprocess

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored
from d0045_tie_observability import replay_z, lift_at, target_and_correction
from d0049_algebraic_tie_preimages import graph, fraction
from prepare import save

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scan', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--optimized', type=Path, required=True)
    parser.add_argument('--sanitized', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    started = json.loads((args.scan / 'STARTED.json').read_text())
    assert started['node'] == 0 and started['exponent'] == -9
    for name, sha in started['source_sha256'].items():
        assert digest(HERE / name) == sha
    assert digest(Path(started['library_path'])) == started['library_sha256']
    path = args.scan / 'targets.tsv'
    size = path.stat().st_size
    with path.open('rb') as source:
        data = source.read(size)
    assert len(data) == size and b'\n' in data
    data = data[:data.rfind(b'\n') + 1]
    prefix = args.out / 'targets-prefix.tsv'
    with prefix.open('xb') as target:
        target.write(data)
    selected, cases = [], {}
    for line in data.decode().splitlines():
        row = line.split()
        if row[0] == 'T':
            cases[int(row[4], 16)] = tuple(map(int, row[5:8]))
        elif row[0] == 'W' and int(row[10], 16):
            selected.append(row)
    assert selected, 'No endpoint witness in this frozen prefix.'
    counts, witnesses = Counter(), []
    selected_words = set()
    rng = random.Random('d0062-independent-prefix-lifts')
    for row in selected:
        _, node, search, exponent, word_text, parity, z_text, step, sign, cell, mask_text = row
        node, search, exponent, word = int(node), int(search), int(exponent), int(word_text, 16)
        parity, m, step, sign, cell, mask = int(parity), int(z_text, 16), int(step), int(sign), int(cell), int(mask_text, 16)
        assert (node, exponent, sign, cell) == (0, -9, 1, 0)
        assert cases[word] == (parity, 1, 1)
        target, h, _ = graph(0, (word, -72))
        _, alternate_h, _ = graph(0, (word, -72), True)
        ft, fh = target_and_correction(0, word * audit.two(-72))
        _, fa = target_and_correction(0, word * audit.two(-72), True)
        assert (fraction(target), fraction(h), fraction(alternate_h)) == (ft, fh, fa)
        z, value, alternate, actual_parity = replay_z(0, m, step)
        assert actual_parity == parity and audit.N64(z * audit.T(z, 64)) == word * audit.two(-72)
        state = dict(path='direct', cell=0)
        a, b = audit.endpoint_vector(restored(state, value)), audit.endpoint_vector(restored(state, alternate))
        assert mask == sum((v != w) << i for i, (v, w) in enumerate(zip(a, b)))
        witness = dict(node=node, search=search, square_exponent=exponent, square_sig=word_text,
                       parity=parity, z_sig=z_text, z_step=step, sign=sign, cell=cell, endpoint_mask=mask_text)
        found = lift_at(z, cell, rng, 8192)
        if found is None:
            witness.update(status='EXTERNAL_LIFT_UNKNOWN', bounded_attempts=8192)
            counts['external_lift_unknown'] += 1
        else:
            y, x, actual, attempts = found
            assert actual['z'] == z and actual['cell'] == cell
            assert value == audit.SPEC['finite_angle'](y, x)
            witness.update(status='EXACT_EXTERNAL_ENDPOINT_SEPARATOR', attempts=attempts,
                           raw=[f'{y.se:04x}', f'{y.sig:016x}', f'{x.se:04x}', f'{x.sig:016x}'])
            counts[f'external_parity{parity}'] += 1
        witnesses.append(witness)
        selected_words.add(word)
    input_file = args.out / 'selected-square-inputs.txt'
    with input_file.open('x') as stream:
        stream.writelines(f'{word:016x}\n' for word in sorted(selected_words))
    binary_pins, output_pins = {}, {}
    outputs = []
    for label, binary in (('optimized', args.optimized), ('sanitized', args.sanitized)):
        binary_pins[str(binary)] = digest(binary)
        output, errors = args.out / f'{label}.txt', args.out / f'{label}.stderr'
        with input_file.open() as source, output.open('x') as target, errors.open('x') as error:
            run = subprocess.run([str(binary.resolve()), 'replay', '0', '-9'], stdin=source, stdout=target, stderr=error)
        assert run.returncode == 0 and errors.stat().st_size == 0
        outputs.append(output)
        output_pins[output.name], output_pins[errors.name] = digest(output), digest(errors)
    assert digest(outputs[0]) == digest(outputs[1])
    replayed = set()
    for line in outputs[0].read_text().splitlines():
        row = line.split()
        word = int(row[1], 16)
        assert word in selected_words and word not in replayed
        assert tuple(map(int, row[2:5])) == cases[word]
        t, h, _ = graph(0, (word, -72))
        _, other, _ = graph(0, (word, -72), True)
        actual = tuple(int(row[i], 16) * audit.two(int(row[i + 1])) for i in (5, 7, 9))
        assert actual == (fraction(t), fraction(h), fraction(other))
        replayed.add(word)
    assert replayed == selected_words
    with path.open('rb') as source:
        assert source.read(len(data)) == data
    save(args.out / 'REPORT.json', dict(status='VERIFIED_LIVE_SCAN_PREFIX_ENDPOINT_WITNESSES',
        scan_path=str(args.scan), scan_started_sha256=digest(args.scan / 'STARTED.json'),
        source_size_at_snapshot=size, prefix_bytes=len(data), prefix_sha256=digest(prefix),
        selected_records=selected, witnesses=witnesses, counts=counts,
        independent_C_square_replays=len(replayed), binary_sha256=binary_pins,
        output_sha256=output_pins, selected_square_inputs_sha256=digest(input_file),
        source_sha256={**started['source_sha256'], 'd0062_freeze_long_prefix.py': digest(Path(__file__))},
        scan_completion_claimed=False, hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='These finite witnesses are authenticated independently of the unfinished scan. The prefix does not certify a complete block interval or the full planned search. A bounded failed external lift is UNKNOWN.'))
    print('PASS prefix witnesses', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
