#!/usr/bin/env python3
"""Fixed remaining-center state predictions; no hardware and not frozen.

The old H1641 center pair is excluded on operand identity alone. Other
centers require reviewed instruction/RC/PC/operand provenance: masks and
new prestate fields are NOT used to make an old numerical tuple fresh.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import h1661_normalization_and_c0_proposals as common
import h1689_exact_center_contract as center
import h1657_score_exception_state as raw
import h1657_scorer_preflight as synthetic
from h1640_remaining_scope_freshness import save

LOCKS = {
    center.PROPOSALS: 'c9b28e70b337b3fe3ce2fa75debc8b1c97f5d18168ebc1e1c4eb528bc8d617f1',
    'experiments/h1661_normalization_and_c0_proposals.py': 'f6ef46894be99e7b454a9517673e9965e577e04e9e56eaeba76e9ee4699267aa',
    'experiments/h1689_exact_center_contract.py': '82f1800ef996c3048dc9a16e3f5237beefea991095de6ae525fb31fd0fcdaf01',
    'tmp/ledger33/current/h1689_exact_center_contract/report.json': 'd67d1522c46576b3fd381040d1b84bd627eb48526baf4487f18117aca607a039',
    'experiments/h1657_score_exception_state.py': '40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808',
}


def operands(root):
    prior = json.loads((root / center.PROPOSALS).read_text())
    records = json.loads((root / 'transfer-tests/h1641/manifest.json').read_text())
    excluded = {r['operand'] for r in records if r['exact_center']}
    assert excluded == {'403d fb53d14aa9c2f2c1', 'c03d fb53d14aa9c2f2c1'}
    centers = [r for r in prior['operands'] if any('center' in k for k in r['kinds']) and r['operand'] not in excluded]
    assert len(centers) == 26
    rows = []
    for i, item in enumerate(centers):
        pattern = (5 * i + 3) % 16
        cc = sum(((pattern >> bit) & 1) << position for bit, position in enumerate((8, 9, 10, 14)))
        rows.append(dict(profile=f'CENTER{i:02d}', probe='exact_center',
            kind='direct_center' if 'direct_table_center' in item['kinds'] else 'reduced_center',
            shape='exact_zero_offset', normalization_shift=None, masks=63, cc=cc,
            flags=0, pending=0, depth=1 + i % 8, empty=0, operand=item['operand']))
    return rows


def predictions(root, rows):
    # The existing function runs all four fixed numerical builds and the
    # independent rational graph, then composes the unchanged H1660 model.
    answer = common.predictions(root, rows)
    for i, row in enumerate(answer):
        old = row['case_id']
        row['case_id'] = f'T{i + 1:05d}'
        assert row['capture_line'].startswith(old + ' ')
        row['capture_line'] = row['case_id'] + row['capture_line'][len(old):]
        row['relations'] = 'Fixed exact-center ROM result and full SW; deeper raw registers unchanged. No pending/unmasked fault is requested. Absolute instruction/data pointers are not predicted.'
        assert row['expected']['delivery'] == 'none'
        assert row['expected']['new_exception_flags'] == 0x20
        assert row['expected']['status_known_mask'] == 0xffff
    assert len(answer) == 624
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output_dir.resolve()
    assert not out.exists()
    evidence = dict(common.LOCKS, **LOCKS)
    for name, expected in evidence.items():
        assert raw.digest(root / name) == expected, name
    rows = operands(root)
    predicted = predictions(root, rows)
    # common.predictions initialized the rational constants already. Reuse
    # them without applying the historical S4 correction a second time.
    checks = Counter()
    for row in predicted:
        formula = center.zero_offset(row['operand'], row['instruction'], row['mode'])
        assert (row['expected']['output'], row['expected']['C1']) == (formula['output'], formula['C1'])
        row['center_formula'] = formula
        checks['ROM_identity_checks'] += 1
        fields = synthetic.synthetic(row)
        fields = raw.parse(' '.join(f'{k}={v}' for k, v in fields.items()))
        assert all(raw.inspect(row, fields)['exact'].values())
        checks['synthetic_full_state_rows'] += 1
        for field, value, check in (('A_R0', 'ffff:ffffffffffffffff', 'output'),
                                    ('A_SW', f'{int(fields["A_SW"], 16) ^ 0x100:04x}', 'status'),
                                    ('B_R0', 'ffff:ffffffffffffffff', 'before')):
            changed = dict(fields); changed[field] = value
            assert not raw.inspect(row, changed)['exact'][check]
            checks[check + '_mutations_detected'] += 1
    out.mkdir(parents=True)
    result = dict(experiment='h1692_remaining_center_state_bank',
        capture_state='SOFTWARE_ONLY_NOT_FROZEN', operands=rows, predictions=predicted,
        counts=dict(operands=len(rows), tuples=len(predicted),
                    kinds=dict(Counter(r['kind'] for r in rows)), preflight=dict(checks)),
        excluded_opened_center_operands=2,
        proposed_identity='instruction, RC, PC, raw80 operand; do not use masks/prestates to exempt old tuples. Across prior campaigns, unknown PC reserves all PC.',
        freshness='H1690/H1691 are supporting inventories, not yet a complete frozen reconciliation. Explicitly distinguish software/sibling records from standalone captures; reserve H1641 pair. Re-audit before freeze.',
        hardware_execution='none', private_ledger_access='none', candidate_changed=False,
        paper_default_change=False,
        sha256=dict(script=raw.digest(Path(__file__)), evidence=evidence))
    save(out / 'bank.json', result)
    print(json.dumps(result['counts'], sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
