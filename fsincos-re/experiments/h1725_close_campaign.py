#!/usr/bin/env python3
"""Assemble the final two-host result from completed native/portable audits."""
import collections
import json
import time
from h1725_full_campaign import BASE, HOSTS, suite, save


def main():
    hosts = {}; totals = collections.Counter(); shard_count = 0; model_pins = None
    for host in HOSTS:
        out = BASE / host; closure = out / 'native-completion-20260907'
        native = json.loads((closure / 'REPORT.json').read_text())
        portable = json.loads((out / 'PORTABLE-COMPLETE.json').read_text())
        cfg = json.loads((closure / 'CUTOVER.json').read_text())
        index = json.loads((out / 'PORTABLE-INDEX.json').read_text())
        assert native['status'] == 'NATIVE_SELECTED_RUN_RECONCILED_PASS'
        assert portable['status'] == 'SELECTED_NATIVE_AND_PORTABLE_RECONCILED_PASS'
        assert portable['native_completion_report_sha256'] == suite.digest(closure / 'REPORT.json')
        assert portable['portable_index_sha256'] == suite.digest(out / 'PORTABLE-INDEX.json')
        assert native['totals']['rows'] == portable['rows'] == index['rows'] == cfg['selected_cases']
        assert sum(x['rows'] for x in index['shards']) == index['rows']
        assert len(index['shards']) == native['total_shards'] == portable['shards']
        assert native['selection_counts'] == portable['selection_counts'] == cfg['selection_counts']
        assert not any(v for k, v in native['totals'].items() if k.endswith('_misses'))
        if model_pins is None:
            model_pins = cfg['algorithm_pins']
        assert cfg['algorithm_pins'] == model_pins
        totals.update(native['totals']); shard_count += portable['shards']
        hosts[host] = dict(address=HOSTS[host], selected_observations=portable['rows'],
            shards=portable['shards'], totals=native['totals'], cpu_context_id=cfg['cpu_context_id'],
            reported_cpu=json.loads((out / 'jobs/job-000000/cpu.json').read_text())['context'],
            native_completed_unix=native['completed_unix'], portable_completed_unix=portable['completed_unix'],
            selection_counts=native['selection_counts'], full_matrix_complete=False,
            native_report=str((closure / 'REPORT.json').relative_to(BASE)),
            portable_report=str((out / 'PORTABLE-COMPLETE.json').relative_to(BASE)),
            portable_index=str((out / 'PORTABLE-INDEX.json').relative_to(BASE)),
            portable_report_sha256=suite.digest(out / 'PORTABLE-COMPLETE.json'))
    assert totals['rows'] == 705480464 and shard_count == 14690
    report = dict(status='TWO_HOST_SELECTED_NATIVE_AND_PORTABLE_PASS', campaign='H1725',
        total_selected_observations=totals['rows'], total_shards=shard_count, totals=dict(totals),
        numerical_lane_checks=totals['output_checks']+totals['sine_checks']+totals['cosine_checks'],
        instructions=['fsin','fcos','fsincos'], rounding_modes=['rn','rd','ru','rz'], precision_control=64,
        model_pins=model_pins, hosts=hosts, full_matrix_complete=False,
        no_native_repeats=True, algorithm_changed=False, paper_changed=False,
        completed_unix=time.time(),
        limits='Finite frozen selected-corpus verification on two reported CPU contexts, not a universal proof. Historical exclusions and held cases are not new passes. Counts are per-host observations, not distinct inputs across hosts. Only index-listed observation datasets are portable export material.')
    save(BASE / 'FINAL-REPORT.json', report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
