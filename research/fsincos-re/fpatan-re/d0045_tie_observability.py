"""Bounded exact tie-separator search with independent arithmetic replay.

All targets and masked intermediate preimages are retained. Only verified
endpoint separators are lifted for later hardware discrimination. No native
instruction, hardware label, private ledger or main algorithm is touched.
"""
import argparse
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import random
import subprocess
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored, traced_kernel
from d0041_inner_tie_preimages import NODES
from prepare import save
from prepare_d0033 import neighbor

HERE = Path(__file__).resolve().parent


def target_and_correction(node, u, altered=False):
    """Independent Fraction replay with u as a relaxed internal input."""
    rom, truncate, nearest = audit.ROM, audit.T, audit.N64
    v = truncate(u * u, 67)
    target = None

    def target_round(value):
        nonlocal target
        target = value
        event = audit.event(value, 64)
        assert event['relation'] == 'tie'
        if not altered:
            return nearest(value)
        unit = audit.two(audit.exponent(abs(value)) - 63)
        q = abs(value) / unit
        whole = q.numerator // q.denominator
        return (-1 if value < 0 else 1) * (whole + int(not (whole & 1))) * unit

    if node >= 2:
        even = truncate(rom[114] + truncate(v * rom[116], 67), 67)
        pre = rom[115] + truncate(v * rom[117], 67)
        odd = target_round(pre) if node == 2 else nearest(pre)
    else:
        odd_pre = rom[121] + truncate(v * rom[123], 67)
        even_pre = rom[120] + truncate(v * rom[122], 67)
        odd_inner = target_round(odd_pre) if node == 0 else nearest(odd_pre)
        even_inner = target_round(even_pre) if node == 1 else nearest(even_pre)
        odd = truncate(rom[119] + truncate(v * odd_inner, 67), 67)
        even = truncate(rom[118] + truncate(v * even_inner, 67), 67)
    pre = truncate(u * odd, 67) + even
    correction = target_round(pre) if node == 3 else nearest(pre)
    assert target is not None
    return target, correction


@lru_cache(maxsize=4096)
def replay_z(node, m, step):
    z = m * audit.two(step)
    value, records = traced_kernel(z, node >= 2)
    event = next(record for record in records if record[0] == NODES[node])
    assert event[3] == 'tie'
    changed, _ = traced_kernel(z, node >= 2,
        (NODES[node], 'ties-away' if event[4] == 0 else 'ties-zero'))
    return z, value, changed, event[4]


def lift_at(z, cell, rng, attempts):
    c = audit.Q(cell, 32)
    ratio = (c + z) / (1 - c * z) if cell else z
    for attempt in range(attempts):
        x = audit.Raw80(16383, (1 << 63) | rng.getrandbits(63))
        y, _ = audit.SPEC['pack_angle'](ratio * audit.SPEC['decode'](x), 'RN')
        for delta in (-1, 0, 1):
            a = audit.Raw80(*neighbor(y.se, y.sig, delta))
            state = audit.reduction(audit.core_key(a, x))
            if state['cell'] == cell and state['z'] == z:
                return a, x, state, attempt + 1
    return None


def verify(output, lift_attempts):
    counts = Counter()
    targets, witnesses = {}, []
    rng = random.Random('d0045-verified-cell-specific-lifts')
    rows = output / 'miner.tsv'
    with rows.open() as stream:
        for line in stream:
            parts = line.split()
            kind, node, search, e, um, parity = parts[:6]
            node, search, e, um, parity = int(node), int(search), int(e), int(um, 16), int(parity)
            u = um * audit.two(e - 63)
            key = node, search
            if kind == 'T':
                assert key not in targets
                target, correction = target_and_correction(node, u)
                same_target, other_correction = target_and_correction(node, u, True)
                assert target == same_target
                assert audit.event(target, 64)['parity'] == parity
                changed = correction != other_correction
                assert changed == bool(int(parts[6]))
                targets[key] = (e, um, parity, changed)
                counts['ties'] += 1
                counts['H_changed'] += changed
                counts[f'parity{parity}'] += 1
                continue
            assert targets[key] == (e, um, parity, True)
            m, step = int(parts[6], 16), int(parts[7])
            z, kernel, other, actual_parity = replay_z(node, m, step)
            assert parity == actual_parity
            assert audit.N64(z * audit.T(z, 64)) == u
            if kind == 'Z':
                counts['square_preimages_after_H_change'] += 1
                changed = audit.T(kernel, 67) != audit.T(other, 67)
                assert changed == bool(int(parts[8]))
                counts['pre_anchor_cut_changed'] += changed
                continue
            assert kind == 'W'
            sign, cell, mask = int(parts[8]), int(parts[9]), int(parts[10], 16)
            state = dict(path='table' if cell else 'direct', cell=cell)
            fixed = restored(state, sign * kernel)
            changed = restored(state, sign * other)
            vector, alternate = audit.endpoint_vector(fixed), audit.endpoint_vector(changed)
            checked_mask = sum((a != b) << i for i, (a, b) in enumerate(zip(vector, alternate)))
            assert checked_mask == mask
            counts['cell_proposals'] += 1
            if not mask:
                continue
            counts['internal_endpoint_separators'] += 1
            result = lift_at(sign * z, cell, rng, lift_attempts)
            witness = dict(node=node, search=search, square_exponent=e,
                square_sig=f'{um:016x}', parity=parity, z_sig=f'{m:x}', z_step=step,
                sign=sign, cell=cell, endpoint_mask=f'{mask:04x}')
            if result is None:
                witness.update(status='EXTERNAL_LIFT_UNKNOWN', bounded_attempts=lift_attempts)
                counts['external_lift_unknown'] += 1
            else:
                y, x, actual, attempts = result
                assert fixed[0] == audit.SPEC['finite_angle'](y, x)
                assert actual['z'] == sign * z and actual['cell'] == cell
                witness.update(status='EXACT_EXTERNAL_ENDPOINT_SEPARATOR', attempts=attempts,
                    raw=[f'{y.se:04x}', f'{y.sig:016x}', f'{x.se:04x}', f'{x.sig:016x}'])
                counts['external_endpoint_separators'] += 1
            witnesses.append(witness)
    return dict(counts=counts, witnesses=witnesses)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--node', required=True, type=int)
    parser.add_argument('--searches', required=True, type=int)
    parser.add_argument('--exponent', required=True, type=int)
    parser.add_argument('--lift-attempts', type=int, default=4096)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    names = ('d0045_tie_observability.py', 'd0045_tie_observability_miner.c',
        'd0041_inner_tie_miner.c', 'd0041_inner_tie_preimages.py',
        'd0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
        'prepare_d0033.py', 'fpatan_candidate.c', 'PSEUDOCODE.md')
    pins = {name: digest(HERE / name) for name in names}
    command = [str(args.binary.resolve()), str(args.node), str(args.searches), str(args.exponent)]
    started = time.monotonic()
    save(args.out / 'STARTED.json', dict(status='SOFTWARE_ONLY_TIE_DISCRIMINATOR_SEARCH',
        command=command, source_sha256=pins, binary_sha256=digest(args.binary), hardware_executed=False))
    with (args.out / 'miner.tsv').open('x') as target, (args.out / 'miner.log').open('x') as log:
        process = subprocess.Popen(command, stdout=target, stderr=subprocess.PIPE, text=True)
        for line in process.stderr:
            log.write(line)
            log.flush()
            print(line.rstrip(), flush=True)
        assert process.wait() == 0
    print('Independent exact replay and cell-specific lifting', flush=True)
    result = verify(args.out, args.lift_attempts)
    for name, sha in pins.items():
        assert digest(HERE / name) == sha
    save(args.out / 'REPORT.json', dict(status='VERIFIED_BOUNDED_TIE_OBSERVABILITY_SEARCH',
        **result, node=args.node, searches=args.searches, square_exponent=args.exponent,
        elapsed_seconds=time.monotonic() - started, source_sha256=pins,
        binary_sha256=digest(args.binary), target_sha256=digest(args.out / 'miner.tsv'),
        log_sha256=digest(args.out / 'miner.log'), hardware_executed=False,
        hardware_labels_opened=False, numerical_model_changed=False,
        limits='Bounded target construction and external lifting, not global monotonicity, unreachability or hardware tie identification. All cell endpoint predictions precede any new capture.'))
    print('PASS', json.dumps(result['counts']), flush=True)


if __name__ == '__main__':
    main()
