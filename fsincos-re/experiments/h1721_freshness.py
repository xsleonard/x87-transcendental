#!/usr/bin/env python3
"""Local history clearance, with aggregate-only private evidence.

This does not execute hardware or freeze a manifest. Remote history is a
separate mandatory check. No private implementation is used as a model.
"""
import argparse
import json
from pathlib import Path
from h1623_fixed_candidate_freshness import matches
import h1691_private_center_representation_audit as private_audit
from h1719_run_saved_suite import digest,save

BANK='tmp/ledger33/current/h1721_challenge_bank/bank.json'
SOFTWARE=('tmp/ledger33/current/h1720_policy2_scan','tmp/ledger33/current/h1721_challenge_bank')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--private-ledger-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();root=a.root.resolve();private=a.private_ledger_dir.resolve();out=a.output_dir.resolve()
    assert private.is_dir() and private.is_relative_to(root)
    bank=json.loads((root/BANK).read_text());assert bank['capture_state']=='SOFTWARE_ONLY_NOT_FROZEN'
    for name,sha in bank['sha256']['evidence'].items():assert digest(root/name)==sha,name
    for name in SOFTWARE:assert not any(x.name in ('FREEZE.json','OPENED.json','hardware-output') for x in (root/name).rglob('*'))
    out.mkdir(parents=True,exist_ok=False);patterns=out/'candidate_signatures.txt'
    with patterns.open('x') as f:f.write(''.join(s+'\n' for s in sorted({r['operand'].split()[1] for r in bank['operands']})))
    print('Public compressed history scan started.',flush=True)
    public=matches(root,patterns,[private,out,root/'src/standalone',*(root/name for name in SOFTWARE)])
    eligible=[r for r in bank['operands'] if r['operand'].split()[1] not in public]
    print('Public audit complete; checking supplemental history locally.',flush=True)
    private_sigs=matches(private,patterns,[])
    hidden,positive=private_audit.inspect(private,{r['operand'] for r in eligible})
    clean=not private_sigs and not positive and not hidden['numeric_parse_failures'] and not hidden['long_numeric_tokens_unparsed']
    report=dict(status='LOCAL_AUDIT_CLEAR_NOT_FROZEN' if clean else 'PRIVATE_AUDIT_UNRESOLVED',
        proposed_operands=len(bank['operands']),rejected_public_significands=len(public),
        private_matching_significands=len(private_sigs),private_possible_occurrences=positive,private_counts=dict(hidden),
        private_identities_contents_hashes_membership_lists_published=False,eligible=eligible if clean else [],
        software_directory_exceptions=list(SOFTWARE),private_implementation_inspected=False,
        hardware_execution='none',manifest_frozen=False,remote_audit_required=True,
        limits='Visible local compressed text plus checked private raw80, decimal, UTF16 and PDF representations; not unavailable history or arbitrary encrypted/image-only records.',
        sha256=dict(bank=digest(root/BANK),script=digest(Path(__file__)),scanner=digest(matches.__code__.co_filename),
            private_scanner=digest(private_audit.__file__)))
    save(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('status','proposed_operands','rejected_public_significands','private_matching_significands','private_possible_occurrences')}),flush=True)


if __name__=='__main__':main()
