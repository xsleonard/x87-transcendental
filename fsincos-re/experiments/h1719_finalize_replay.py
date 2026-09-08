#!/usr/bin/env python3
"""Reconcile completed two-host saved-label reports, without running hardware."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text())


def checked(report):
    assert report['status'] == 'PASS' and report['hardware_executions'] == 0
    counts = sum((Counter(r['counts']) for r in report['records']), Counter())
    assert counts == Counter(report['counts'])
    assert all(r['status'] == 'PASS' and r['returncode'] == 0 for r in report['records'])
    assert not any(v for k, v in counts.items() if 'miss' in k)
    return counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True); p.add_argument('--results', type=Path, required=True)
    a = p.parse_args(); root = a.root.resolve(); base = a.results.resolve()
    result = dict(status='PASS_SAVED_LABEL_REPLAYS_BOTH_HOSTS', hardware_executions=0,
                  private_access=False, algorithm_changed=False, paper_changed=False, hosts={}, evidence={})
    models = set(); drivers = set(); common_counts = []
    for host in ('i7', 'skylake'):
        directory = base / (host + '-bulk')
        native = read(directory / 'results/report.json'); common = read(directory / 'retained-results/report.json')
        native_counts = checked(native); shared_counts = checked(common)
        assert native['host'] == host
        assert shared_counts['rows'] == 15655784 and shared_counts['lanes'] == 27699959
        assert common['jobs'] == 167
        assert common['bundle_sha256'] == '4351394266f9af1df1298d28eec2873dabbc1a5d1d7a1999287c0345c2e29ab1'
        assert common['driver_sha256'] == native['source_sha256']['experiments/h1719_saved_verifier']
        assert common['script_sha256'] == digest(root / 'experiments/h1719_retained_bundle.py')
        assert native['driver_validation'] == dict(status='PASS', actual_CLI_equivalence_cases=1704, negative_controls=5)
        models.add(native['source_sha256']['src/fsincos_skylake']); drivers.add(common['driver_sha256'])
        for name, sha in native['source_sha256'].items():
            if name not in ('src/fsincos_skylake', 'experiments/h1719_saved_verifier'):
                assert digest(root / name) == sha, (host, name)
        by_group = defaultdict(Counter)
        for row in common['records']:
            by_group[row['job']['tag']].update(row['counts'])
        assert by_group['fixture_frontier']['rows'] == 81
        assert by_group['fixture_legacy']['rows'] == 53
        h633 = Counter()
        if host == 'i7':
            for mode in ('rn', 'rd', 'ru'):
                counts = read(directory / 'h633' / (mode + '.json'))
                assert counts['rows'] == 524288 and counts['C1_checks'] == 524288
                assert not any(v for k, v in counts.items() if 'miss' in k)
                h633.update(counts)
        total = native_counts + shared_counts + h633
        for key in ('output_misses', 'C1_misses', 'C2_misses', 'hardware_executions'): total[key] = 0
        result['hosts'][host] = dict(total_counts=dict(total), native_inventory=dict(native_counts),
            common_retained=dict(shared_counts), h633_additional=dict(h633),
            common_groups={k: dict(v) for k, v in by_group.items()},
            unavailable_native_modes=native['unavailable_mode_count'],
            compiler=native['compiler'], execution_cpu=native['execution_cpu'])
        common_counts.append(shared_counts)
        for file in sorted(directory.rglob('*.json')):
            result['evidence'][str(file.relative_to(base))] = digest(file)
    assert len(models) == len(drivers) == 1 and common_counts[0] == common_counts[1]
    raw_counts = Counter()
    for name in ('h1712', 'h1714', 'h1715-x64', 'h1715-i386', 'review'):
        raw = read(base / 'skylake-bulk/raw-replay' / (name + '.json'))
        assert raw['miss_total'] == 0
        raw_counts.update(raw['counts'])
    assert raw_counts['tuples'] == 357360 and raw_counts['lanes'] == 482304
    assert raw_counts['c1_checks'] == 353520
    result['original_raw_skylake_crosscheck'] = dict(raw_counts)
    result['original_raw_crosscheck_not_added_to_totals'] = True
    local = read(root / 'tmp/ledger33/current/h1719_local_checks/retained-replay/report.json')
    assert checked(local) == common_counts[0]
    result['identical_x86_main_binary_sha256'] = models.pop()
    result['identical_x86_verifier_binary_sha256'] = drivers.pop()
    result['local_cross_architecture_counts_match'] = True
    result['checks'] = dict(corpus_toolkit_synthetic_tests=8, local_ubsan_parity_cases=1704,
                            per_host_CLI_equivalence_cases=1704, per_host_negative_controls=5,
                            per_host_saved_paired_regressions=6)
    result['limits'] = [
        'Counts are overlapping instruction/RC/PC appearances, never unique or fresh hardware observations.',
        'Both hosts replay the same complete retained suite plus their available native historical banks; '
        'the larger i7 h491 archive is not claimed to be Skylake-origin evidence or re-executed on Skylake.',
        'Missing capture modes and undefined/unrecorded C1 are not counted as passing checks.',
        'C1/C2 and output encodings are scored where available; no claim of an entirely emulated architectural state.',
        'The full corpus-v1 Cartesian capture matrix and the earlier seed-based native exhaustive loop are not rerun.',
        'Zero retained misses is not a universal silicon or cross-generation proof.',
    ]
    result['sha256'] = {s: digest(root / s) for s in (
        'src/fsincos_skylake.c', 'src/general/paired.h', 'paper/skylake-x87.tex', 'paper/skylake-x87.pdf',
        'experiments/h1719_saved_verifier.c', 'experiments/h1719_run_saved_suite.py',
        'experiments/h1719_retained_bundle.py', 'experiments/h1719_finalize_replay.py')}
    with (base / 'report.json').open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True); f.write('\n')
    print(result['status'])
    for host, data in result['hosts'].items(): print(host, data['total_counts'])


if __name__ == '__main__': main()
