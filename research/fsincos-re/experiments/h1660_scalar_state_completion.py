#!/usr/bin/env python3
"""Default-off staged-state completion to challenge on fresh inputs.

The invalid C0=0 prediction is deliberately new. H1656 could not distinguish
preserve from set on that path. Zero/infinity and unsupported control states
retain the prior explicit limits; nothing is promoted into the emulator.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
import h1652_exception_transition as prior
import h1659_wrapped_underflow as underflow
from h1650_score_masked_state import digest
from h1640_remaining_scope_freshness import save

LOCKS = dict(underflow.LOCKS, **{
    'experiments/h1659_wrapped_underflow.py': 'e80ed534a8b1300fe68c6f6e8c9be0fb569797311e4534ebca4f63bb6046b004',
    'tmp/ledger33/current/h1659_wrapped_underflow/report.json': '5f4df6828352e787f5f5e5814c2d659d2466ce8c093f92dc3dffd5521f638a04',
})


def complete(result, se, sig, *, before_status, enabled=False):
    if not enabled:
        return result
    result = underflow.complete_underflow(result, se, sig, before_status=before_status, enabled=True)
    if result.delivery == 'at_next_wait' and result.new_exception_flags in (1, 2) and result.encoding_class != 'infinity':
        # Hypothesis for the previously ambiguous invalid C0: preserve C0/C3,
        # clear C1/C2 before setting outcome bits, independent of raw payload.
        return replace(result, C1=0, C2=0, status_bits=result.status_bits | (before_status & 0x4100),
                       status_known_mask=0xffff)
    return result


def transition(se, sig, instruction, *, enabled=False, **kwargs):
    result = prior.transition(se, sig, instruction, experimental_condition_mask=enabled, **kwargs)
    return complete(result, se, sig, before_status=kwargs.get('before_status', 0x3800), enabled=enabled)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items():
        assert digest(root/name) == sha, name
    rows = json.loads((root/'transfer-tests/h1656/manifest.json').read_text())
    lines = (root/'transfer-tests/h1656/hardware-output/state-output.txt').read_text().splitlines()
    assert len(rows) == len(lines) == 36864
    counts = Counter()
    for row, line in zip(rows, lines):
        raw = dict(w.lower().split('=') for w in line.split())
        se, sig = (int(w, 16) for w in row['operand'].split())
        original = prior.Transition(**row['expected'])
        assert complete(original, se, sig, before_status=row['before_SW']) == original
        counts['disabled_identity_checks'] += 1
        result = complete(original, se, sig, before_status=row['before_SW'], enabled=True)
        selected = 'a' if int(raw['a_valid']) else 'f'
        assert result.output == raw[selected+'_r0'] and result.status_bits == int(raw[selected+'_sw'], 16)
        assert result.status_known_mask == 0xffff
        counts['retrospective_output_full_SW_checks'] += 1
    out.mkdir(parents=True)
    report = dict(experiment='h1660_scalar_state_completion', status='PASS_RETROSPECTIVE_ONLY', counts=dict(counts),
        hardware_execution='none', private_ledger_access='none', production_or_paper_change='none',
        claim_boundary='Default-off completion. Existing invalid C0=1 rows cannot validate the new C0=0 prediction. Underflow scaling has only shifts1/2 observed. No all-input silicon or full-control closure.',
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS))
    save(out/'report.json', report)
    print(json.dumps(dict(status=report['status'], counts=dict(counts)), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
