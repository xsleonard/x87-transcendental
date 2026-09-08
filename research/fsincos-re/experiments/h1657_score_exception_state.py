#!/usr/bin/env python3
"""Score frozen H1656 exception-state predictions without modifying them.

Unknown endpoints/bits remain unscored; their alternatives are descriptive.
Fault-context equality failures are distinguished from numerical/state misses.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from h1650_score_masked_state import digest
from h1640_remaining_scope_freshness import save

STATE_FIELDS = ('CW', 'SW', 'TOP', 'FTW', *(f'R{i}' for i in range(8)), 'FOP', 'FIP', 'FDP')


def parse(line):
    pairs = [token.split('=') for token in line.split()]
    assert all(len(p) == 2 for p in pairs)
    fields = {k: v.lower() for k, v in pairs}
    required = {'CASE', 'INSN', 'MODE', 'PC', 'MASKS', 'DEPTH', 'CC', 'FLAGS', 'PENDING', 'EMPTY',
                'A_VALID', 'FAULT', 'FAULT_AT', 'SI_CODE', 'TRAP'}
    required |= {p+'_'+k for p in ('B', 'A', 'F') for k in STATE_FIELDS}
    assert len(fields) == len(pairs) == 60 and set(fields) == required
    for prefix in ('B', 'A', 'F'):
        for name, width in (('CW', 4), ('SW', 4), ('FTW', 2), ('FOP', 4), ('FIP', 16), ('FDP', 16)):
            assert re.fullmatch(f'[0-9a-f]{{{width}}}', fields[prefix+'_'+name])
        assert int(fields[prefix+'_TOP']) == ((int(fields[prefix+'_SW'], 16) >> 11) & 7)
        for i in range(8):
            assert re.fullmatch('[0-9a-f]{4}:[0-9a-f]{16}', fields[f'{prefix}_R{i}'])
    a, f, at = (int(fields[k]) for k in ('A_VALID', 'FAULT', 'FAULT_AT'))
    assert (a, f, at) in ((1, 0, 0), (0, 1, 1), (1, 1, 2))
    return fields


def inspect(row, raw):
    before = {'CASE': row['case_id'].lower(), 'INSN': row['instruction'], 'MODE': row['mode'],
        'PC': f'pc{row["pc"]}', 'MASKS': f'{row["masks"]:02x}', 'DEPTH': str(row['depth']),
        'CC': f'{row["cc"]:04x}', 'FLAGS': f'{row["flags"]:02x}', 'PENDING': str(row['pending']),
        'EMPTY': str(row['empty']), 'B_CW': f'{row["before_CW"]:04x}',
        'B_SW': f'{row["before_SW"]:04x}', 'B_FTW': f'{row["before_FTW"]:02x}',
        'B_R0': row['operand'].replace(' ', ':')}
    for i in range(1, row['depth']):
        before[f'B_R{i}'] = f'3fff:{(1<<63)+8*i:016x}'
    before_errors = [k for k, v in before.items() if raw[k] != v]
    phase_errors = [k for k in ('A_VALID', 'FAULT', 'FAULT_AT', 'TRAP')
                    if int(raw[k]) != row['expected_'+k]]
    selected = 'A' if int(raw['A_VALID']) else 'F'
    value = raw[selected+'_R0']; sw = int(raw[selected+'_SW'], 16)
    expected = row['expected']
    exact = dict(before=not before_errors, delivery=not phase_errors,
        status=((sw ^ expected['status_bits']) & expected['status_known_mask']) == 0,
        CW=raw[selected+'_CW'] == before['B_CW'], TOP=int(raw[selected+'_TOP']) == expected['top'],
        FTW=int(raw[selected+'_FTW'], 16) == expected['physical_abridged_tag'],
        deeper=all(raw[selected+f'_R{i}'] == raw[f'B_R{i}'] for i in range(1, 8)))
    if expected['output'] is not None:
        exact['output'] = value == expected['output']
    relation_errors = []
    if int(raw['FAULT']):
        reference = 'B' if int(raw['FAULT_AT']) == 1 else 'A'
        relation_errors = [k for k in STATE_FIELDS if raw['F_'+k] != raw[reference+'_'+k]]
        exact['fault_snapshot_relation'] = not relation_errors
    return dict(case_id=row['case_id'], kind=row['kind'], operand=row['operand'],
        instruction=row['instruction'], mode=row['mode'], pc=row['pc'], profile=row['profile'],
        masks=row['masks'], expected=expected, actual=raw, selected_snapshot=selected,
        exact=exact, before_errors=before_errors, phase_errors=phase_errors,
        fault_relation_errors=relation_errors,
        status_difference=(sw ^ expected['status_bits']) & expected['status_known_mask'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--mark-opened', action='store_true')
    a = p.parse_args(); kit, out = a.kit.resolve(), a.output_dir.resolve()
    assert not out.exists() and not (a.mark_opened and (kit/'OPENED.json').exists())
    freeze = json.loads((kit/'FREEZE.json').read_text())
    assert freeze['experiment'] == 'h1656_exception_state' and freeze['capture_state'] == 'FROZEN_UNOPENED'
    assert digest(Path(__file__)) == freeze['sha256']['scorer']
    checked = set()
    for line in (kit/'CHECKSUMS.sha256').read_text().splitlines():
        sha, name = line.split(None, 1); path = Path(name.strip())
        assert not path.is_absolute() and '..' not in path.parts and str(path) not in checked
        assert digest(kit/path) == sha; checked.add(str(path))
    assert checked == {'FREEZE.json', 'manifest.json', 'inputs.txt', 'candidate_signatures.txt', 'run_capture.sh'}
    rows = json.loads((kit/'manifest.json').read_text())
    assert len(rows) == freeze['unique_capture_tuples'] == 36864
    assert len({(r['instruction'], r['mode'], r['pc'], r['operand']) for r in rows}) == len(rows)
    assert (kit/'inputs.txt').read_text().splitlines() == [r['capture_line'] for r in rows]
    output = kit/'hardware-output'
    assert (output/'complete-utc.txt').is_file()
    assert (output/'binary.sha256').read_text().split()[0] == freeze['hardware_target']['capture_binary_sha256']
    sha, name = (output/'outputs.sha256').read_text().strip().split(None, 1)
    assert name == 'hardware-output/state-output.txt' and digest(output/'state-output.txt') == sha
    cpu = (output/'cpu-summary.txt').read_text()
    assert re.search(r'vendor_id\s*:\s*GenuineIntel', cpu)
    assert re.search(r'^model\s*:\s*85\s*$', cpu, re.M) and re.search(r'cpu family\s*:\s*6\s*$', cpu, re.M)
    lines = (output/'state-output.txt').read_text().splitlines()
    assert len(lines) == len(rows)
    counts = Counter(); cells = defaultdict(Counter); deliveries = Counter()
    survivors = {}; trials = Counter(); initial_values = defaultdict(set)
    endpoint_survivors = {}; endpoint_trials = Counter()
    scored = []; misses = []; pc_groups = defaultdict(list)
    for row, line in zip(rows, lines):
        raw = parse(line); record = inspect(row, raw); scored.append(record)
        if not all(record['exact'].values()):
            misses.append(record)
        cell = row['profile'][0]+'/'+row['kind']+'/'+row['instruction']
        counts['rows'] += 1; cells[cell]['rows'] += 1
        for name, truth in record['exact'].items():
            counts[name+'_checks'] += 1; counts[name+'_exact'] += truth
            cells[cell][name+'_checks'] += 1; cells[cell][name+'_exact'] += truth
        selected = record['selected_snapshot']; sw = int(raw[selected+'_SW'], 16)
        if row['expected']['status_known_mask'] == 0xffff:
            counts['full_SW_checks'] += 1; counts['full_SW_exact'] += sw == row['expected']['status_bits']
        if row['expected']['output'] is None:
            counts['unpredicted_outputs'] += 1
        deliveries[raw['FAULT_AT']] += 1
        group = row['kind']+'/'+row['instruction']+'/'+row['expected']['delivery']
        for bit, options in row['unmodeled_bit_alternatives'].items():
            key = group+'/'+bit
            valid = {k for k, v in options.items() if v == ((sw >> int(bit)) & 1)}
            survivors[key] = survivors.get(key, set(options)) & valid
            trials[key] += 1; initial_values[key].add((row['before_SW'] >> int(bit)) & 1)
        options = row['unmodeled_output_alternatives']
        if options is not None:
            valid = {k for k, v in options.items() if v == raw[selected+'_R0']}
            endpoint_survivors[group] = endpoint_survivors.get(group, set(options)) & valid
            endpoint_trials[group] += 1
        pc_groups[(row['operand'], row['instruction'], row['mode'])].append(
            (raw[selected+'_R0'], raw[selected+'_SW'], raw[selected+'_FTW'], raw['A_VALID'], raw['FAULT_AT']))
    assert all(len(v) == 3 for v in pc_groups.values())
    out.mkdir(parents=True); save(out/'score.json', scored); save(out/'misses.json', misses)
    result = dict(experiment='h1657_score_exception_state', capture_state='OPENED_ONCE', repeats=0,
        verdict='FROZEN_EXCEPTION_MODEL_SURVIVES' if not misses else 'FROZEN_EXCEPTION_MODEL_FALSIFIED',
        counts=dict(counts), miss_rows=len(misses), cells={k: dict(v) for k, v in cells.items()},
        observed_delivery_sites=dict(deliveries), PC_groups=len(pc_groups),
        PC_differences=sum(len(set(v)) != 1 for v in pc_groups.values()),
        unknown_bit_discriminators={k: dict(survivors=sorted(v), trials=trials[k], initial_values=sorted(initial_values[k])) for k, v in sorted(survivors.items())},
        unknown_output_discriminators={k: dict(survivors=sorted(v), trials=endpoint_trials[k]) for k, v in sorted(endpoint_survivors.items())},
        claim_boundary='Finite frozen fault/state predictions. Unknown outputs/bits are descriptive discriminators, not scored passes. Preserve all failed predictions and distinguish fault-context relations from numerical/model failures. No all-input closure or default/paper promotion.',
        sha256=dict(freeze=digest(kit/'FREEZE.json'), manifest=digest(kit/'manifest.json'), scorer=digest(Path(__file__)),
                    raw_output=sha, score=digest(out/'score.json'), misses=digest(out/'misses.json'),
                    raw_metadata={p.name: digest(p) for p in output.iterdir() if p.is_file() and p.name != 'state-output.txt'}))
    save(out/'report.json', result)
    if a.mark_opened:
        save(kit/'OPENED.json', dict(experiment=freeze['experiment'], capture_state='OPENED_ONCE', repeats=0,
            verdict=result['verdict'], counts=dict(counts), miss_rows=len(misses),
            report_sha256=digest(out/'report.json'), freeze_sha256=result['sha256']['freeze'],
            candidate_changed=False, paper_change='none'))
    print(json.dumps({k: result[k] for k in ('verdict', 'counts', 'miss_rows', 'observed_delivery_sites', 'PC_differences', 'unknown_output_discriminators')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
