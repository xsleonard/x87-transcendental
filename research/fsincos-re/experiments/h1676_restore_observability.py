#!/usr/bin/env python3
"""Audit restore collapse and prove the remaining Boolean identifiability limit.

This is a finite theorem about observed support and candidate functions, not
a universal FXRSTOR theorem or a choice of the physical pending gate.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from h1640_remaining_scope_freshness import save

LOCKS = {
    'transfer-tests/h1675/FREEZE.json': 'd1b53fccfa1f5db61aade4cb982ef46ec992b6bd5889797f473710232af1ac1a',
    'transfer-tests/h1675/manifest.json': '8bb285cf30fbedb107dd34edde1b5435017b0e6b2e48f6a292cdab94a45213f5',
    'transfer-tests/h1675/hardware-output/state-output.txt': '490bded690975f3a50e51e3933a15919f2a54a3808cb29ba13516ea769709a2e',
    'tmp/ledger33/current/h1674_guarded_summary_score/report.json': '08787d5587af4651f4d4d9e80256103583b35fbdf12cc8b4d869baadd4646dfe',
    'tmp/ledger33/current/h1677_independent_guarded_hardware/report.json': '801bf03df87b54acd7db1e8f913524d9a96aae2aad499f7339bcf7f206cde061',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args()
    root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items():
        assert digest(root / name) == sha, name
    kit = root / 'transfer-tests/h1675'
    manifest = json.loads((kit / 'manifest.json').read_text())
    lines = (kit / 'hardware-output/state-output.txt').read_text().splitlines()
    assert len(lines) == len(manifest) == 38016
    categories, stages, actual, kinds = Counter(), Counter(), Counter(), defaultdict(Counter)
    actual_by_request = defaultdict(set)
    summary = Counter()
    for row, line in zip(manifest, lines):
        pairs = [word.split('=') for word in line.split()]
        assert len(pairs) == 62 and all(len(pair) == 2 for pair in pairs)
        f = dict(pairs)
        assert len(f) == 62 and f['CASE'] == row['case_id']
        cw, before, requested = (int(f[k], 16) for k in ('B_CW', 'B_SW', 'REQ_SW'))
        assert cw == row['before_CW'] and requested == row['requested_SW']
        assert (before ^ requested) & 0x7f7f == 0
        u = int(bool(before & ~cw & 63))
        want_index = (u << 2) | (((requested >> 7) & 1) << 1) | ((requested >> 15) & 1)
        actual_index = (u << 2) | (((before >> 7) & 1) << 1) | ((before >> 15) & 1)
        assert actual_index == 7 * u
        actual_by_request[want_index].add(actual_index)
        categories[f'{want_index:03b}->{actual_index:03b}'] += 1
        actual[f'{actual_index:03b}'] += 1
        assert f['ATTEMPTED'] == '1'
        at = int(f['FAULT_AT'])
        assert at in (0, 1, 2) and int(at == 1) == u
        assert int(f['A_VALID']) == int(at != 1)
        stage = {0: 'opcode_completed_no_fault', 1: 'pending_fault_opcode_not_completed',
                 2: 'opcode_completed_fault_at_wait'}[at]
        stages[stage] += 1
        kinds[row['kind']][stage] += 1
        summary['identity_restoration_misses'] += int((before & 0x8080) != row['summary'])
        summary['requested_ES_opcode_prediction_misses'] += int(bool(requested & 128) != (at == 1))
    assert len(actual_by_request) == 8
    assert summary == dict(identity_restoration_misses=28512, requested_ES_opcode_prediction_misses=19008)
    # Enumerate every truth table: only the actual restored state may be an
    # argument to the consuming opcode. Requested off-diagonal states are not
    # evidence about physical off-diagonal execution.
    survivors = [table for table in range(256)
                 if all(((table >> int(index, 2)) & 1) == int(index == '111') for index in actual)]
    assert len(survivors) == 64
    composition = []
    for requested_index in range(8):
        restored, = actual_by_request[requested_index]
        possible = sorted({(table >> restored) & 1 for table in survivors})
        assert possible == [requested_index >> 2]
        composition.append(dict(requested=f'{requested_index:03b}', observed_restored=f'{restored:03b}',
                                all_surviving_composed_gate_values=possible))
    missing = []
    for index in range(1, 7):
        assert {(table >> index) & 1 for table in survivors} == {0, 1}
        missing.append(f'{index:03b}')
    out.mkdir(parents=True)
    save(out / 'composed_truth_table.json', composition)
    report = dict(experiment='h1676_restore_observability', status='PROVED_CAPTURE_SUPPORT_IDENTIFIABILITY_LIMIT',
        rows=len(lines), requested_to_actual_U_ES_B=dict(categories), actual_U_ES_B=dict(actual),
        stages=dict(stages), kinds={k: dict(v) for k, v in kinds.items()}, primary_falsifications=dict(summary),
        new_arithmetic_endpoint_observations=stages['opcode_completed_no_fault'] + stages['opcode_completed_fault_at_wait'],
        unchanged_pending_state_observations=stages['pending_fault_opcode_not_completed'],
        before_only_rows=0, consistent_three_input_Boolean_gates=len(survivors),
        unobserved_consumption_states=missing,
        interpretation='The observed restore/snapshot pipeline maps each requested (U,ES,B) to (U,U,U). All 64 surviving Boolean gates compose to U on all eight requested states. No gate is selected; zero errors of six named actual-state gates do not distinguish them.',
        causal_limit='These captures do not isolate FXRSTOR, snapshot, scheduling or virtualization internals. No universal restoration law or reachability impossibility is proved.',
        next_requirement='A genuinely distinct state-establishment/observation path must first demonstrate off-diagonal actual state, with a non-retrying trap guard. More requests through the same observed collapse do not identify the consuming gate.',
        hardware_execution='none; retained raw audit only', new_hardware_tuples=0, default_or_paper_change='none',
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS, composed_truth_table=digest(out / 'composed_truth_table.json')))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'stages', 'primary_falsifications',
        'new_arithmetic_endpoint_observations', 'consistent_three_input_Boolean_gates')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
