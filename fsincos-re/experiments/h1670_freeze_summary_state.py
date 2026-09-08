#!/usr/bin/env python3
"""Freeze unchanged ES/B proposals after conservative local freshness checks."""
import argparse
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import h1668_summary_state_proposals as proposal
import h1669_score_summary_state as score
from h1623_fixed_candidate_freshness import matches
from h1640_remaining_scope_freshness import save

BANK='tmp/ledger33/current/h1668_summary_state_proposals/bank.json'
LOCKS={BANK:'2730bb54fbaf1170b1c8b024edf12c1b340b1113613527c8c7df1a875d6c4511',
    'experiments/h1668_summary_state_proposals.py':'71df85d7800131f9f6ff394fd896fc7dc88af3a96e6ea11c61a9b6d273acbd14',
    'experiments/h1669_score_summary_state.py':'7e2bd40c5bc4277f964d332af3cddafe426951c28db08635fc84ca4713b86993',
    'experiments/h1671_independent_summary_state.py':'b3e879312a4daf763a43ed761ae594e03b48463a1d7719ebedc5d811a521b6c0',
    'experiments/h1657_score_exception_state.py':'40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808',
    'experiments/h1623_fixed_candidate_freshness.py':'392554c2a402eb8b2411f851b6028326d363f21087b7f3b0d0d4791eceb87656',
    'tmp/ledger33/current/h1669_summary_preflight/report.json':'b4463355082b6c1ea3fddc6e44d77b1f6b434433f013f648a5200dae20128b3f',
    'tmp/ledger33/current/h1671_summary_software_preflight/report.json':'02d09d39506495366fe7c586653ef0b917e1df13ad551b50e5bb1320e3343920'}


def coverage(rows):
    return dict(operands=len(rows),kinds=dict(Counter(r['kind'] for r in rows)),
        requested_U_ES_B=dict(Counter(f'{int(bool(r["flags"]&~r["masks"]&63))}{int(bool(r["summary"]&128))}{int(bool(r["summary"]&32768))}' for r in rows)))


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    p.add_argument('--private-ledger-dir',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,private,out=a.root.resolve(),a.private_ledger_dir.resolve(),a.output_dir.resolve()
    assert private.is_dir() and not out.exists(); digest=score.digest; locks=dict(LOCKS)
    for name,sha in locks.items(): assert digest(root/name)==sha,name
    bank=json.loads((root/BANK).read_text()); assert bank['capture_state']=='SOFTWARE_ONLY_NOT_FROZEN'
    for name,sha in bank['sha256']['evidence'].items(): assert digest(root/name)==sha,name; locks[name]=sha
    assert proposal.proposals()==bank['operands'] and proposal.predictions(root,bank['operands'])==bank['predictions']
    preflight=score.preflight(bank['predictions'])
    assert preflight==json.loads((root/'tmp/ledger33/current/h1669_summary_preflight/report.json').read_text())['counts']
    print('Frozen prediction replay and synthetic preflight pass; scanning public/private freshness.',flush=True)
    out.mkdir(parents=True); patterns=out/'candidate_signatures.txt'
    signatures={r['operand'].split()[1] for r in bank['operands']}
    with patterns.open('x') as target: target.write(''.join(s+'\n' for s in sorted(signatures)))
    software=(root/BANK).parent
    assert not any(p.name in {'FREEZE.json','OPENED.json','hardware-output'} for p in software.rglob('*'))
    excluded=[software,out]+([private] if private.is_relative_to(root) else [])
    public=matches(root,patterns,excluded); hidden=matches(private,patterns,[])
    assert (public|hidden)<=signatures
    eligible=[r for r in bank['operands'] if r['operand'].split()[1] not in public|hidden]
    assert set(coverage(eligible)['requested_U_ES_B'])=={'000','001','010','011','100','101','110','111'}
    identities={r['operand'] for r in eligible}
    selected=[dict(r,capture_state='FROZEN_UNOPENED') for r in bank['predictions'] if r['operand'] in identities]
    assert len(selected)==24*len(eligible)==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in selected})
    save(out/'manifest.json',selected)
    with (out/'inputs.txt').open('x') as target: target.write(''.join(r['capture_line']+'\n' for r in selected))
    with (out/'run_capture.sh').open('x') as target: target.write((root/'experiments/h1670_run_capture.sh').read_text())
    freeze=dict(experiment='h1670_summary_state',capture_state='FROZEN_UNOPENED',frozen_utc=datetime.now(timezone.utc).isoformat(),
        unique_operands=len(eligible),unique_capture_tuples=len(selected),selected_coverage=coverage(eligible),synthetic_preflight=preflight,
        one_observation_maximum_per_tuple=True,instruction_retries=0,candidate_changed=False,
        hardware_target=dict(host='45.32.204.118',family=6,model=85,capture_binary_sha256='04147ce0b5f38b122dd46c2dfcf7c4b4dca3cbd846040de3873b91910115a296'),
        freshness=dict(rejected_public_significands=len(public),rejected_private_significands=len(hidden),
            rejected_union_significands=len(public|hidden),selected_public_collisions=0,selected_private_collisions=0,
            compressed_files_searched=True,private_files_examined=sum(p.is_file() for p in private.rglob('*')),
            private_identity_contents_or_hashes_published=False,
            policy='Reject every prior-visible significand, independently of instruction/control/state/host. Selection is freshness-only; old narrower instruction/RC/PC/operand keys remain unique.',
            software_only_directory_exceptions=[str(software.relative_to(root))]),
        claim_boundary='Identity restoration and ES pending are frozen hypotheses; conditional executed arithmetic/state is scored separately. Unknown post-execution summary/delivery is not predicted credit. No all-input proof or default/paper promotion.',
        sha256=dict(evidence=locks,manifest=digest(out/'manifest.json'),inputs=digest(out/'inputs.txt'),patterns=digest(patterns),
            runner=digest(out/'run_capture.sh'),freezer=digest(Path(__file__)),scorer=digest(Path(score.__file__))))
    save(out/'FREEZE.json',freeze)
    with (out/'CHECKSUMS.sha256').open('x') as target:
        for name in ('FREEZE.json','manifest.json','inputs.txt','candidate_signatures.txt','run_capture.sh'):
            target.write(f'{digest(out/name)}  {name}\n')
    print(json.dumps({k:freeze[k] for k in ('unique_capture_tuples','selected_coverage','freshness')},sort_keys=True),flush=True)


if __name__=='__main__': main()
