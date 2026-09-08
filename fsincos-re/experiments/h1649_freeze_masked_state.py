#!/usr/bin/env python3
"""Replay, audit locally, and freeze the unchanged H1648 state predictions.

Previously visible significands are rejected, including compressed public and
private history. State fields do not exempt old operand tuples from that rule.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
import h1648_masked_state_proposals as proposal
from h1623_fixed_candidate_freshness import matches
from h1640_remaining_scope_freshness import save

BANK='tmp/ledger33/current/h1648_masked_state_proposals/bank.json'
BANK_SHA='370808966ce27c4c4f94fda177cddbc7c9c6a888c50d50d3e63b44a552240755'
CAPTURE_SHA='bd00b7ca1cf30a767ccdf7984929872188b251c3a7ab6823c3f5933f4642dbb6'
BUILD='tmp/ledger33/current/h1649_capture_build/'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--private-ledger-dir',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,private,out=a.root.resolve(),a.private_ledger_dir.resolve(),a.output_dir.resolve()
    assert private.is_dir() and not out.exists()
    digest=proposal.numerical.candidate.table.records.digest
    locks={BANK:BANK_SHA,'experiments/h1648_masked_state_proposals.py':'11db0d315529ded56f2ed7aa714316c49ad7634ccd5422f97c764c38edb13724',
        'experiments/h1623_fixed_candidate_freshness.py':'392554c2a402eb8b2411f851b6028326d363f21087b7f3b0d0d4791eceb87656',
        BUILD+'x87_masked_transition_capture':CAPTURE_SHA,
        BUILD+'capture.disassembly.txt':'b1bdd90f33b847f4596909e7584d17dc0480bd0867134ae8a6e4a1240c964641'}
    for name,sha in locks.items(): assert digest(root/name)==sha,name
    bank=json.loads((root/BANK).read_text())
    assert bank['capture_state']=='SOFTWARE_ONLY_NOT_FROZEN' and not bank['status_model_changed']
    for name,sha in bank['sha256']['evidence'].items():
        assert digest(root/name)==sha,name
        locks[name]=sha
    assert proposal.proposals()==bank['operands']
    assert proposal.predictions(root,bank['operands'])==bank['predictions']
    rows=bank['predictions']
    assert len(rows)==16128 and len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in rows})==len(rows)
    out.mkdir(parents=True)
    patterns=out/'candidate_signatures.txt'
    with patterns.open('x') as target:
        target.write(''.join(s+'\n' for s in sorted({r['operand'].split()[1] for r in rows})))
    software=(root/BANK).parent
    assert not any(p.name in {'FREEZE.json','OPENED.json','hardware-output'} for p in software.rglob('*'))
    excluded=[software,out]
    if private.is_relative_to(root): excluded.append(private)
    print('Predictions replayed; final compressed public/private significand freshness audit.',flush=True)
    public_hits=matches(root,patterns,excluded); private_hits=matches(private,patterns,[])
    assert not public_hits and not private_hits, 'Prior-visible significands found; no manifest frozen'
    manifest=[]
    for r in rows:
        line=f'{r["case_id"]} {r["instruction"]} {r["mode"]} pc{r["pc"]} {r["depth"]} {r["cc"]:04x} {r["flags"]:02x} {r["empty"]} {r["operand"]}'
        manifest.append(dict(r,capture_line=line,capture_state='FROZEN_UNOPENED'))
    save(out/'manifest.json',manifest)
    with (out/'inputs.txt').open('x') as target: target.write(''.join(r['capture_line']+'\n' for r in manifest))
    template=root/'experiments/h1649_run_capture.sh'
    with (out/'run_capture.sh').open('x') as target: target.write(template.read_text())
    freeze=dict(experiment='h1649_masked_state',capture_state='FROZEN_UNOPENED',frozen_utc=datetime.now(timezone.utc).isoformat(),
        unique_operands=672,unique_capture_tuples=16128,equal_value_pairs=1152,operand_kinds=bank['operand_kinds'],
        candidate_arithmetic_changed=False,status_model_changed=False,hardware_execution='none',
        one_observation_maximum_per_tuple=True,
        identity='instruction+RC+PC+masks+operand plus explicit CC/sticky/depth/tag prestate; even the narrower instruction/RC/PC/operand keys are unique and fresh',
        hardware_target=dict(host='45.32.204.118',family=6,model=85,capture_binary_sha256=CAPTURE_SHA),
        freshness=dict(selected_public_collisions=0,selected_private_collisions=0,compressed_files_searched=True,
            private_files_examined=sum(p.is_file() for p in private.rglob('*')),private_identity_contents_or_hashes_published=False,
            policy='Reject every prior-visible significand regardless of exponent/instruction/RC/PC/host/prestate.',
            software_only_directory_exceptions=[str(software.relative_to(root))]),
        claim_boundary=bank['prediction_scope']+' No all-input silicon proof, new arithmetic selector, default or paper change.',
        sha256=dict(evidence=locks,manifest=digest(out/'manifest.json'),inputs=digest(out/'inputs.txt'),
            runner=digest(out/'run_capture.sh'),freezer=digest(Path(__file__)),patterns=digest(patterns),
            scorer=digest(root/'experiments/h1650_score_masked_state.py')))
    save(out/'FREEZE.json',freeze)
    with (out/'CHECKSUMS.sha256').open('x') as target:
        for name in ('FREEZE.json','manifest.json','inputs.txt','candidate_signatures.txt','run_capture.sh'):
            target.write(f'{digest(out/name)}  {name}\n')
    print(json.dumps({k:freeze[k] for k in ('unique_operands','unique_capture_tuples','equal_value_pairs','freshness')},sort_keys=True),flush=True)


if __name__=='__main__': main()
