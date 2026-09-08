#!/usr/bin/env python3
"""Read-only timing analysis of existing H1725 receipts; no captures or SSH.

Optional output is a new report only. Never modify an existing receipt.
Capture time includes validation/compression and is not a pure FPU benchmark.
"""
import argparse
import datetime
import json
import math
import statistics
from pathlib import Path

from h1725_full_campaign import BASE, save


def profile(host, since, limit):
    stages = {}; completed = []
    for line in (BASE / host / 'launchd.stdout.log').read_text().splitlines():
        if not line.startswith('{'):
            continue
        row = json.loads(line)
        if 'job' not in row or row['updated_unix'] < since:
            continue
        key = (row['pid'], row['job'])
        stages.setdefault(key, {})[row['stage']] = row['updated_unix']
        if row['stage'] == 'RUNNING':
            completed.append((key, row))
    samples = []
    for (pid, name), row in completed[-limit:]:
        stage = stages[pid, name]
        previous = stages.get((pid, f'job-{int(name[4:]) - 1:06d}'), {})
        if not all(s in stage for s in ('CAPTURING', 'DOWNLOADING_AND_SCORING', 'RUNNING')):
            continue
        if 'RUNNING' not in previous:
            continue
        job = BASE / host / 'jobs' / name
        if not (job / 'DONE.json').exists():
            continue
        start = json.loads((job / 'STARTED.json').read_text())
        complete = json.loads((job / 'COMPLETE.json').read_text())
        done = json.loads((job / 'DONE.json').read_text())
        assert done['status'] == 'PASS'
        assert not any(v for k, v in done['totals'].items() if k.endswith('_misses'))
        duration = (datetime.datetime.fromisoformat(complete['completed'])
                    - datetime.datetime.fromisoformat(start['time'])).total_seconds()
        samples.append(dict(job=name, pid=pid, rows=complete['rows'],
            total_seconds=stage['RUNNING'] - previous['RUNNING'],
            prep_upload_seconds=stage['CAPTURING'] - previous['RUNNING'],
            capture_poll_seconds=stage['DOWNLOADING_AND_SCORING'] - stage['CAPTURING'],
            download_score_ack_seconds=stage['RUNNING'] - stage['DOWNLOADING_AND_SCORING'],
            remote_capture_validate_compress_seconds=duration,
            cumulative_rows=done['totals']['rows'], completed_unix=stage['RUNNING']))
    if not samples:
        return dict(host=host, complete_samples=0)
    last = samples[-1]
    selected = json.loads((BASE / host / 'SELECTION.json').read_text())['counts']['selected_cases']
    total_shards = math.ceil((BASE / host / 'selected.bin').stat().st_size / 100000)
    fields = ('rows', 'total_seconds', 'prep_upload_seconds', 'capture_poll_seconds',
              'download_score_ack_seconds', 'remote_capture_validate_compress_seconds')
    mean = {k: statistics.mean(s[k] for s in samples) for k in fields}
    return dict(host=host, complete_samples=len(samples), first=samples[0]['job'],
        last=last['job'], pid=last['pid'], means=mean,
        measured_cases_per_second=mean['rows'] / mean['total_seconds'],
        remaining_hours_by_cases=(selected - last['cumulative_rows'])
            / (mean['rows'] / mean['total_seconds']) / 3600,
        remaining_hours_by_shards=(total_shards - int(last['job'][4:]) - 1)
            * mean['total_seconds'] / 3600,
        samples=samples)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--since', type=float, default=1788798000)
    parser.add_argument('--last', type=int, default=60)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = dict(hardware_executed=False, since=args.since,
                  hosts={h: profile(h, args.since, args.last) for h in ('i7', 'skylake')})
    if args.out:
        save(args.out, result)
    print(json.dumps({**result, 'hosts': {h: {k: v for k, v in r.items() if k != 'samples'}
                                        for h, r in result['hosts'].items()}}, indent=2))
