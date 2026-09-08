#!/usr/bin/env python3
"""Freeze the fresh guarded bank; neither H1670 nor unsafe states are executed."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import h1673_guarded_summary_proposals as proposal
import h1674_score_guarded_summary as score
from h1623_fixed_candidate_freshness import matches
from h1640_remaining_scope_freshness import save

BANK = 'tmp/ledger33/current/h1673_guarded_summary_proposals/bank.json'
PREFLIGHT = 'tmp/ledger33/current/h1674_guarded_preflight/report.json'
LOCKS = {
    BANK: '3a7731ab9a7632bfe8d91c26307a63d8a2e17be3d1fefbd69474ca2991448193',
    PREFLIGHT: 'f61dd610f8643111cd2ebe146b84743940b67fbacbdba3fc45e002a999f6a5e4',
    'experiments/h1673_guarded_summary_proposals.py': 'e324d7fe4a3d0390259f2b3c24592478da66b8b84e4b986398e1501156e6c170',
    'experiments/h1674_score_guarded_summary.py': '2b2cc9efd951d286572bdd9d9685f4cc4633b6874c5af1bc6b03f1910175e737',
    'experiments/h1677_independent_guarded_summary.py': '151fef2c4c9dff5d34b271a3c1a12cc24d704c19e6e8cc1c0957cd30cc42c835',
    'tmp/ledger33/current/h1677_guarded_software_preflight/report.json': 'cac7594f3072b7e2900896d38861028157d63b6da5a81c62b9da20510acaef72',
    'experiments/h1669_score_summary_state.py': '7e2bd40c5bc4277f964d332af3cddafe426951c28db08635fc84ca4713b86993',
    'experiments/h1657_score_exception_state.py': '40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808',
    'experiments/h1623_fixed_candidate_freshness.py': '392554c2a402eb8b2411f851b6028326d363f21087b7f3b0d0d4791eceb87656',
}


def coverage(rows):
    return dict(operands=len(rows), kinds=dict(Counter(r['kind'] for r in rows)),
        requested_U_ES_B=dict(Counter(
            f'{int(bool(r["flags"] & ~r["masks"] & 63))}{int(bool(r["summary"] & 128))}{int(bool(r["summary"] & 32768))}'
            for r in rows)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--private-ledger-dir', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args()
    root, private, out = a.root.resolve(), a.private_ledger_dir.resolve(), a.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    digest, locks = score.digest, dict(LOCKS)
    for name, sha in locks.items():
        assert digest(root / name) == sha, name
    bank = json.loads((root / BANK).read_text())
    assert bank['capture_state'] == 'SOFTWARE_ONLY_NOT_FROZEN'
    for name, sha in bank['sha256']['evidence'].items():
        assert digest(root / name) == sha, name
        locks[name] = sha
    assert proposal.proposals() == bank['operands']
    assert proposal.predictions(root, bank['operands']) == bank['predictions']
    preflight = score.preflight(bank['predictions'])
    assert preflight == json.loads((root / PREFLIGHT).read_text())['counts']
    print('Frozen prediction replay and guarded synthetic preflight pass; scanning freshness.', flush=True)
    out.mkdir(parents=True)
    patterns = out / 'candidate_signatures.txt'
    signatures = {r['operand'].split()[1] for r in bank['operands']}
    with patterns.open('x') as target:
        target.write(''.join(s + '\n' for s in sorted(signatures)))
    software = (root / BANK).parent
    assert not any(p.name in {'FREEZE.json', 'OPENED.json', 'hardware-output'} for p in software.rglob('*'))
    excluded = [software, out] + ([private] if private.is_relative_to(root) else [])
    public = matches(root, patterns, excluded)
    hidden = matches(private, patterns, [])
    assert (public | hidden) <= signatures
    eligible = [r for r in bank['operands'] if r['operand'].split()[1] not in public | hidden]
    assert set(coverage(eligible)['requested_U_ES_B']) == {'000', '001', '010', '011', '100', '101', '110', '111'}
    identities = {r['operand'] for r in eligible}
    selected = [dict(r, capture_state='FROZEN_UNOPENED') for r in bank['predictions'] if r['operand'] in identities]
    assert len(selected) == 24 * len(eligible) == len({(r['instruction'], r['mode'], r['pc'], r['operand']) for r in selected})
    save(out / 'manifest.json', selected)
    with (out / 'inputs.txt').open('x') as target:
        target.write(''.join(r['capture_line'] + '\n' for r in selected))
    with (out / 'run_capture.sh').open('x') as target:
        target.write((root / 'experiments/h1675_run_capture.sh').read_text())
    freeze = dict(experiment='h1675_guarded_summary', capture_state='FROZEN_UNOPENED',
        frozen_utc=datetime.now(timezone.utc).isoformat(), unique_operands=len(eligible),
        unique_capture_tuples=len(selected), selected_coverage=coverage(eligible), synthetic_preflight=preflight,
        one_observation_maximum_per_tuple=True, instruction_retries=0, candidate_changed=False,
        hardware_target=dict(host='45.32.204.118', role='Skylake Xeon', family=6, model=85,
            capture_binary_sha256='72d49ae21259b15c2941a19537976221459a731f5dc6d99d90de0e33e30e7bb6'),
        freshness=dict(rejected_public_significands=len(public), rejected_private_significands=len(hidden),
            rejected_union_significands=len(public | hidden), selected_public_collisions=0, selected_private_collisions=0,
            compressed_files_searched=True, private_files_examined=sum(p.is_file() for p in private.rglob('*')),
            private_identity_contents_or_hashes_published=False,
            policy='Reject every prior-visible significand, independently of instruction/control/state/host. Selection is freshness-only; old narrower instruction/RC/PC/operand keys remain unique.',
            software_only_directory_exceptions=[str(software.relative_to(root))]),
        claim_boundary='Identity restoration and ES pending are frozen hypotheses. Actual restored U=0 and nonzero ES/B is BEFORE_ONLY: no opcode/FWAIT, endpoint, status-transition or pending-gate credit. Unknown post-execution summary/delivery stays unpredicted. H1670 remains on hold. No all-input proof or default/paper promotion.',
        sha256=dict(evidence=locks, manifest=digest(out / 'manifest.json'), inputs=digest(out / 'inputs.txt'),
            patterns=digest(patterns), runner=digest(out / 'run_capture.sh'), freezer=digest(Path(__file__)),
            scorer=digest(Path(score.__file__)), independent=digest(root / 'experiments/h1677_independent_guarded_summary.py')))
    save(out / 'FREEZE.json', freeze)
    with (out / 'CHECKSUMS.sha256').open('x') as target:
        for name in ('FREEZE.json', 'manifest.json', 'inputs.txt', 'candidate_signatures.txt', 'run_capture.sh'):
            target.write(f'{digest(out / name)}  {name}\n')
    print(json.dumps({k: freeze[k] for k in ('unique_capture_tuples', 'selected_coverage', 'freshness')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
