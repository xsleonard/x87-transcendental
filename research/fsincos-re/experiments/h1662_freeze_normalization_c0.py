#!/usr/bin/env python3
"""Freshness-only selection of predeclared H1661 normalization/C0 predictions."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import h1661_normalization_and_c0_proposals as proposal
import h1657_scorer_preflight as synthetic
import h1657_score_exception_state as raw
from h1623_fixed_candidate_freshness import matches
from h1640_remaining_scope_freshness import save

BANK='tmp/ledger33/current/h1661_normalization_and_c0_proposals/bank.json'
LOCKS={BANK:'2060d02cb018df0e9a21b25d7a090cda20e1fb57f93dbe1cc8eec5305e3eeb10',
    'experiments/h1661_normalization_and_c0_proposals.py':'f6ef46894be99e7b454a9517673e9965e577e04e9e56eaeba76e9ee4699267aa',
    'experiments/h1657_score_exception_state.py':'40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808',
    'experiments/h1623_fixed_candidate_freshness.py':'392554c2a402eb8b2411f851b6028326d363f21087b7f3b0d0d4791eceb87656',
    'tmp/ledger33/current/h1660_scalar_state_completion/report.json':'eae6396f2839d2a5dd84542194b44e1337333d234d866d6a0f23b68439d5fbe3'}


def coverage(rows):
    return dict(operands=len(rows),probes=dict(Counter(r['probe'] for r in rows)),
        normalization_shifts=dict(Counter(r['normalization_shift'] for r in rows if r['probe']=='normalization')),
        invalid_C0=dict(Counter((r['cc']>>8)&1 for r in rows if r['probe']=='invalid_C0')))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--private-ledger-dir',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,private,out=a.root.resolve(),a.private_ledger_dir.resolve(),a.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    digest=raw.digest; locks=dict(LOCKS)
    for name,sha in locks.items(): assert digest(root/name)==sha,name
    bank=json.loads((root/BANK).read_text()); assert bank['capture_state']=='SOFTWARE_ONLY_NOT_FROZEN'
    for name,sha in bank['sha256']['evidence'].items():
        assert digest(root/name)==sha,name
        locks[name]=sha
    assert proposal.proposals()==bank['operands']
    assert proposal.predictions(root,bank['operands'])==bank['predictions']
    preflight=Counter()
    for row in bank['predictions']:
        fields=synthetic.synthetic(row)
        fields=raw.parse(' '.join(f'{k}={v}' for k,v in fields.items()))
        assert all(raw.inspect(row,fields)['exact'].values())
        preflight['synthetic_pass_rows']+=1
        changed=dict(fields); changed['A_R0']='ffff:ffffffffffffffff'
        assert not raw.inspect(row,changed)['exact']['output']
        preflight['output_mutations_detected']+=1
        changed=dict(fields); changed['A_SW']=f'{int(fields["A_SW"],16)^0x100:04x}'
        assert not raw.inspect(row,changed)['exact']['status']
        preflight['C0_mutations_detected']+=1
    out.mkdir(parents=True)
    signatures=sorted({r['operand'].split()[1] for r in bank['operands']})
    patterns=out/'candidate_signatures.txt'
    with patterns.open('x') as target: target.write(''.join(s+'\n' for s in signatures))
    software=(root/BANK).parent
    assert not any(p.name in {'FREEZE.json','OPENED.json','hardware-output'} for p in software.rglob('*'))
    excluded=[software,out]
    if private.is_relative_to(root): excluded.append(private)
    print('Predictions and synthetic scorer checks pass. Auditing compressed public/private history.',flush=True)
    public=matches(root,patterns,excluded); hidden=matches(private,patterns,[])
    assert (public|hidden)<=set(signatures)
    rejected=public|hidden
    eligible=[r for r in bank['operands'] if r['operand'].split()[1] not in rejected]
    assert eligible
    identities={r['operand'] for r in eligible}
    selected=[dict(r,capture_state='FROZEN_UNOPENED') for r in bank['predictions'] if r['operand'] in identities]
    assert len(selected)==24*len(eligible)==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in selected})
    # No prediction changes or new masks/prestates during freshness selection.
    save(out/'manifest.json',selected)
    with (out/'inputs.txt').open('x') as target: target.write(''.join(r['capture_line']+'\n' for r in selected))
    with (out/'run_capture.sh').open('x') as target: target.write((root/'experiments/h1662_run_capture.sh').read_text())
    freeze=dict(experiment='h1662_normalization_c0',capture_state='FROZEN_UNOPENED',
        frozen_utc=datetime.now(timezone.utc).isoformat(),unique_operands=len(eligible),unique_capture_tuples=len(selected),
        proposed_coverage=coverage(bank['operands']),selected_coverage=coverage(eligible),synthetic_preflight=dict(preflight),
        one_observation_maximum_per_tuple=True,instruction_retries=0,candidate_changed=False,
        hardware_target=dict(host='45.32.204.118',family=6,model=85,capture_binary_sha256='1f0be29e0447c4b8390e3edf0b69a78f996d7c2e6293e0588ef7087cb870212e'),
        freshness=dict(rejected_public_significands=len(public),rejected_private_significands=len(hidden),
            rejected_union_significands=len(rejected),selected_public_collisions=0,selected_private_collisions=0,
            compressed_files_searched=True,private_files_examined=sum(p.is_file() for p in private.rglob('*')),
            private_identity_contents_or_hashes_published=False,
            policy='Reject every prior-visible significand; select only by freshness, not labels. Narrower instruction/RC/PC/operand keys remain unique.',
            software_only_directory_exceptions=[str(software.relative_to(root))]),
        claim_boundary='Frozen prospective full-output/full-SW completion. Rejected shifts have no new hardware coverage. No all-input silicon proof, policy relaxation or default/paper promotion.',
        sha256=dict(evidence=locks,manifest=digest(out/'manifest.json'),inputs=digest(out/'inputs.txt'),runner=digest(out/'run_capture.sh'),
            patterns=digest(patterns),freezer=digest(Path(__file__)),scorer=digest(root/'experiments/h1663_score_normalization_c0.py'),
            synthetic_helper=digest(Path(synthetic.__file__))))
    save(out/'FREEZE.json',freeze)
    with (out/'CHECKSUMS.sha256').open('x') as target:
        for name in ('FREEZE.json','manifest.json','inputs.txt','candidate_signatures.txt','run_capture.sh'):
            target.write(f'{digest(out/name)}  {name}\n')
    print(json.dumps({k:freeze[k] for k in ('unique_operands','unique_capture_tuples','selected_coverage','freshness')},sort_keys=True),flush=True)


if __name__=='__main__': main()
