#!/usr/bin/env python3
"""Independently certify software schedule separators, before new labels."""
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
import h1710_verify_paired_program as I
from h1714_rounding_challenge import prediction as standalone_prediction,c_predictions
from h1721_policy2_challenge import possible_old_generator
from h1719_run_saved_suite import PINS,digest,save


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    scan=root/'tmp/ledger33/current/h1724_schedule_scan'
    assert (scan/'scan.stderr').read_text().endswith('DONE software_inputs=16000000 differences=6\n')
    for name,sha in PINS.items():assert digest(root/name)==sha
    I.constants(root);ops=defaultdict(set)
    for line in (scan/'proposals.txt').read_text().splitlines():
        se,sig,*_=line.split()
        for sign in (0,0x8000):
            for delta in (-1,0,1):
                op=f'{int(se,16)|sign:04x} {int(sig,16)+delta:016x}'
                if not possible_old_generator(op):ops[op].add('schedule_separator' if delta==0 else 'separator_adjacent_control')
    rows=[dict(operand=op,kinds=sorted(k),predictions={},policy1_predictions={}) for op,k in sorted(ops.items())]
    cache={};different=[]
    for insn in ('fsin','fcos','fsincos'):
        for mode in ('rn','rd','ru','rz'):
            c=c_predictions(root/'src/fsincos_skylake',insn,mode,[r['operand'] for r in rows])
            for row,got in zip(rows,c):
                if insn=='fsincos':
                    def pred(policy):
                        value,meta=I.expected(row['operand'],mode,policy,cache)
                        return dict(outputs=list(value),path=meta[0],C1=meta[3] if meta[1] else None)
                    expected=pred('all');old=pred('last');row['policy1_predictions'][mode]=old
                    if old!=expected:different.append(dict(operand=row['operand'],mode=mode,policy2=expected,policy1=old))
                else:expected=standalone_prediction(row['operand'],insn,mode,cache)
                assert got==expected,(insn,mode,row['operand'],got,expected)
                row['predictions'].setdefault(insn,{})[mode]=expected
    out.mkdir(parents=True,exist_ok=False);save(out/'software_differences.json',different)
    evidence={**PINS,**{str(p.relative_to(root)):digest(p) for p in [scan/'scan.stderr',scan/'proposals.txt',
        root/'experiments/h1724_schedule_separator_scan.c',root/'experiments/h1710_paired_program.h',
        root/'experiments/h1721_policy2_challenge.py']}}
    save(out/'bank.json',dict(capture_state='SOFTWARE_ONLY_NOT_FROZEN',candidate_changed=False,hardware_execution='none',operands=rows,
        counts=dict(independent_instruction_rows=len(rows)*12,independent_lane_outputs=len(rows)*16),
        sha256=dict(evidence=evidence,script=digest(Path(__file__)),certificate=digest(out/'software_differences.json'))))
    print(json.dumps(dict(operands=len(rows),independent_policy1_differences=len(different))),flush=True)


if __name__=='__main__':main()
