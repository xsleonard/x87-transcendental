#!/usr/bin/env python3
"""Freeze fresh restoration-only observations after private/public audit."""
import argparse
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import h1679_restore_paths_proposals as proposal
import h1681_score_restore_paths as score
import h1682_independent_restore_paths as independent
from h1623_fixed_candidate_freshness import matches
from h1640_remaining_scope_freshness import save

BANK='tmp/ledger33/current/h1679_restore_paths_proposals/bank.json'
LOCKS={BANK:'40c1ac8271901364720dcfc81ad6c9f268f1fa75bf45299d36314d34a98a4dce',
    'experiments/h1679_restore_paths_proposals.py':'a02ca1fa0192bab1f20e018cf76a395459736c6c9b2b64af7b63cf7b37a2d7e7',
    'experiments/h1681_score_restore_paths.py':'6fc88b6b4499f378eacfd51222ea1b2c8e612618172142c2ee2593c0e487b583',
    'experiments/h1682_independent_restore_paths.py':'9da52eae937ed096cb505672d16688565cd2d84c80fa56a97ed190aa48305bef',
    'tmp/ledger33/current/h1681_restore_preflight/report.json':'57c570ce86b2f900fd9275d37861e4375242675ff3b923938d87a75c3691e2e0',
    'tmp/ledger33/current/h1682_restore_software_preflight/report.json':'00946dfe2e5a687d6b1c2d6860d3155b64e94536d4e064df2f16d9b3c840c939',
    'tmp/ledger33/current/h1678_restore_paths_static/report.json':'7db00cebb8b477ea727e8340b7c082c6b609e9884e9cbd6f701b80da171241f7',
    'experiments/h1623_fixed_candidate_freshness.py':'392554c2a402eb8b2411f851b6028326d363f21087b7f3b0d0d4791eceb87656'}

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    p.add_argument('--private-ledger-dir',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,private,out=a.root.resolve(),a.private_ledger_dir.resolve(),a.output_dir.resolve()
    assert private.is_dir() and not out.exists(); digest=score.digest; locks=dict(LOCKS)
    for name,sha in locks.items(): assert digest(root/name)==sha,name
    bank=json.loads((root/BANK).read_text()); assert bank['capture_state']=='SOFTWARE_ONLY_NOT_FROZEN'
    for name,sha in bank['sha256']['evidence'].items(): assert digest(root/name)==sha,name; locks[name]=sha
    assert proposal.proposals()==bank['rows']
    assert all(independent.expectation(row)==row['prediction'] for row in bank['rows'])
    preflight=score.preflight(bank['rows'])
    assert preflight==json.loads((root/'tmp/ledger33/current/h1681_restore_preflight/report.json').read_text())['counts']
    out.mkdir(parents=True); patterns=out/'candidate_signatures.txt'
    signatures={r['operand'].split()[1] for r in bank['rows']}
    with patterns.open('x') as target: target.write(''.join(s+'\n' for s in sorted(signatures)))
    software=(root/BANK).parent
    assert not any(p.name in {'FREEZE.json','OPENED.json','hardware-output'} for p in software.rglob('*'))
    excluded=[software,out]+([private] if private.is_relative_to(root) else [])
    print('Prediction replay/preflight passed; checking compressed public/private history.',flush=True)
    public=matches(root,patterns,excluded); hidden=matches(private,patterns,[])
    assert (public|hidden)<=signatures
    selected=[dict(r,capture_state='FROZEN_UNOPENED') for r in bank['rows'] if r['operand'].split()[1] not in public|hidden]
    assert len(selected)==len({r['operand'] for r in selected})
    assert len({(r['method'],r['order']) for r in selected})==10
    save(out/'manifest.json',selected)
    with (out/'inputs.txt').open('x') as target: target.write(''.join(r['capture_line']+'\n' for r in selected))
    with (out/'run_capture.sh').open('x') as target: target.write((root/'experiments/h1680_run_capture.sh').read_text())
    freeze=dict(experiment='h1680_restore_paths',capture_state='FROZEN_UNOPENED',frozen_utc=datetime.now(timezone.utc).isoformat(),
        unique_capture_tuples=len(selected),unique_operands=len(selected),method_counts=dict(Counter(r['method'] for r in selected)),
        one_observation_maximum_per_tuple=True,instruction_retries=0,transcendental_executions=0,pending_delivery_credit=0,
        hardware_target=dict(host='45.32.204.118',role='Skylake Xeon',family=6,model=85,
            capture_binary_sha256='f093eb12fd2d2102bc5711618b69427b499d2bbdb907bfebbfc4700fbf134bee'),
        freshness=dict(rejected_public_significands=len(public),rejected_private_significands=len(hidden),
            rejected_union_significands=len(public|hidden),selected_public_collisions=0,selected_private_collisions=0,
            compressed_files_searched=True,private_files_examined=sum(p.is_file() for p in private.rglob('*')),
            private_identity_contents_or_hashes_published=False,
            policy='Reject every prior-visible significand across instructions, controls, states and hosts. Each selected operand has exactly one setup/observation path; selection is freshness-only.',
            software_only_directory_exceptions=[str(software.relative_to(root))]),
        claim_boundary='Restoration-only hypotheses, not FSIN/FCOS execution or exception-consumption credit. No observed labels used to alter predictions; undefined CC/pointers excluded. No default/paper promotion.',
        sha256=dict(evidence=locks,manifest=digest(out/'manifest.json'),inputs=digest(out/'inputs.txt'),patterns=digest(patterns),
            runner=digest(out/'run_capture.sh'),freezer=digest(Path(__file__)),scorer=digest(Path(score.__file__)),
            independent=digest(Path(independent.__file__))))
    save(out/'FREEZE.json',freeze)
    with (out/'CHECKSUMS.sha256').open('x') as target:
        for name in ('FREEZE.json','manifest.json','inputs.txt','candidate_signatures.txt','run_capture.sh'):
            target.write(f'{digest(out/name)}  {name}\n')
    print(json.dumps({k:freeze[k] for k in ('unique_capture_tuples','method_counts','freshness')},sort_keys=True),flush=True)
if __name__=='__main__': main()
