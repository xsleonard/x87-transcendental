#!/usr/bin/env python3
"""Conservative freshness clearance for H1714; private output is aggregate only."""
import argparse
import json
from collections import Counter
from pathlib import Path
import h1691_private_center_representation_audit as private_audit
from h1623_fixed_candidate_freshness import matches
from h1709_paired_retained_census import digest, save

BANK='tmp/ledger33/current/h1714_rounding_challenge/bank.json'
SOFTWARE=('tmp/ledger33/current/h1714_rounding_scan',
    'tmp/ledger33/current/h1714_rounding_scan_v2','tmp/ledger33/current/h1714_rounding_challenge')


def refresh(root, private, out, rows, patterns):
    for name in SOFTWARE:
        assert not any(p.name in {'FREEZE.json','OPENED.json','hardware-output'} for p in (root/name).rglob('*'))
    public=matches(root,patterns,[private,out,*(root/name for name in SOFTWARE)])
    eligible=[r for r in rows if r['operand'].split()[1] not in public]
    private_signatures=matches(private,patterns,[])
    hidden,positive=private_audit.inspect(private,{r['operand'] for r in eligible})
    clean=not private_signatures and not positive and not hidden['numeric_parse_failures'] and not hidden['long_numeric_tokens_unparsed']
    return public,eligible,hidden,positive,len(private_signatures),clean


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--private-ledger-dir',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();private=a.private_ledger_dir.resolve();out=a.output_dir.resolve()
    assert private.is_dir() and private.is_relative_to(root) and not out.exists()
    bank=json.loads((root/BANK).read_text()); assert bank['capture_state']=='SOFTWARE_ONLY_NOT_FROZEN'
    for name,sha in bank['sha256']['evidence'].items():assert digest(root/name)==sha,name
    assert digest(root/'experiments/h1714_rounding_challenge.py')==bank['sha256']['script']
    out.mkdir(parents=True);patterns=out/'candidate_signatures.txt'
    with patterns.open('x') as f:f.write(''.join(s+'\n' for s in sorted({r['operand'].split()[1] for r in bank['operands']})))
    print('Public/compressed and private representation audits started; no labels are opened.',flush=True)
    public,eligible,hidden,positive,private_sigs,clean=refresh(root,private,out,bank['operands'],patterns)
    report=dict(experiment='h1714_freshness',status='AUDITED_NOT_FROZEN' if clean else 'PRIVATE_AUDIT_UNRESOLVED',
        proposed_operands=len(bank['operands']),rejected_public_significands=len(public),
        private_matching_significand_count=private_sigs,private_possible_representation_occurrences=positive,
        private_counts=dict(hidden),private_identities_contents_hashes_membership_lists_published=False,
        eligible=eligible if clean else [],eligible_operands=len(eligible) if clean else 0,
        eligible_kinds=dict(Counter(k for r in eligible for k in r['kinds'])) if clean else {},
        software_directory_exceptions=list(SOFTWARE),hardware_execution='none',manifest_frozen=False,
        policy='Reject every previously visible significand regardless of exponent, instruction, RC, PC or host. Any private possible match blocks clearance. Existing reservations remain reserved.',
        limits='Locally visible compressed text and enumerated raw80/decimal/UTF16/private PDF representations; not arbitrary encrypted, image-only or generated-history completeness.',
        sha256=dict(bank=digest(root/BANK),script=digest(Path(__file__)),scanner=digest(Path(matches.__code__.co_filename)),
            private_scanner=digest(Path(private_audit.__file__))))
    save(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('status','proposed_operands','rejected_public_significands',
        'private_matching_significand_count','private_possible_representation_occurrences','eligible_operands','eligible_kinds')}),flush=True)


if __name__=='__main__':main()
