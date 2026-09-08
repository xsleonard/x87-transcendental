#!/usr/bin/env python3
"""Local synthetic recovery tests; no SSH or native x87 execution."""
import gzip
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from h1725_full_campaign import BASE, ROOT, PINS, save, suite
import h1725_dispatch_remote as dispatch
import h1725_resume_full as resume


def main():
    out = Path(tempfile.mkdtemp(prefix='recovery-preflight-', dir=BASE)); checks = 0
    job = out / 'job-000000'; job.mkdir()
    save(job / 'JOB.json', {'identity': 'SYNTHETIC'})
    assert dispatch.state(job)['state'] == 'UNATTEMPTED'; checks += 1
    with patch.object(dispatch.subprocess, 'Popen') as start:
        dispatch.dispatch(out, job, Path('/unused'), Path('/unused'))
        dispatch.dispatch(out, job, Path('/unused'), Path('/unused'))
        assert start.call_count == 1; checks += 1
    assert dispatch.state(job)['state'] == 'IN_FLIGHT_OR_UNCERTAIN_NO_RETRY'; checks += 1
    save(job / 'STARTED.json', {'reserved': True})
    save(job / 'WORKER_EXIT.json', {'returncode': 1})
    assert dispatch.state(job)['state'] == 'FAILED_RESERVED_NO_RETRY'; checks += 1
    with patch.object(dispatch.subprocess, 'Popen') as start:
        dispatch.dispatch(out, job, Path('/unused'), Path('/unused'))
        assert start.call_count == 0; checks += 1
    # Legacy completed jobs can be safely packed and read after their old
    # per-job directory is gone. Every metadata byte is retained in the gzip.
    packed_job = out / 'job-000001'; packed_job.mkdir()
    values = {'JOB.json': {'identity': 'SYNTHETIC'}, 'STARTED.json': {'reserved': True},
              'COMPLETE.json': {'done': True}, 'OFFLOADED.json': {'archived': True}}
    for name, value in values.items():
        save(packed_job / name, value)
    first = dispatch.compact(packed_job); second = dispatch.compact(packed_job)
    assert first == second and not packed_job.exists(); checks += 1
    assert dispatch.state(packed_job)['state'] == 'CAPTURED'; checks += 1
    with patch.object(dispatch.subprocess, 'Popen') as start:
        dispatch.dispatch(out, packed_job, Path('/unused'), Path('/unused'))
        assert start.call_count == 0; checks += 1
    unsafe = out / 'job-000002'; unsafe.mkdir()
    for name, value in values.items():
        save(unsafe / name, value)
    save(unsafe / 'unrelated.json', {'do_not_delete': True})
    try:
        dispatch.compact(unsafe)
    except AssertionError:
        checks += 1
    else:
        raise AssertionError('unknown file was accepted')
    assert (unsafe / 'unrelated.json').exists()
    crash = out / 'job-000003'; crash.mkdir(); save(crash / 'JOB.json', {})
    with patch.object(dispatch.subprocess, 'Popen', side_effect=OSError('synthetic start failure')):
        try:
            dispatch.dispatch(out, crash, Path('/unused'), Path('/unused'))
        except OSError:
            pass
    with patch.object(dispatch.subprocess, 'Popen') as start:
        dispatch.dispatch(out, crash, Path('/unused'), Path('/unused'))
        assert start.call_count == 0; checks += 1
    # The original default parity and hostile scorer/guard suite remains
    # unchanged. Route only its result record to this new test directory.
    import h1725_preflight as original
    original_save = original.save
    def redirected(path, value):
        return original_save(out / 'ORIGINAL_PREFLIGHT.json' if path == BASE / 'PREFLIGHT.json' else path, value)
    with patch.object(original, 'save', side_effect=redirected):
        original.main()
    checks += 1
    # Re-score a previously sealed shard in a scratch view. This exercises
    # the recovery scorer with real labels without executing any hardware.
    source = BASE / 'skylake/jobs/job-000440'
    recovered = out / 'recovered'; recovered.mkdir()
    import os
    for name in ('inputs.txt.gz', 'outputs.txt.gz', 'predictions.json.gz', 'cpu.json', 'COMPLETE.json'):
        os.link(source / name, recovered / name)
    result = resume.score_recoverably(recovered)
    assert result == json.loads((source / 'score.json').read_text()); checks += 1
    assert resume.score_recoverably(recovered) == result; checks += 1
    with patch.object(resume, 'download', side_effect=AssertionError('unnecessary remote download')):
        resume.ensure_download('skylake', source, json.loads((source / 'JOB.json').read_text()))
    checks += 1
    for name, sha in PINS.items():
        assert suite.digest(ROOT / name) == sha
    report = dict(status='PASS', checks=checks, native_hardware_executions=0,
        score_replayed_rows=result['counts']['rows'], source_pins=PINS,
        controller_sha256=suite.digest(ROOT / 'experiments/h1725_resume_full.py'),
        dispatch_sha256=suite.digest(ROOT / 'experiments/h1725_dispatch_remote.py'))
    save(out / 'REPORT.json', report)
    prior = BASE / 'RECOVERY_PREFLIGHT.json'
    if prior.exists():
        import time
        prior.rename(BASE / ('RECOVERY_PREFLIGHT-before-' + str(time.time_ns()) + '.json'))
    save(prior, dict(report, artifact=str(out / 'REPORT.json')))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
