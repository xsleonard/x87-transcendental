#!/usr/bin/env python3
"""Freeze all H1640-eligible H1639 predictions after a fresh local audit.

No labels are read and no hardware runs. The fixed four-build outputs and
separate integer/rational formulas are replayed before the immutable manifest.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import h1639_remaining_scope_proposals as proposals
from h1640_remaining_scope_freshness import BANK, BANK_SHA, SCANNER_SHA, save
from h1623_fixed_candidate_freshness import matches

AUDIT = 'tmp/ledger33/current/h1640_remaining_scope_freshness/report.json'
AUDIT_SHA = '4e55a5041ba75cca79689e9cfa2173d6c4bffab7be035322f8bae3776e9d3b7c'
CAPTURE_SHA = '9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--private-ledger-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root, private, output = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and not output.exists()
    digest = proposals.candidate.table.records.digest
    locks = {BANK:BANK_SHA, AUDIT:AUDIT_SHA,
        'experiments/h1623_fixed_candidate_freshness.py':SCANNER_SHA,
        'experiments/h1640_remaining_scope_freshness.py':'cb39f44ac28655de16e1b4b069772e9f3ff1d97099746d9d3e8a706c44414ebf',
        'capture-kit/x87_capture.c':'aededbaea438dbd1526aca4926530b655d6c9a1ad0f0bac82ad58fcbe3d824d1'}
    for name, expected in locks.items(): assert digest(root/name) == expected, name
    bank, audit = (json.loads((root/name).read_text()) for name in (BANK,AUDIT))
    assert bank['capture_state'] == 'SOFTWARE_ONLY_NOT_FROZEN' and not bank['candidate_changed']
    assert audit['state'] == 'AUDITED_PROPOSALS_NOT_FROZEN'
    for name, expected in bank['sha256']['evidence'].items():
        assert digest(root/name) == expected, name
        locks[name] = expected
    chosen = audit['eligible']; operands = [r['operand'] for r in chosen]
    assert len(operands) == len(set(operands)) == 268 and audit['eligible_full_tuples'] == 6432
    original = {r['operand']:r for r in bank['operands']}
    assert all(original[r['operand']] == r for r in chosen)
    predicted = {(r['instruction'],r['mode'],r['operand']):r for r in bank['predictions']}
    proposals.independent.initialize_proof(root)
    for insn in ('fsin','fcos'):
        for mode in ('rn','rd','ru','rz'):
            reference = [predicted[(insn,mode,op)] for op in operands]
            for label, sha in bank['sha256']['binaries'].items():
                binary = root/proposals.MODELS/label; assert digest(binary) == sha
                values, metadata, _ = proposals.candidate.run(binary,insn,mode,operands)
                assert values == [r['output'] for r in reference]
                assert [metadata.get(i) for i in range(len(operands))] == [r['metadata'] for r in reference]
            for r in reference:
                small = proposals.candidate.spec.evaluate(r['operand'],insn,mode)
                meta = r['metadata']
                if meta and meta['lane'] in ('table','polynomial'):
                    value,c1,_,center = proposals.independent.verify_hit(r['operand'],insn,mode,meta)
                    assert value == r['output'] and c1 == r['C1'] and center == r['exact_center']
                else:
                    proposals.candidate.check_spec(r['operand'],insn,mode,r['output'],meta)
                    assert small['output'] == r['output'] and small['C1'] == r['C1']
                assert small['exception_flags'] == r['exception_flags']
    output.mkdir(parents=True)
    patterns = output/'candidate_signatures.txt'
    with patterns.open('x') as target:
        target.write(''.join(s+'\n' for s in sorted({op.split()[1] for op in operands})))
    software = [(root/BANK).parent,(root/AUDIT).parent]
    for directory in software:
        assert not any(p.name in {'OPENED.json','FREEZE.json','hardware-output'} for p in directory.rglob('*'))
    excluded = software + [output]
    if private.is_relative_to(root): excluded.append(private)
    print('All four-build and independent predictions replayed; final public/private freshness recheck.',flush=True)
    public_hits, private_hits = matches(root,patterns,excluded), matches(private,patterns,[])
    assert not public_hits and not private_hits, 'Freshness changed; no manifest frozen'
    inputs = output/'inputs'; inputs.mkdir()
    rows, lanes = [], {}
    for insn in ('fsin','fcos'):
        for pc in (24,53,64):
            for mode in ('rn','rd','ru','rz'):
                lane = f'{insn}_pc{pc}_{mode}'
                for op in operands:
                    r = predicted[(insn,mode,op)]
                    rows.append(dict(r,case_id=f'F{len(rows)+1:05d}',lane=lane,precision_control=pc,capture_state='FROZEN_UNOPENED'))
                path = inputs/(lane+'.txt')
                with path.open('x') as target: target.write(''.join(op+'\n' for op in operands))
                lanes[lane] = dict(rows=len(operands),instruction=insn,precision_control=pc,mode=mode,sha256=digest(path))
    assert len(rows) == len({(r['instruction'],r['precision_control'],r['mode'],r['operand']) for r in rows}) == 6432
    save(output/'manifest.json',rows)
    runner = output/'run_capture.sh'; template = root/'experiments/h1641_run_capture.sh'
    with runner.open('x') as target: target.write(template.read_text())
    freeze = dict(experiment='h1641_remaining_scope',capture_state='FROZEN_UNOPENED',frozen_utc=datetime.now(timezone.utc).isoformat(),
        hardware_execution='none',candidate_changed=False,one_observation_maximum_per_tuple=True,
        unique_operands=len(operands),unique_capture_tuples=len(rows),lanes=lanes,operand_kinds=audit['eligible_kinds'],
        selection_rule='All 268 H1640-eligible operands, both instructions, RN/RD/RU/RZ, PC24/53/64. No label selection.',
        hardware_target=dict(host='45.32.204.118',family=6,model=85,capture_binary_sha256=CAPTURE_SHA),
        predicted_C1_tuples=sum(r['C1'] is not None for r in rows),
        predicted_exception_mask_tuples=sum(r['exception_flags'] is not None for r in rows),
        independent_instruction_mode_checks=len(operands)*8,C_builds_replayed=4,
        freshness=dict(selected_public_collisions=0,selected_private_collisions=0,compressed_files_searched=True,
            private_files_examined=sum(p.is_file() for p in private.rglob('*')),
            private_identity_contents_or_hashes_published=False,
            policy=audit['freshness']['policy'],software_only_public_directory_exceptions=[str(p.relative_to(root)) for p in software]),
        claim_boundary=bank['prediction_limits']+' Finite prospective test, not universal closure, production promotion or paper update.',
        sha256=dict(evidence=locks,manifest=digest(output/'manifest.json'),runner=digest(runner),template=digest(template),
            scorer=digest(root/'experiments/h1642_score_remaining_scope.py'),freezer=digest(Path(__file__)),patterns=digest(patterns)))
    save(output/'FREEZE.json',freeze)
    with (output/'CHECKSUMS.sha256').open('x') as target:
        for path in (output/'FREEZE.json',output/'manifest.json',runner,patterns,*sorted(inputs.iterdir())):
            target.write(f'{digest(path)}  {path.relative_to(output)}\n')
    print(json.dumps({k:freeze[k] for k in ('unique_operands','unique_capture_tuples','predicted_C1_tuples','predicted_exception_mask_tuples','freshness')},sort_keys=True),flush=True)


if __name__ == '__main__':
    main()
