"""Independently verify C-mined quadrant/RC/C1 boundary neighborhoods.

No hardware is run or opened. The complete nine-point neighborhoods are
retained. A transition is an exact local endpoint bracket, not a statement
that either its angle or the full graph is globally monotone.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from prepare import save
from prepare_d0033 import neighbor

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def ordered_raw(a, b, quadrant, negative_y=False):
    y, x = (a, b) if quadrant < 2 else (b, a)
    return y[0] | (32768 if negative_y else 0), y[1], x[0] | (32768 if quadrant & 1 else 0), x[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.binary.is_file()
    args.out.mkdir(exist_ok=False)
    seeds = args.out / 'seeds.tsv'
    sources = {name: digest(HERE / name) for name in
               ('d0034_quadrant_boundary_miner.c', 'd0034_quadrant_boundary_mining.py',
                'd0031_internal_rounding_coverage.py', 'prepare_d0033.py',
                'fpatan_candidate.c', 'PSEUDOCODE.md')}
    save(args.out / 'STARTED.json', dict(status='SOFTWARE_MINING_RUNNING',
        binary_sha256=digest(args.binary), source_sha256=sources, hardware_executed=False))
    with seeds.open('xb') as destination:
        process = subprocess.run([str(args.binary)], stdout=destination,
                                 stderr=subprocess.PIPE, check=True)
    native_counts = json.loads(process.stderr)
    groups, coverage, events, distances, examples = defaultdict(dict), Counter(), Counter(), {}, {}
    for line in seeds.read_text().splitlines():
        ident, family, quadrant, rc, offset, ase, am, bse, bm, se, sig, c1 = line.split()
        a, b = (int(ase, 16), int(am, 16)), (int(bse, 16), int(bm, 16))
        quadrant, offset, ident = int(quadrant), int(offset), int(ident)
        raw = ordered_raw(a, b, quadrant)
        y, x = audit.Raw80(*raw[:2]), audit.Raw80(*raw[2:])
        angle = audit.SPEC['finite_angle'](y, x)
        result, flag = audit.SPEC['pack_angle'](angle, rc.upper())
        assert (result.se, result.sig, flag) == (int(se, 16), int(sig, 16), int(c1))
        assert offset not in groups[ident]
        state = audit.reduction(audit.core_key(y, x))
        groups[ident][offset] = dict(a=a, b=b, raw=raw, family=family, quadrant=quadrant,
            rc=rc, result=(result.se, result.sig, flag), path=state['path'], cell=state['cell'])
        if offset in (-1, 0):
            event = audit.event(angle, 64, -16382)
            label = f'{audit.RESTORATIONS[quadrant]}:{rc}:{state["path"]}'
            for boundary in ('half', 'integer'):
                distance = event['distance_' + boundary]
                key = label + ':' + boundary
                if key not in distances or distance < distances[key]:
                    distances[key], examples[key] = distance, dict(raw=raw, seed=ident, offset=offset)
    assert len(groups) == native_counts['seeds']
    assert sum(len(group) for group in groups.values()) == native_counts['rows']
    for ident, group in groups.items():
        assert set(group) == set(range(-4, 5))
        crossing = group[0]
        quadrant = crossing['quadrant']
        direction = 1 if quadrant in (0, 3) else -1
        label = f'{audit.RESTORATIONS[quadrant]}:{crossing["rc"]}:{crossing["path"]}:cell{crossing["cell"]}'
        coverage[label] += 1
        keys = []
        for offset in range(-4, 5):
            row = group[offset]
            assert row['a'] == neighbor(*crossing['a'], offset)
            assert row['b'] == crossing['b']
            se, sig, c1 = row['result']
            keys.append((se, sig, 1 - c1))
        assert (keys[3] < keys[4]) if direction > 0 else (keys[3] > keys[4])
        kind = 'value' if group[-1]['result'][:2] != crossing['result'][:2] else 'C1-only'
        events[f'{audit.RESTORATIONS[quadrant]}:{crossing["rc"]}:{kind}'] += 1
        events['local_reversals'] += sum((keys[i] > keys[i + 1]) if direction > 0 else (keys[i] < keys[i + 1]) for i in range(8))
    for name, expected in sources.items():
        assert digest(HERE / name) == expected
    save(args.out / 'REPORT.json', dict(status='INDEPENDENTLY_VERIFIED_QUADRANT_BOUNDARY_WINDOWS',
        counts=native_counts, coverage=coverage, events=events,
        best_boundary_distances={k: str(v) for k, v in distances.items()}, closest_examples=examples,
        seeds_sha256=digest(seeds), binary_sha256=digest(args.binary), source_sha256=sources,
        verified_neighbor_rows=native_counts['rows'],
        hardware_executed=False, hardware_labels_opened=False, capture_manifest_frozen=False,
        limit='Software-mined local endpoint/C1 brackets. Skipped ranges are not impossibility proofs; no hardware correctness claim.'))
    print('PASS independent quadrant windows:', json.dumps(dict(counts=native_counts, events=events)), flush=True)


if __name__ == '__main__':
    main()
