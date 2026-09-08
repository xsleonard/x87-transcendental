#!/usr/bin/env python3
"""Synthetic parser/scorer mutation tests before the H1656 hardware freeze."""
import argparse
import json
from collections import Counter
from pathlib import Path
import h1657_score_exception_state as score
from h1640_remaining_scope_freshness import save

BANK = 'tmp/ledger33/current/h1655_exception_state_proposals/bank.json'
BANK_SHA = 'b67f477ad99d2fdc5e14dc9c4b422d0173e5953eee77f26f81c6176c6ebdb80b'


def synthetic(row):
    fields = dict(CASE=row['case_id'].lower(), INSN=row['instruction'], MODE=row['mode'], PC=f'pc{row["pc"]}',
        MASKS=f'{row["masks"]:02x}', DEPTH=str(row['depth']), CC=f'{row["cc"]:04x}', FLAGS=f'{row["flags"]:02x}',
        PENDING=str(row['pending']), EMPTY=str(row['empty']), SI_CODE='0')
    for name in ('A_VALID', 'FAULT', 'FAULT_AT', 'TRAP'):
        fields[name] = str(row['expected_'+name])
    for prefix in ('B', 'A', 'F'):
        for name in score.STATE_FIELDS:
            width = 16 if name in ('FIP', 'FDP') else 2 if name == 'FTW' else 1 if name == 'TOP' else 4
            fields[prefix+'_'+name] = '0000:0000000000000000' if name.startswith('R') else '0'*width
    fields.update(B_CW=f'{row["before_CW"]:04x}', B_SW=f'{row["before_SW"]:04x}',
                  B_FTW=f'{row["before_FTW"]:02x}', B_TOP=str((row['before_SW']>>11)&7),
                  B_R0=row['operand'].replace(' ', ':'), B_FOP='0123', B_FIP='0000000000004567', B_FDP='00000000000089ab')
    for i in range(1, row['depth']):
        fields[f'B_R{i}'] = f'3fff:{(1<<63)+8*i:016x}'
    if row['expected_A_VALID']:
        for name in score.STATE_FIELDS:
            fields['A_'+name] = fields['B_'+name]
        expected = row['expected']
        fields.update(A_SW=f'{expected["status_bits"]:04x}', A_FTW=f'{expected["physical_abridged_tag"]:02x}',
                      A_TOP=str(expected['top']), A_R0=expected['output'] or '0000:0000000000000000')
    if row['expected_FAULT']:
        reference = 'B' if row['expected_FAULT_AT'] == 1 else 'A'
        for name in score.STATE_FIELDS:
            fields['F_'+name] = fields[reference+'_'+name]
    return fields


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists() and score.digest(root/BANK) == BANK_SHA
    rows = json.loads((root/BANK).read_text())['predictions']; counts = Counter()
    for row in rows:
        raw = synthetic(row)
        raw = score.parse(' '.join(f'{k}={v}' for k, v in raw.items()))
        result = score.inspect(row, raw)
        assert all(result['exact'].values())
        counts['synthetic_positive_rows'] += 1
        selected = result['selected_snapshot']
        changed = dict(raw)
        changed[selected+'_SW'] = f'{int(raw[selected+"_SW"],16)^1:04x}'
        assert not score.inspect(row, changed)['exact']['status']
        counts['known_status_mutation_detected'] += 1
        changed = dict(raw); changed['B_R0'] = 'ffff:ffffffffffffffff'
        assert not score.inspect(row, changed)['exact']['before']
        counts['prestate_mutation_detected'] += 1
        changed = dict(raw); changed[selected+'_R0'] = 'ffff:fffffffffffffff0'
        mutated = score.inspect(row, changed)
        if row['expected']['output'] is None:
            assert 'output' not in mutated['exact']
            counts['unknown_output_not_credited'] += 1
        else:
            assert not mutated['exact']['output']
            counts['known_output_mutation_detected'] += 1
        if row['expected_FAULT']:
            changed = dict(raw); changed['F_FIP'] = '000000000000eeee'
            assert not score.inspect(row, changed)['exact']['fault_snapshot_relation']
            counts['fault_context_mutation_detected'] += 1
        unknown = (~row['expected']['status_known_mask']) & 0xffff
        if unknown:
            bit = unknown & -unknown
            changed = dict(raw)
            changed[selected+'_SW'] = f'{int(raw[selected+"_SW"],16)^bit:04x}'
            if row['expected_FAULT_AT'] == 2:
                changed['F_SW'] = changed['A_SW']
            assert all(score.inspect(row, changed)['exact'].values())
            counts['unknown_status_not_credited'] += 1
    for line in ('CASE=x CASE=y', 'not-an-assignment', 'A_VALID=0 FAULT=0 FAULT_AT=0'):
        try:
            score.parse(line)
        except AssertionError:
            counts['malformed_rejections'] += 1
        else:
            raise AssertionError('Malformed snapshot accepted')
    out.mkdir(parents=True)
    report = dict(experiment='h1657_scorer_preflight', status='PASS_SYNTHETIC_ONLY', counts=dict(counts),
        hardware_execution='none', private_ledger_access='none',
        claim_boundary='Synthetic parser/scorer tests; no numerical or state silicon evidence. Unknown fields receive no predicted-pass credit.',
        sha256=dict(bank=BANK_SHA, script=score.digest(Path(__file__)), scorer=score.digest(root/'experiments/h1657_score_exception_state.py')))
    save(out/'report.json', report)
    print(json.dumps(dict(status=report['status'], counts=dict(counts)), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
