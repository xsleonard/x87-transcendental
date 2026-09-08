#!/usr/bin/env python3
"""Reconcile retained raw pre/post state and locate special-class exceptions.

The paired rows establish their BEFORE-load state, not automatic numerical
transfer to standalone instructions. Preserve the three known failed PE seeds.
No hardware, labels, private history or canonical/default changes.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import h1405_score_single_shot_state as old
from h1640_remaining_scope_freshness import save

STATE='tmp/ledger33/current/h1401_single_shot/'
LOCKS={
    STATE+'raw-state-output.txt':'1d937f8f3775aeecd01fb88cc7277dfb6cba4020ec79c46d341821dd3a2b0c1d',
    STATE+'identity-manifest.tsv':'404770c1db4be96909c23ee1d0b0332a5963ed1a50e196b801180c30330a49df',
    'transfer-tests/h1400/core-transfer.tsv':'951d00440e3620958dbd060235fd3cfe4e7d94a2d33f6e20a9dfbb643b8fc8eb',
    'transfer-tests/h1400/architecture-semantics.tsv':'97c506b70991e74a7174df2cbe5c452ed5727f8098bbe894041a0ca3d9eb4b63',
    'experiments/h1405_score_single_shot_state.py':'ce680d7e3711cc111803feb16455ecef8bf37c2b2e24fe99a09831fe2e5becd2',
    'tmp/ledger33/current/h1405b_single_shot_report.txt':'bc5853a3da8723b5edc2c8f399c12b63376eccc37ce7e8881696ab38bcd21016',
    'tmp/pdfs/h1644-intel-sdm-089.pdf':'1eb81360c636a723fb34610a1deef276e98e1fc331ac08b380114079664add20',
}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    for name,sha in LOCKS.items(): assert old.sha256(root/name)==sha,name
    core=old.read_tsv(root/'transfer-tests/h1400/core-transfer.tsv')
    architecture=old.read_tsv(root/'transfer-tests/h1400/architecture-semantics.tsv')
    expected=old.expected_identity(core,architecture)
    old.verify_identity(expected,old.read_tsv(root/STATE/'identity-manifest.tsv'))
    raw=old.parse_state(root/STATE/'raw-state-output.txt')
    assert len(raw)==len(expected)==124
    setup_failures={}; before=[]; counts=Counter(); by_id={}
    for ident,row in zip(expected,raw):
        assert ident['case_id'].lower()==row['CASE']
        case=ident['case_id']; by_id[case]=row
        errors=old.check_before(ident,row)
        if errors: setup_failures[case]=errors
        assert row['B_R0']==ident['operand'].replace(' ',':').lower()
        sw=int(row['B_SW'],16); after=int(row['A_SW'],16)
        flags=sw&0x3f; counts['before_exception_mask/'+f'{flags:02x}']+=1
        before.append(dict(case=case,instruction=row['INSN'],operand=row['B_R0'],before_SW=row['B_SW'],
            after_SW=row['A_SW'],new_exception_bits=f'{(after&0x3f)&~flags:02x}',setup_errors=errors))
    assert setup_failures=={k:['before.prior_flags.pe'] for k in ('A002','A005','A024')}
    for row in architecture:
        assert not old.check_relation(row,by_id[row['case_id']])
    special=[]
    for case,flag in (('A008',0),('A009',1),('A010',1),('A011',1),('A012',0x32),('A013',0x22)):
        row=by_id[case]
        assert int(row['B_SW'],16)&0x3f==0 and int(row['A_SW'],16)&0x3f==flag
        special.append(dict(case=case,operand=row['B_R0'],instruction=row['INSN'],before_flags=0,after_flags=flag,
            before_value=row['B_R0'],after_cosine=row['A_R0'],after_sine=row['A_R1']))
    # FXSAVE occurs after FLDT but before FSINCOS. The unchanged raw payloads
    # and zero preflags localize these flags to the arithmetic instruction.
    # They do not identify internal micro-operations or prove standalone parity.
    out.mkdir(parents=True)
    save(out/'before_after.json',before)
    report=dict(experiment='h1644_load_status_causal_audit',status='PASS_RECONCILIATION',raw_rows=124,
        setup_failures=setup_failures,counts=dict(counts),special_rows=special,
        all_loaded_operands_raw_unchanged=True,architecture_relations_replayed=24,
        manual=dict(url='https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf',
            pdf_pages_1_based=dict(denormal=236,underflow=237,precision=238,FCOS=[1019,1020],FLD=[1041,1042],FSIN=[1069,1070]),
            limits='FLD m80fp excludes denormal/SNaN load exceptions. FSIN/FCOS C0/C3 are architecturally undefined. The FSIN exception list omits U despite the retained observed underflow flags; do not use it to erase silicon evidence.'),
        hardware_execution='none',private_ledger_access='none',paper_or_default_change='none',
        claim_boundary='Retained before/after evidence, not new observations or paired-to-standalone numerical transfer. Failed PE seeds remain failed, not sticky-PE evidence.',
        sha256=dict(script=old.sha256(Path(__file__)),evidence=LOCKS,before_after=old.sha256(out/'before_after.json')))
    save(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('status','raw_rows','counts','setup_failures')},sort_keys=True),flush=True)


if __name__=='__main__': main()
