#!/usr/bin/env python3
"""Revalidate, conservatively audit freshness, and freeze H1655 predictions."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import h1655_exception_state_proposals as proposal
from h1623_fixed_candidate_freshness import matches
from h1650_score_masked_state import digest
from h1640_remaining_scope_freshness import save

BANK = 'tmp/ledger33/current/h1655_exception_state_proposals/bank.json'
LOCKS = {
    BANK: 'b67f477ad99d2fdc5e14dc9c4b422d0173e5953eee77f26f81c6176c6ebdb80b',
    'experiments/h1655_exception_state_proposals.py': '97364c89404793fe16d6f17fd8210c2e194eb9d154aa6d79a5bd4e01ae9549cd',
    'experiments/h1623_fixed_candidate_freshness.py': '392554c2a402eb8b2411f851b6028326d363f21087b7f3b0d0d4791eceb87656',
    'tmp/ledger33/current/h1653_exception_transition_audit/report.json': 'c59a590dbda99a9fb445353c6e2f8c24efec6cf313f07eb2e4915b7b1cdad12e',
    'tmp/ledger33/current/h1654_capture_static_audit/report.json': '7a5b0198db87093a708e7c8c513eea63c5cce82e6ddcc0dbf5296c4302689cc7',
    'tmp/ledger33/current/h1657_scorer_preflight/report.json': '0598fd4f826862982257ede5fa2d1513e6eb9e7d4576547e68a0355c2d238af5',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--private-ledger-dir', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, private, out = a.root.resolve(), a.private_ledger_dir.resolve(), a.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    locks = dict(LOCKS)
    for name, sha in locks.items():
        assert digest(root/name) == sha, name
    preflight = json.loads((root/'tmp/ledger33/current/h1657_scorer_preflight/report.json').read_text())
    assert preflight['status'] == 'PASS_SYNTHETIC_ONLY'
    assert preflight['sha256']['scorer'] == digest(root/'experiments/h1657_score_exception_state.py')
    bank = json.loads((root/BANK).read_text())
    assert bank['capture_state'] == 'SOFTWARE_ONLY_NOT_FROZEN' and not bank['candidate_arithmetic_changed']
    for name, sha in bank['sha256']['evidence'].items():
        assert digest(root/name) == sha, name
        locks[name] = sha
    assert proposal.proposals() == bank['operands']
    assert proposal.predictions(root, bank['operands']) == bank['predictions']
    rows = bank['predictions']
    assert len(rows) == len({(r['instruction'], r['mode'], r['pc'], r['operand']) for r in rows}) == 36864
    out.mkdir(parents=True)
    signatures = sorted({r['operand'].split()[1] for r in rows})
    assert len(signatures) == 288
    patterns = out/'candidate_signatures.txt'
    with patterns.open('x') as target:
        target.write(''.join(s+'\n' for s in signatures))
    software = (root/BANK).parent
    assert not any(p.name in {'FREEZE.json', 'OPENED.json', 'hardware-output'} for p in software.rglob('*'))
    excluded = [software, out]
    if private.is_relative_to(root):
        excluded.append(private)
    print('Immutable predictions replayed. Checking compressed public/private history; no labels opened.', flush=True)
    public_hits = matches(root, patterns, excluded)
    private_hits = matches(private, patterns, [])
    assert not public_hits and not private_hits, 'Prior-visible signatures found; no manifest frozen'
    manifest = [dict(r, capture_state='FROZEN_UNOPENED') for r in rows]
    save(out/'manifest.json', manifest)
    with (out/'inputs.txt').open('x') as target:
        target.write(''.join(r['capture_line']+'\n' for r in rows))
    with (out/'run_capture.sh').open('x') as target:
        target.write((root/'experiments/h1656_run_capture.sh').read_text())
    freeze = dict(experiment='h1656_exception_state', capture_state='FROZEN_UNOPENED',
        frozen_utc=datetime.now(timezone.utc).isoformat(), unique_operands=1536, unique_capture_tuples=len(rows),
        expected_counts=bank['counts'], expected_deliveries=bank['deliveries'],
        one_observation_maximum_per_tuple=True, instruction_retries=0, candidate_arithmetic_changed=False,
        identity='Full masks/prestate included; narrower instruction/RC/PC/operand keys are still unique and fresh.',
        hardware_target=dict(host='45.32.204.118', family=6, model=85,
            capture_binary_sha256='1f0be29e0447c4b8390e3edf0b69a78f996d7c2e6293e0588ef7087cb870212e'),
        freshness=dict(selected_public_collisions=0, selected_private_collisions=0,
            compressed_files_searched=True, private_files_examined=sum(p.is_file() for p in private.rglob('*')),
            private_identity_contents_or_hashes_published=False,
            policy='Reject every prior-visible significand regardless of exponent/instruction/RC/PC/host/masks/prestate.',
            software_only_directory_exceptions=[str(software.relative_to(root))]),
        claim_boundary=bank['claim_boundary'],
        sha256=dict(evidence=locks, manifest=digest(out/'manifest.json'), inputs=digest(out/'inputs.txt'),
            runner=digest(out/'run_capture.sh'), freezer=digest(Path(__file__)), patterns=digest(patterns),
            scorer=digest(root/'experiments/h1657_score_exception_state.py')))
    save(out/'FREEZE.json', freeze)
    with (out/'CHECKSUMS.sha256').open('x') as target:
        for name in ('FREEZE.json', 'manifest.json', 'inputs.txt', 'candidate_signatures.txt', 'run_capture.sh'):
            target.write(f'{digest(out/name)}  {name}\n')
    print(json.dumps({k: freeze[k] for k in ('unique_operands', 'unique_capture_tuples', 'expected_counts', 'freshness')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
