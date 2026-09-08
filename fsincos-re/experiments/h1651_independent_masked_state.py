#!/usr/bin/env python3
"""Independent raw parser, numerical replay and masked-state algebra for H1649.

Does not import the H1650 parser or H1645 status implementation. New condition
bit write-mask agreement is retrospective, never renamed prospective proof.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import h1638_tiny_c_transfer as cmodel
import h1636_retained_rz_pc_transfer as independent
from h1640_remaining_scope_freshness import save

KIT='transfer-tests/h1649/'
SCORE='tmp/ledger33/current/h1650_score_masked_state/'
MODELS='tmp/ledger33/current/h1638_tiny_c_transfer/'
LOCKS={
    KIT+'FREEZE.json':'cd257a2353b8dd90a7ba06026ed715554454dbeac7462d42b46aa46f8383ec33',
    KIT+'manifest.json':'00ba74c08d8f4154cfdc74e0fdd0bd876dca2b69282e6656c23d5a3f9b1c19ee',
    SCORE+'report.json':'6373f96f8e62d7d2ef32a784800f754109081ac60aabe111661ca0babb202a28',
}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    digest=independent.proof.digest
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    freeze=json.loads((root/KIT/'FREEZE.json').read_text())
    for name,sha in freeze['sha256']['evidence'].items(): assert digest(root/name)==sha,name
    score=json.loads((root/SCORE/'report.json').read_text())
    assert digest(root/SCORE/'score.json')==score['sha256']['score']
    previous={r['case_id']:r for r in json.loads((root/SCORE/'score.json').read_text())}
    rows=json.loads((root/KIT/'manifest.json').read_text())
    path=root/KIT/'hardware-output/state-output.txt'
    assert digest(path)==score['sha256']['raw_output']
    lines=path.read_text().splitlines(); assert len(rows)==len(lines)==16128
    independent.initialize_proof(root)
    model_report=json.loads((root/MODELS/'report.json').read_text())
    counts=Counter(); recomputed=[]
    for insn in ('fsin','fcos'):
        for mode in ('rn','rd','ru','rz'):
            for pc in (24,53,64):
                indices=[i for i,r in enumerate(rows) if (r['instruction'],r['mode'],r['pc'])==(insn,mode,pc)]
                selected=[rows[i] for i in indices]; ops=[r['operand'] for r in selected]
                reference=None
                for label in ('candidate_O0','candidate_O2','candidate_O3','candidate_ubsan'):
                    binary=root/MODELS/label
                    assert digest(binary)==model_report['sha256']['binaries'][label]
                    values,metadata,_=cmodel.run(binary,insn,mode,ops)
                    if reference is None: reference=values,metadata
                    assert (values,metadata)==reference
                    counts['software_build_rows']+=len(ops)
                values,metadata=reference
                for pos,i in enumerate(indices):
                    row=rows[i]; words=lines[i].lower().split()
                    assert all(w.count('=')==1 for w in words)
                    pairs=[w.split('=') for w in words]
                    fields=dict(pairs); assert len(pairs)==len(fields)==33
                    assert fields['case']==row['case_id'].lower()
                    assert fields['insn']==insn and fields['mode']==mode and fields['pc']==f'pc{pc}'
                    assert int(fields['cc'],16)==row['cc'] and int(fields['flags'],16)==row['flags']
                    assert int(fields['depth'])==row['depth'] and int(fields['empty'])==row['empty']
                    before=int(fields['b_sw'],16); after=int(fields['a_sw'],16)
                    cw=0x7f|{24:0,53:0x200,64:0x300}[pc]|{'rn':0,'rd':0x400,'ru':0x800,'rz':0xc00}[mode]
                    top=(8-row['depth'])%8
                    tag=((1<<row['depth'])-1)<<(8-row['depth'])
                    if row['empty']: tag-=1<<top
                    assert before==(top<<11)|row['cc']|row['flags']
                    assert int(fields['b_ftw'],16)==tag and int(fields['b_top'])==top
                    assert int(fields['b_cw'],16)==int(fields['a_cw'],16)==cw
                    se,sig=(int(w,16) for w in row['operand'].split()); e=se&0x7fff; j=sig>>63
                    encoded=f'{se:04x}:{sig:016x}'
                    assert fields['b_r0']==encoded
                    for k in range(1,row['depth']): assert fields[f'b_r{k}']==f'3fff:{(1<<63)+8*k:016x}'
                    assert all(fields[f'a_r{k}']==fields[f'b_r{k}'] for k in range(1,8))
                    assert int(fields['a_top'])==top and after&0x3800==top<<11
                    meta=metadata.get(pos); small=cmodel.spec.evaluate(row['operand'],insn,mode)
                    if meta and meta['lane'] in ('polynomial','table'):
                        number,c1,_,_=independent.verify_hit(row['operand'],insn,mode,meta)
                    else: number,c1=small['output'],small['C1']
                    assert number==values[pos] and meta==row['numerical']['metadata']
                    c2=0; new_flags=0; sf=before&0x40; unknown=0x4100
                    if row['empty']:
                        expected='ffff:c000000000000000'; new_flags=1; sf=0x40; c1=0; unknown|=0x400; tag|=1<<top
                    elif e and not j:
                        expected='ffff:c000000000000000'; new_flags=1; c1=0; unknown|=0x400
                    elif e==0x7fff:
                        assert sig!=(1<<63)  # Infinity is not in this fresh bank.
                        expected=f'{se:04x}:{sig|(1<<62):016x}'
                        new_flags=int(not sig&(1<<62)); c1=0; unknown|=0x400
                    elif not e:
                        assert sig
                        expected=number; new_flags=0x22|(0x10 if insn=='fsin' and not j else 0)
                    elif e>=0x403e:
                        expected=encoded; c2=1; c1=0; unknown|=0x200
                    else:
                        expected=number; new_flags=0x20
                    assert c1 in (0,1)
                    modeled=(top<<11)|(before&0x3f)|new_flags|sf|(c1<<9)|(c2<<10)
                    known=0xffff^unknown
                    assert modeled==row['expected']['status_bits'] and known==row['expected']['status_known_mask']
                    assert fields['a_r0']==expected and int(fields['a_ftw'],16)==tag
                    assert ((after^modeled)&known)==0
                    # Retrospective single write-mask candidate: preserve C0/C3;
                    # clear C1/C2 before inserting final outcome bits.
                    full=modeled|(before&0x4100)
                    assert after==full
                    assert previous[row['case_id']]['actual']['A_SW']==fields['a_sw']
                    counts['raw_rows']+=1
                    counts['nonempty_four_build_output_checks']+=0 if row['empty'] else 4
                    counts['posthoc_full_SW_matches']+=1
                    recomputed.append(dict(case_id=row['case_id'],output=expected,status_bits=modeled,
                        status_known_mask=known,observed_full_SW=after,posthoc_write_mask_SW=full,
                        top=top,tag=tag,new_exception_flags=new_flags))
    assert counts['raw_rows']==16128 and counts['nonempty_four_build_output_checks']==59904
    out.mkdir(parents=True); save(out/'recomputed.json',recomputed)
    result=dict(experiment='h1651_independent_masked_state',status='PASS_INDEPENDENT_RAW_NUMERICAL_STATE',counts=dict(counts),
        hardware_execution='none',private_ledger_access='none',model_or_paper_change='none',
        claim_boundary='Separate raw parser and flag algebra plus rational/integer numerical recomputation. Full SW write-mask matches are retrospective observations; zero/infinity, unmasked/pending/reserved controls and all-input silicon correctness remain unproved.',
        sha256=dict(script=digest(Path(__file__)),evidence=LOCKS,recomputed=digest(out/'recomputed.json')))
    save(out/'report.json',result)
    print(json.dumps(dict(status=result['status'],counts=dict(counts)),sort_keys=True),flush=True)


if __name__=='__main__': main()
