#!/usr/bin/env python3
"""Prove finite masked center-key coverage without counting sibling records.

The exact external-center universe is H1639's model enumeration. H1641's old
48 rows provide output/C1/flags, not the new full-prestate coverage of H1694.
No new hardware, transfer assumption, default or paper promotion.
"""
import argparse
import json
from collections import Counter
from itertools import product
from pathlib import Path
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest

BASE = 'tmp/ledger33/current/'
LOCKS = {
    BASE + 'h1639_remaining_scope_proposals/bank.json': 'c9b28e70b337b3fe3ce2fa75debc8b1c97f5d18168ebc1e1c4eb528bc8d617f1',
    BASE + 'h1689_exact_center_contract/report.json': 'd67d1522c46576b3fd381040d1b84bd627eb48526baf4487f18117aca607a039',
    BASE + 'h1694_center_state_score/report.json': '64e1b6101e80971caeb8931f43e933baf6a0887e9b6b8b96b070c67680b48422',
    'transfer-tests/h1694/FREEZE.json': '2ae03aea2ed62ce06be21d45b7201dd28d472b7686e001c449366bffd18d22ed',
    'transfer-tests/h1694/manifest.json': '50f3b34b71647649e09d210d1aea294195bd49293823a785874133e96d5c0247',
    'transfer-tests/h1694/OPENED.json': '74ac5c9a09c8946158ad3638d0ad0aea224069e83852907e4c6ab1f5a5cda6b9',
    'transfer-tests/h1694/hardware-output/state-output.txt': '9e43ee3840f7312d780f7dc50648c0cc20ef875c7b9c9d837a267c9ea4e2a57b',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); root, out = args.root.resolve(), args.output_dir.resolve()
    assert not out.exists()
    for name, expected in LOCKS.items():
        assert digest(root / name) == expected, name
    bank = json.loads((root / BASE / 'h1639_remaining_scope_proposals/bank.json').read_text())
    centers = {r['operand']: r for r in bank['operands'] if any('center' in k for k in r['kinds'])}
    universe = set(product(('fsin', 'fcos'), ('rn', 'rd', 'ru', 'rz'), (24, 53, 64), centers))
    assert len(centers) == 28 and len(universe) == 672
    old_report = json.loads((root / BASE / 'h1689_exact_center_contract/report.json').read_text())
    old_path = root / BASE / 'h1689_exact_center_contract/standalone_retained_checks.json'
    assert digest(old_path) == old_report['sha256']['artifacts'][old_path.name]
    new_report = json.loads((root / BASE / 'h1694_center_state_score/report.json').read_text())
    assert new_report['status'] == 'FROZEN_CENTER_PREDICTIONS_PASS' and new_report['miss_rows'] == 0
    new_path = root / BASE / 'h1694_center_state_score/score.json'
    assert digest(new_path) == new_report['sha256']['score']
    rows, keys, old_keys, new_keys = [], set(), set(), set()
    for row in json.loads(old_path.read_text()):
        key = (row['instruction'], row['mode'], row['precision_control'], row['operand'])
        assert key in universe and key not in keys
        keys.add(key); old_keys.add(key)
        sw = int(row['SW'], 16)
        assert (sw >> 9) & 1 == row['C1'] and sw & 63 == 32
        rows.append(dict(key=list(key), origin='H1641', output=row['output'], C1=row['C1'],
            exception_flags=sw & 63, full_prestate_and_full_SW_credit=False,
            center=row['b'], direct=False))
    for row in json.loads(new_path.read_text()):
        key = (row['instruction'], row['mode'], row['pc'], row['operand'])
        assert key in universe and key not in keys
        keys.add(key); new_keys.add(key)
        assert all(row['exact'].values()) and row['exact'] == row['independent_exact']
        expected, actual = row['independent_expected'], row['actual']
        assert actual['A_R0'] == expected['output'] and int(actual['A_SW'], 16) == expected['status_bits']
        rows.append(dict(key=list(key), origin='H1694', output=actual['A_R0'], C1=expected['C1'],
            exception_flags=expected['new_exception_flags'], full_prestate_and_full_SW_credit=True,
            center=row['center'], direct='direct_table_center' in centers[row['operand']]['kinds']))
    assert len(old_keys) == 48 and len(new_keys) == 624 and not old_keys & new_keys
    assert keys == universe
    by_center = Counter(str(r['center']) for r in rows)
    by_route = Counter('direct' if r['direct'] else 'reduced' for r in rows)
    assert by_route == dict(direct=288, reduced=384)
    out.mkdir(parents=True); save(out / 'coverage.json', sorted(rows, key=lambda r: r['key']))
    report = dict(experiment='h1695_exact_center_coverage_union',
        status='COMPLETE_FINITE_MASKED_MODEL_CENTER_KEY_COVERAGE',
        center_operands=28, key_universe=672, old_rows=48, fresh_rows=624,
        overlap=0, missing_keys=0, output_C1_exception_flag_passes=672,
        full_prestate_full_SW_fresh_passes=624, by_center=dict(by_center), by_route=dict(by_route),
        scope='Every external exact-center operand in the fixed M66 enumeration, FSIN/FCOS, RN/RD/RU/RZ, PC24/53/64, masked exceptions at the tested prestates. This is exhaustive for that finite key universe, not all external inputs, arbitrary histories/controls, or proof that silicon has no additional center preimages.',
        sibling_instruction_credit=0, hardware_execution='none', candidate_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS,
            old_rows=digest(old_path), fresh_rows=digest(new_path), coverage=digest(out / 'coverage.json')))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'key_universe', 'overlap', 'missing_keys', 'by_center', 'by_route')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
