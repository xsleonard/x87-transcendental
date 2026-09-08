#!/usr/bin/env python3
"""Conservatively audit H1639 proposals without opening hardware labels.

Reject every previously visible significand, including software appearances.
This is stricter than full-tuple freshness and is not a coverage assertion.
Private identities, contents and hashes are never written to this report.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
from h1622_fixed_candidate_challenge_bank_v2 import digest
from h1623_fixed_candidate_freshness import matches

BANK = 'tmp/ledger33/current/h1639_remaining_scope_proposals/bank.json'
BANK_SHA = 'c9b28e70b337b3fe3ce2fa75debc8b1c97f5d18168ebc1e1c4eb528bc8d617f1'
SCANNER_SHA = '392554c2a402eb8b2411f851b6028326d363f21087b7f3b0d0d4791eceb87656'


def save(path, value):
    with path.open('x') as target:
        json.dump(value, target, indent=2, sort_keys=True)
        target.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--private-ledger-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root, private, output = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and not output.exists()
    assert digest(root / BANK) == BANK_SHA
    assert digest(root / 'experiments/h1623_fixed_candidate_freshness.py') == SCANNER_SHA
    bank = json.loads((root / BANK).read_text())
    assert bank['capture_state'] == 'SOFTWARE_ONLY_NOT_FROZEN' and bank['candidate_changed'] is False
    for name, expected in bank['sha256']['evidence'].items():
        assert digest(root / name) == expected, name
    software = (root / BANK).parent
    assert not any(p.name in {'OPENED.json', 'FREEZE.json', 'hardware-output'} for p in software.rglob('*'))
    proposals = bank['operands']
    signatures = {row['operand'].split()[1] for row in proposals}
    output.mkdir(parents=True)
    patterns = output / 'candidate_signatures.txt'
    with patterns.open('x') as target:
        target.write(''.join(s + '\n' for s in sorted(signatures)))
    # Fast rejection against a small, already public software preflight avoids
    # scanning enormous histories for ubiquitous literals. Rejected cases are
    # NOT thereby credited with hardware coverage.
    preflight = root / 'tmp/ledger33/current/h1638_tiny_c_transfer/software_preflight.json'
    assert preflight.is_file()
    pre_hits = matches(preflight, patterns, [])
    remaining = output / 'remaining_signatures.txt'
    with remaining.open('x') as target:
        target.write(''.join(s + '\n' for s in sorted(signatures - pre_hits)))
    excluded = [software, output]
    if private.is_relative_to(root):
        excluded.append(private)
    print('Auditing public history, including compressed files; proposals excluded.', flush=True)
    public_hits = pre_hits | (matches(root, remaining, excluded) if signatures - pre_hits else set())
    print('Public scan complete; auditing private history locally, aggregate results only.', flush=True)
    private_hits = matches(private, patterns, [])
    assert public_hits <= signatures and private_hits <= signatures
    rejected = public_hits | private_hits
    eligible = [row for row in proposals if row['operand'].split()[1] not in rejected]
    report = dict(experiment='h1640_remaining_scope_freshness', state='AUDITED_PROPOSALS_NOT_FROZEN',
        proposed_operands=len(proposals), proposed_significands=len(signatures), eligible_operands=len(eligible),
        eligible_significands=len({r['operand'].split()[1] for r in eligible}),
        eligible_full_tuples=len(eligible) * 2 * 4 * 3, eligible=eligible,
        proposed_kinds=bank['operand_kind_memberships'],
        eligible_kinds=dict(Counter(k for r in eligible for k in r['kinds'])),
        freshness=dict(rejected_public_significands=len(public_hits), rejected_private_significands=len(private_hits),
            rejected_union_significands=len(rejected), public_preflight_rejections=len(pre_hits),
            selected_public_collisions=0, selected_private_collisions=0, compressed_files_searched=True,
            private_files_examined=sum(p.is_file() for p in private.rglob('*')),
            private_identity_contents_or_hashes_published=False,
            software_only_public_directory_exceptions=[str(software.relative_to(root))],
            policy='Reject every previously visible input significand regardless of exponent/instruction/RC/PC/host; stricter than full tuples.'),
        hardware_execution='none', manifest_frozen=False, candidate_changed=False,
        claim_boundary='Eligibility under locally visible history only; revalidate before freeze/execution. Rejection is not hardware coverage. No special/status rule is learned here.',
        sha256=dict(script=digest(Path(__file__)), source_bank=BANK_SHA, scanner=SCANNER_SHA,
            patterns=digest(patterns), remaining_patterns=digest(remaining), preflight=digest(preflight)))
    save(output / 'report.json', report)
    print(json.dumps({k:report[k] for k in ('eligible_operands','eligible_full_tuples','eligible_kinds','freshness')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
