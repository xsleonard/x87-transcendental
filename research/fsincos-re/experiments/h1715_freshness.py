#!/usr/bin/env python3
"""Aggregate-only local freshness audit for H1715, before portable capture."""
import argparse
import json
from collections import Counter
from pathlib import Path
import h1714_freshness as base
from h1709_paired_retained_census import digest,save

BANK='tmp/ledger33/current/h1715_challenge_bank/bank.json'
SOFTWARE=('tmp/ledger33/current/h1715_internal_scan','tmp/ledger33/current/h1715_challenge_bank')


def refresh(root,private,out,rows,patterns):
    old=base.SOFTWARE;base.SOFTWARE=SOFTWARE
    try:return base.refresh(root,private,out,rows,patterns)
    finally:base.SOFTWARE=old


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--private-ledger-dir',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();private=a.private_ledger_dir.resolve();out=a.output_dir.resolve();assert not out.exists()
    bank=json.loads((root/BANK).read_text());assert bank['capture_state']=='SOFTWARE_ONLY_NOT_FROZEN'
    for name,sha in bank['sha256']['evidence'].items():assert digest(root/name)==sha,name
    out.mkdir(parents=True);patterns=out/'candidate_signatures.txt'
    with patterns.open('x') as f:f.write(''.join(s+'\n' for s in sorted({r['operand'].split()[1] for r in bank['operands']})))
    print('Public/compressed and private local representation checks started.',flush=True)
    public,eligible,hidden,positive,private_sigs,clean=refresh(root,private,out,bank['operands'],patterns)
    report=dict(experiment='h1715_freshness',status='AUDITED_NOT_FROZEN' if clean else 'PRIVATE_AUDIT_UNRESOLVED',
        proposed_operands=len(bank['operands']),rejected_public_significands=len(public),private_matching_significand_count=private_sigs,
        private_possible_representation_occurrences=positive,private_counts=dict(hidden),eligible=eligible if clean else [],
        eligible_operands=len(eligible) if clean else 0,eligible_kinds=dict(Counter(k for r in eligible for k in r['kinds'])) if clean else {},
        private_identities_contents_hashes_membership_lists_published=False,software_directory_exceptions=list(SOFTWARE),
        hardware_execution='none',manifest_frozen=False,
        policy='Reject every prior public significand and fail closed on any private possible match; preserve reservations. Local visibility is not arbitrary encrypted/image-only/generated-history completeness.',
        sha256=dict(bank=digest(root/BANK),script=digest(Path(__file__)),base=digest(Path(base.__file__)),
            scanner=digest(Path(base.matches.__code__.co_filename)),private_scanner=digest(Path(base.private_audit.__file__))))
    save(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('status','proposed_operands','rejected_public_significands',
        'private_matching_significand_count','private_possible_representation_occurrences','eligible_operands','eligible_kinds')}),flush=True)


if __name__=='__main__':main()
