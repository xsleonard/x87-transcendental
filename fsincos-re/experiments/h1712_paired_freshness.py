#!/usr/bin/env python3
"""Conservative local public/private freshness audit; never open hardware labels.

Only aggregate private findings are serialized. Public significand rejection
is deliberately stricter than instruction/RC/PC/operand tuple novelty.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
import h1691_private_center_representation_audit as private_audit
from h1623_fixed_candidate_freshness import matches
from h1709_paired_retained_census import digest, save

BANK = 'tmp/ledger33/current/h1711_paired_challenge_bank/bank.json'
SOFTWARE = ('tmp/ledger33/current/h1711_paired_discriminator_scan',
            'tmp/ledger33/current/h1711_paired_challenge_bank')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path); p.add_argument('--private-ledger-dir', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root = a.root.resolve(); private = a.private_ledger_dir.resolve(); out = a.output_dir.resolve()
    assert private.is_dir() and private.is_relative_to(root) and not out.exists()
    bank = json.loads((root / BANK).read_text())
    assert bank['capture_state'] == 'SOFTWARE_ONLY_NOT_FROZEN' and not bank['manifest_frozen']
    for name, sha in bank['sha256']['evidence'].items(): assert digest(root / name) == sha, name
    for name in SOFTWARE:
        assert not any(p.name in {'FREEZE.json', 'OPENED.json', 'hardware-output'} for p in (root / name).rglob('*'))
    rows = bank['operands']; signatures = {r['operand'].split()[1] for r in rows}
    out.mkdir(parents=True); patterns = out / 'candidate_signatures.txt'
    with patterns.open('x') as stream: stream.write(''.join(s+'\n' for s in sorted(signatures)))
    print('Public local history audit, including compressed text; excluding only declared software proposals.', flush=True)
    public = matches(root, patterns, [private, out, *(root / name for name in SOFTWARE)])
    eligible = [r for r in rows if r['operand'].split()[1] not in public]
    print('Public scan completed; private local checks return aggregate findings only.', flush=True)
    private_signatures = matches(private, patterns, [])
    targets = {r['operand'] for r in eligible}
    assert targets
    hidden, positive = private_audit.inspect(private, targets)
    # Fail closed for any private possible match; never emit private membership.
    clean = not private_signatures and not positive and not hidden['numeric_parse_failures'] and not hidden['long_numeric_tokens_unparsed']
    report = dict(experiment='h1712_paired_freshness', status='AUDITED_NOT_FROZEN' if clean else 'PRIVATE_AUDIT_UNRESOLVED',
        proposed_operands=len(rows), rejected_public_significands=len(public),
        private_matching_significand_count=len(private_signatures), private_possible_representation_occurrences=positive,
        private_counts=dict(hidden), private_identities_contents_hashes_membership_lists_published=False,
        eligible=eligible if clean else [], eligible_operands=len(eligible) if clean else 0,
        eligible_discriminator_operands=sum(bool(r['discriminator_modes']) for r in eligible) if clean else 0,
        eligible_kinds=dict(Counter(k for r in eligible for k in r['kinds'])) if clean else {},
        software_directory_exceptions=list(SOFTWARE), hardware_execution='none', manifest_frozen=False,
        policy='Exclude all previously visible significands regardless of exponent/instruction/mode/precision/host. Private possible matches stop clearance. Existing reserved tuples remain closed.',
        limits='Locally visible checked representations, compressed public/private text, extracted private PDFs and enumerated raw80 byte layouts. Not arbitrary encrypted/image/generated-history completeness.',
        sha256=dict(bank=digest(root / BANK), script=digest(Path(__file__)),
            scanner=digest(Path(matches.__code__.co_filename)), private_scanner=digest(Path(private_audit.__file__))))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status','proposed_operands','rejected_public_significands',
        'private_matching_significand_count','private_possible_representation_occurrences','eligible_operands',
        'eligible_discriminator_operands','eligible_kinds')},sort_keys=True), flush=True)


if __name__ == '__main__': main()
