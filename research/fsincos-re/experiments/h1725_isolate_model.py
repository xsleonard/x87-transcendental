#!/usr/bin/env python3
"""Retain the original H1725 model and test orchestration isolation locally.

No SSH, native x87 capture, live-source modification, or reservation changes.
Existing artifacts are never replaced. Run once for this recovery.
"""
import difflib
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from h1725_full_campaign import BASE, ROOT, PINS, save, suite
import h1725_preflight as original
import h1725_recovery_preflight as recovery
import h1725_resume_full as resume


def main():
    out = Path(tempfile.mkdtemp(prefix='model-isolation-', dir=BASE))
    frozen = BASE / 'frozen-model'
    assert not frozen.exists(), 'Preserve/review existing snapshot; do not overwrite it'
    preflight = json.loads((BASE / 'PREFLIGHT.json').read_text())
    campaign = json.loads((BASE / 'CAMPAIGN.json').read_text())
    assert campaign['model_pins'] == preflight['source_pins'] == PINS
    assert suite.digest(BASE / 'predictor') == preflight['predictor_sha256']
    baseline = ROOT / 'tmp/verification-expansion/f2xm1/baseline'
    archive_pins = json.loads((baseline.parent / 'SOURCE-PINS.json').read_text())
    files = {n: s for n, s in archive_pins.items() if n.startswith(('src/', 'data/'))}
    assert all(files[n] == s for n, s in PINS.items())
    for name, sha in files.items():
        assert suite.digest(baseline / name) == sha, name

    # Confirm the complete live-C delta is confined to the new F2XM1 helper
    # and its F2XM1-only call. No broad claim about shared-code equivalence.
    old = (baseline / 'src/fsincos_skylake.c').read_text()
    live = (ROOT / 'src/fsincos_skylake.c').read_text()
    start = live.index('/* Round the exact tiny-path product once at the raw80 spacing.')
    end = live.index('/* reconstructed six-coefficient table polynomial. */', start)
    assert 'static sf_t f2xm1_tiny_raw80(' in live[start:end]
    call = '    if (x.exp <= -16382) return f2xm1_tiny_raw80(x, rc);\n'
    assert live.count(call) == 1
    assert (live[:start] + live[end:]).replace(call, '', 1) == old
    for name, sha in PINS.items():
        if name != 'src/fsincos_skylake.c':
            assert suite.digest(ROOT / name) == sha
    live_sha = suite.digest(ROOT / 'src/fsincos_skylake.c')
    diff = ''.join(difflib.unified_diff(old.splitlines(True), live.splitlines(True),
                                     fromfile='frozen-original', tofile='live-f2xm1-only'))
    with (out / 'source-change.diff').open('x') as f:
        f.write(diff)

    frozen.mkdir()
    for name, sha in files.items():
        target = frozen / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(baseline / name, target)
        assert suite.digest(target) == sha
    # A self-contained old CLI lets the unchanged original preflight run
    # against the original model, even as the editable worktree evolves.
    for name, sha in preflight['files'].items():
        assert suite.digest(ROOT / 'experiments' / name) == sha
        target = frozen / 'experiments' / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'experiments' / name, target)
        files['experiments/' + name] = sha
    subprocess.run(['cc', '-O2', '-o', str(frozen / 'src/fsincos_skylake'),
                    str(frozen / 'src/fsincos_skylake.c'), '-lm'], check=True)
    files['src/fsincos_skylake'] = suite.digest(frozen / 'src/fsincos_skylake')
    save(frozen / 'MANIFEST.json', dict(status='ORIGINAL_H1725_MODEL_ISOLATED',
         source_pins=PINS, predictor_sha256=preflight['predictor_sha256'], files=files,
         source_snapshot_origin=str(baseline), executable_rebuilt=False,
         note='The campaign predictor is NOT rebuilt. Only a test CLI was built.'))
    resume.verify_execution_model(preflight)

    checks = []
    # The live-source root may change without affecting this frozen artifact.
    with patch.object(resume, 'ROOT', out / 'unrelated-editable-worktree'):
        resume.verify_execution_model(preflight)
    checks.append('editable_worktree_not_an_execution_dependency')
    actual_digest = suite.digest
    for changed in (BASE / 'predictor', frozen / 'src/fsincos_skylake.c',
                    frozen / 'src/general/paired.h'):
        def altered(path, changed=changed):
            return '0' * 64 if Path(path) == changed else actual_digest(path)
        with patch.object(suite, 'digest', side_effect=altered):
            try:
                resume.verify_execution_model(preflight)
            except AssertionError:
                checks.append('reject_changed:' + str(changed.relative_to(BASE)))
            else:
                raise AssertionError('altered frozen artifact accepted')
    bad = dict(preflight, predictor_sha256='0' * 64)
    try:
        resume.verify_execution_model(bad)
    except AssertionError:
        checks.append('reject_changed_predictor_pin')
    else:
        raise AssertionError('altered predictor pin accepted')

    # Reuse the full local recovery/scorer/reservation tests, redirecting
    # original-model reads to the frozen view. Preserve every older report.
    with patch.object(original, 'ROOT', frozen), patch.object(recovery, 'ROOT', frozen):
        # recovery records the controller/helper hashes from this view.
        for name in ('h1725_resume_full.py', 'h1725_dispatch_remote.py'):
            shutil.copyfile(ROOT / 'experiments' / name, frozen / 'experiments' / name)
        recovery.main()
    checks.append('full_recovery_and_original_preflight_pass')
    resume.verify_execution_model(preflight)
    assert suite.digest(ROOT / 'src/fsincos_skylake.c') == live_sha
    report = dict(status='PASS', hardware_executions=0, checks=checks,
        source_change='F2XM1 helper and F2XM1-only call; remaining C byte-identical',
        live_c_sha256=live_sha, frozen_c_sha256=PINS['src/fsincos_skylake.c'],
        predictor_sha256=preflight['predictor_sha256'],
        frozen_manifest_sha256=suite.digest(frozen / 'MANIFEST.json'),
        controller_sha256=suite.digest(ROOT / 'experiments/h1725_resume_full.py'),
        recovery_preflight_sha256=suite.digest(BASE / 'RECOVERY_PREFLIGHT.json'))
    save(out / 'REPORT.json', report)
    print(json.dumps(dict(report, artifact=str(out / 'REPORT.json')), indent=2))


if __name__ == '__main__':
    main()
