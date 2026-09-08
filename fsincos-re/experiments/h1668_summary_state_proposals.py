#!/usr/bin/env python3
"""Predeclare restoration/gate discriminators and conditional execution checks.

Requested ES/B restoration and pending delivery are explicitly hypotheses.
No model is fitted, no old tuple becomes eligible through new state fields,
and unknown post-execution summary bits/delivery receive no predicted credit.
"""
import argparse
import json
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import h1648_masked_state_proposals as numerical
import h1660_scalar_state_completion as completion
from h1650_score_masked_state import digest
from h1640_remaining_scope_freshness import save

BUILD='tmp/ledger33/current/h1667_capture_build/'
LOCKS={**numerical.LOCKS, **completion.LOCKS,
    'experiments/h1660_scalar_state_completion.py':'ca97e612effca75c47d592e9bdaca360c95f219cee8a736072b623c464dd17c9',
    'experiments/h1666_summary_observability.py':'c961bd8acc9f1ba9cffaffd41755ad13601cc4771116090fab661b6d9ee861c5',
    'capture-kit/x87_summary_transition_capture.c':'175a9d19f9bd2996834d24d9b1be142e74d198b955b1eaf36d9432da286092d4',
    BUILD+'x87_summary_transition_capture':'04147ce0b5f38b122dd46c2dfcf7c4b4dca3cbd846040de3873b91910115a296',
    BUILD+'capture.disassembly.txt':'d8e54c1d7e85c5f3e9ba604c7f47c2aa86da26b11d6baaff9327d82ef80fa7b2',
    'tmp/ledger33/current/h1667_capture_static_audit/report.json':'7d242427fc131b1866f3de70459af6ffadc3876a27c6c3ba825ff2ea33a5ec5b'}


def proposals():
    rng=random.Random(0x1668); rows=[]; used=set(); serial=0
    profiles=[(0,0x3f),(0,0x0c)]
    for flags in (1,2,4,8,16,32,0x41,0x7f):
        profiles.extend(((flags,0x3f),(flags,0x0c if flags==0x7f else 0x3f^(flags&0x3f))))
    for flags,masks in profiles:
        for summary in (0,0x80,0x8000,0x8080):
            for kind,e in (('quiet_nan',0x7fff),('signaling_nan',0x7fff),('denormal',0),
                ('pseudo_denormal',0),('polynomial',0x3ffc),('table',0x3ffd),('reduced',0x400a),
                ('out_of_range',0x403e),('empty_stack',0x3ffc),('unnormal',0x3fff),('tiny_bypass',16383-69)):
                while True:
                    sig=rng.getrandbits(63)|1
                    if kind=='quiet_nan': sig|=3<<62
                    elif kind=='signaling_nan': sig=(1<<63)|(sig&((1<<62)-1))
                    elif kind not in ('denormal','unnormal'): sig|=1<<63
                    if sig not in used: break
                used.add(sig)
                for sign in (0,0x8000):
                    rows.append(dict(profile=f'F{flags:02x}_M{masks:02x}_S{summary:04x}',
                        flags=flags,masks=masks,summary=summary,kind=kind,depth=1+serial%8,
                        cc=numerical.cc_bits(serial%16),empty=int(kind=='empty_stack'),
                        operand=f'{e|sign:04x} {sig:016x}'))
                serial+=1
    assert len(rows)==1584==len({r['operand'] for r in rows})
    return rows


def predictions(root,rows):
    values=numerical.numerical_predictions(root,rows); answer=[]
    for insn in ('fsin','fcos'):
        for pc,pcbits in numerical.PC.items():
            for mode,rcbits in numerical.RC.items():
                for row in rows:
                    top=(-row['depth'])&7; tag=((1<<row['depth'])-1)<<(8-row['depth'])
                    if row['empty']: tag &= ~(1<<top)
                    sw=(top<<11)|row['cc']|row['flags']|row['summary']; cw=0x40|row['masks']|pcbits|rcbits
                    se,sig=(int(w,16) for w in row['operand'].split()); n=values[(insn,mode,row['operand'])]
                    # Conditional execution hypothesis: if the opcode executes,
                    # prior exception flags remain sticky but do not change its
                    # fresh arithmetic/early-exception behavior. Do not feed
                    # inconsistent state into H1652 and silently normalize it.
                    fresh=completion.transition(se,sig,insn,enabled=True,
                        before_status=sw&~0x80bf,before_tag=tag,control_word=cw,
                        finite_output=n['numerical_output'],finite_C1=n['numerical_C1'])
                    assert fresh.output is not None and fresh.status_known_mask==0xffff
                    executed=asdict(fresh)
                    executed.update(status_bits=(fresh.status_bits|row['flags'])&~0x8080,
                                    status_known_mask=0x7f7f,delivery=None,response=None)
                    case=f'E{len(answer)+1:06d}'
                    line=(f'{case} {insn} {mode} pc{pc} {row["masks"]:02x} {row["depth"]} '
                          f'{row["cc"]:04x} {row["flags"]:02x} {row["summary"]:04x} {row["empty"]} {row["operand"]}')
                    answer.append(dict(row,case_id=case,instruction=insn,mode=mode,pc=pc,
                        before_CW=cw,requested_SW=sw,before_FTW=tag,capture_line=line,numerical=n,
                        conditional_executed=executed,
                        primary_restore_hypothesis='identity',primary_pending_hypothesis='ES',
                        predicted_restored_summary=row['summary'],predicted_opcode_fault=bool(row['summary']&0x80),
                        unknown_fields=['actual_restored_ES_B','post_execution_ES_B','post_execution_fault_delivery']))
    assert len(answer)==38016==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in answer})
    return answer


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path); a=p.parse_args()
    root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    locks=dict(LOCKS)
    for name,sha in locks.items(): assert digest(root/name)==sha,name
    parent=json.loads((root/numerical.MODEL_DIR/'report.json').read_text())
    for name,sha in parent['sha256']['evidence'].items():
        assert digest(root/name)==sha,name; locks[name]=sha
    operands=proposals(); predicted=predictions(root,operands); out.mkdir(parents=True)
    bank=dict(experiment='h1668_summary_state_proposals',capture_state='SOFTWARE_ONLY_NOT_FROZEN',
        operands=operands,predictions=predicted,unique_operands=len(operands),full_tuples=len(predicted),
        requested_U_ES_B=dict(Counter(f'{int(bool(r["flags"]&~r["masks"]&63))}{int(bool(r["summary"]&128))}{int(bool(r["summary"]&32768))}' for r in operands)),
        hardware_execution='none',private_ledger_access='none',manifest_frozen=False,
        claim_boundary='Predeclared identity restoration and ES pending hypotheses plus conditional executed-output/non-summary-state checks. Unknown summary/delivery fields are not predicted successes. Existing arithmetic and production defaults unchanged.',
        sha256=dict(script=digest(Path(__file__)),evidence=locks))
    save(out/'bank.json',bank)
    print(json.dumps({k:bank[k] for k in ('unique_operands','full_tuples','requested_U_ES_B')},sort_keys=True),flush=True)


if __name__=='__main__': main()
