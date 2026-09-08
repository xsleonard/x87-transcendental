"""Sanitized standalone C versus Python V6: frontier, saved and synthetic rows.

This is software implementation parity, not prospective silicon validation.
The architecture selector is analysis-only; its default remains V4.
"""
import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
from architecture import ArchitecturePolicy, predict
from d0010_causal_intervals import BASE
from prepare import save


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', type=Path, required=True)
    args = ap.parse_args()
    rng = random.Random('D0021 V6 independent C/Python implementation parity')
    lines = [r['input'] for p in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs'] for r in p['rows']]
    for job in [f'd{i:04d}' for i in range(1, 10)] + ['d0013']:
        root = BASE / job
        compressed = (root / 'inputs.txt.gz').exists()
        path = root / ('inputs.txt.gz' if compressed else 'inputs.txt')
        reservoir = []
        with (gzip.open(path, 'rt') if compressed else path.open()) as stream:
            for index, line in enumerate(stream):
                if index < 256:
                    reservoir.append(line.strip())
                else:
                    slot = rng.randrange(index + 1)
                    if slot < 256:
                        reservoir[slot] = line.strip()
        lines.extend(reservoir)
    for i in range(512):
        ys, xs = rng.randrange(32767), rng.randrange(32767)
        if i % 3 == 0:
            ys, xs = 16377 + rng.randrange(3), 16383
        ym, xm = rng.getrandbits(64), rng.getrandbits(64)
        if ys:
            ym |= 1 << 63
        if xs:
            xm |= 1 << 63
        ys |= rng.randrange(2) << 15
        xs |= rng.randrange(2) << 15
        for rc, pc in itertools.product(('rn', 'rd', 'ru', 'rz'), (24, 53, 64)):
            lines.append(f'd0021parity{i}_{rc}_{pc} {rc} {pc} {ys:04x} {ym:016x} {xs:04x} {xm:016x}')
    policy = ArchitecturePolicy(numerical_graph='v6')
    expected = []
    for line in lines:
        ident, rc, pc, *raw = line.split()
        se, sig, c1, flags, before = predict(*(int(v, 16) for v in raw), rc, policy)
        expected.append(f'{ident} {se:04x} {sig:016x} {c1} {flags:02x} {before:02x}\n')
    result = subprocess.run([str(args.binary.resolve())], input='\n'.join(lines)+'\n', text=True, capture_output=True, check=True)
    assert not result.stderr
    got = result.stdout.splitlines(keepends=True)
    assert len(got) == len(expected)
    differences = [dict(input=inp, python=want.strip(), C=actual.strip())
                   for inp, want, actual in zip(lines, expected, got) if want != actual]
    save(BASE / 'd0021-v6-sanitizer-parity.json', dict(status='SOFTWARE_PARITY_ONLY', rows=len(lines),
         differences=differences, binary_sha256=hashlib.sha256(args.binary.read_bytes()).hexdigest(),
         source_sha256={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                        for n in ('fpatan_candidate_v6.c', 'graph_v6.py', 'architecture.py', 'd0021_v6_parity.py')},
         inputs_sha256=hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest(),
         expected_sha256=hashlib.sha256(''.join(expected).encode()).hexdigest(),
         hardware_executed=False, numerical_model_promoted=False))
    assert not differences, differences[:3]
    print('PASS sanitized C/Python V6', len(lines), 'rows, all output/flags fields', flush=True)


if __name__ == '__main__':
    main()
