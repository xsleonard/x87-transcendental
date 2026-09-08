#!/usr/bin/env python3
"""Fixed paired predictions for software-mined discriminators and domain controls.

No hardware labels, private material, freshness clearance or manifest freeze.
Exact preimages are explicitly distinguished from rounded-reduction controls.
"""
import argparse
import json
import random
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import h1710_verify_paired_program as independent
from h1709_paired_retained_census import digest, save

SCAN = 'tmp/ledger33/current/h1711_paired_discriminator_scan'
MODELS = 'tmp/ledger33/current/h1710_independent_paired_program'


def encode(value):
    assert value > 0
    e = independent.rational.top(value)
    sig = value / independent.rational.p2(e - 63)
    return f'{e+16383:04x} {int(sig):016x}', sig.denominator == 1


def proposals(root):
    rng = random.Random(0x17110cafe); kinds = defaultdict(set); relations = defaultdict(list)
    def add(op, kind):
        se, sig = op.split(); assert len(se) == 4 and len(sig) == 16 and int(sig, 16) >> 63
        kinds[op].add(kind); kinds[f'{int(se,16)^0x8000:04x} {sig}'].add(kind)
    for line in (root / SCAN / 'proposals.txt').read_text().splitlines():
        se, sig, mask = line.split(); op = f'{se} {sig}'
        add(op, 'software_materialization_discriminator')
        for delta in (-2, -1, 1, 2): add(f'{se} {int(sig,16)+delta:016x}', 'discriminator_neighbor_control')
        r = int(sig, 16) * independent.rational.p2(int(se, 16) - 16383 - 63)
        # Enumerate a finite transfer family without rounding the residual.
        # Keep the first exactly representable operand in each quadrant/sign.
        seen = set()
        for q in range(1, 129):
            for direction in (-1, 1):
                key = q % 4, direction
                if key in seen: continue
                value = q * independent.rational.M66 * independent.rational.p2(-65) + direction * r
                target, exact = encode(value)
                if exact:
                    assert independent.rational.external(target, 'fsin')[0] == r
                    seen.add(key); add(target, 'exact_reduction_preimage')
                    relations[target].append(dict(direct=op, q=q, residual_sign=int(direction < 0)))
    for e in range(-32, -2):
        for _ in range(6): add(f'{e+16383:04x} {rng.getrandbits(63)|(1<<63):016x}', 'polynomial_exponent_control')
    for e in (-69, -68, -67, -34, -33, -32, -31, -3, -2, -1, 61, 62, 63):
        for edge in (1 << 63, (1 << 64) - 1):
            for _ in range(2):
                delta = rng.randrange(65, 65536)
                sig = edge + delta if edge == 1 << 63 else edge - delta
                add(f'{e+16383:04x} {sig:016x}', 'dispatch_binade_boundary')
    for boundary in (Fraction(1,4), Fraction(5,16), Fraction(3,8), Fraction(7,16),
                     Fraction(1,2), Fraction(5,8), Fraction(3,4),
                     independent.rational.M66 * independent.rational.p2(-66)):
        op, _ = encode(boundary); se, sig = op.split()
        for delta in (-rng.randrange(65, 2048), rng.randrange(65, 2048)):
            n = int(sig,16) + delta; ef = int(se,16)
            if n < 1 << 63: n *= 2; ef -= 1
            if n >= 1 << 64: n //= 2; ef += 1
            add(f'{ef:04x} {n:016x}', 'table_dispatch_boundary')
    for q in (1,2,3,4,7,8,15,16,31,127,1024,65537,(1<<30)+1,(1<<50)+3,(1<<61)+1):
        for offset in (Fraction(1,1<<32),Fraction(1,8),Fraction(1,4),Fraction(1,2)):
            for direction in (-1,1):
                v = q * independent.rational.M66 * independent.rational.p2(-65) + direction * offset
                op, _ = encode(v); se, sig = op.split()
                # Deliberately near, not exact isomorphs. Freshness is separate.
                n = int(sig,16) + rng.randrange(65,2048)
                if n >= 1 << 64: n //= 2; se = f'{int(se,16)+1:04x}'
                add(f'{se} {n:016x}', 'reduction_boundary_bracket')
    return [dict(operand=op, kinds=sorted(kinds[op]), exact_relations=relations[op]) for op in sorted(kinds)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path); p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root = a.root.resolve(); out = a.output_dir.resolve(); assert not out.exists()
    report = json.loads((root / SCAN / 'report.json').read_text())
    assert report['status'] == 'SOFTWARE_ONLY_NOT_FROZEN'
    assert digest(root / SCAN / 'proposals.txt') == report['sha256']['proposals']
    independent.constants(root); rows = proposals(root); ops = [r['operand'] for r in rows]
    original = json.loads((root / MODELS / 'report.json').read_text()); cache = {}; counts = Counter()
    for row in rows: row['predictions'] = {}
    for policy in ('baseline', 'last', 'all'):
        binary = root / MODELS / (policy + '_O2')
        assert digest(binary) == original['sha256']['binaries'][binary.name]
        for mode in ('rn','rd','ru','rz'):
            values, metadata = independent.run(binary, mode, ops, True)
            for i, row in enumerate(rows):
                value, meta = independent.expected(row['operand'], mode, policy, cache)
                assert (values[i], metadata.get(i)) == (value, meta), (policy, mode, row['operand'])
                row['predictions'].setdefault(policy, {})[mode] = dict(outputs=value,
                    path=meta[0] if meta else 'range', C1=meta[3] if meta and meta[1] else None)
                counts['independent_instruction_rows'] += 1
                counts['independent_lane_outputs'] += 2 if value is not None else 0
    for row in rows:
        row['discriminator_modes'] = [mode for mode in ('rn','rd','ru','rz')
            if row['predictions']['baseline'][mode] != row['predictions']['last'][mode]]
        row['last_vs_all_modes'] = [mode for mode in ('rn','rd','ru','rz')
            if row['predictions']['last'][mode] != row['predictions']['all'][mode]]
    out.mkdir(parents=True)
    bank = dict(experiment='h1711_paired_challenge_bank', capture_state='SOFTWARE_ONLY_NOT_FROZEN',
        hardware_execution='none', private_access='none', candidate_changed=False, manifest_frozen=False,
        counts=dict(counts), operands=rows, kind_memberships=dict(Counter(k for r in rows for k in r['kinds'])),
        discriminator_operands=sum(bool(r['discriminator_modes']) for r in rows),
        last_vs_all_operands=sum(bool(r['last_vs_all_modes']) for r in rows),
        claim_boundary='Fixed paired graph predictions and software search only. No uniqueness, freshness or silicon claim.',
        sha256=dict(script=digest(Path(__file__)), verifier=digest(Path(independent.__file__)),
            scan_report=digest(root / SCAN / 'report.json'), independent_report=digest(root / MODELS / 'report.json'),
            evidence=json.loads((root / SCAN / 'prepared.json').read_text())['sha256']['evidence']))
    save(out / 'bank.json', bank)
    print(json.dumps({k: bank[k] for k in ('counts','kind_memberships','discriminator_operands','last_vs_all_operands')},sort_keys=True))


if __name__ == '__main__': main()
