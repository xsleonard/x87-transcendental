#!/usr/bin/env python3
"""Software-only adversaries for normalization regions and invalid C0=0.

Every candidate precedes freshness screening and hardware. Selection may only
remove prior-visible signatures, never select according to observed outcomes.
"""
from __future__ import annotations
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

LOCKS = {**numerical.LOCKS, **completion.LOCKS,
    'experiments/h1660_scalar_state_completion.py': 'ca97e612effca75c47d592e9bdaca360c95f219cee8a736072b623c464dd17c9',
    'capture-kit/x87_exception_transition_capture.c': '7ac8b93ff9361fd4160d969c3fb4f750f1caa310479e8f282abc8131782e6fb7',
    'tmp/ledger33/current/h1654_capture_build/x87_exception_transition_capture': '1f0be29e0447c4b8390e3edf0b69a78f996d7c2e6293e0588ef7087cb870212e',
    'tmp/ledger33/current/h1654_capture_build/capture.disassembly.txt': 'eebc646467582d364cd6770d90895d7adf735f6f7c5851b9c2a53fa2b975e12f',
}


def proposals():
    rng = random.Random(0x1661)
    rows = []; used = set()
    def add(row, se, sig):
        for sign in (0, 0x8000):
            op = f'{se|sign:04x} {sig:016x}'
            assert op not in used
            used.add(op); rows.append(dict(row, operand=op))
    serial = 0
    for shift in range(1, 64):
        k = 63-shift; lo, hi = 1<<k, (1<<(k+1))-1; mid=(lo+hi)//2
        choices = [('low',lo),('low_plus1',lo+1),('low_plus2',lo+2),('low_plus3',lo+3),
                   ('middle',mid),('middle_plus1',mid+1),('high_minus3',hi-3),
                   ('high_minus2',hi-2),('high_minus1',hi-1),('high',hi)]
        choices += [(f'random{i}',rng.randint(lo,hi)) for i in range(8)]
        unique = set()
        for shape, sig in choices:
            if not lo <= sig <= hi or sig in unique:
                continue
            unique.add(sig)
            masks = (0x0e,0x0f,0x2e,0x2f)[serial%4]
            cc = numerical.cc_bits(rng.randrange(16))
            row = dict(profile=f'N{shift:02d}_{shape}', probe='normalization', kind='true_denormal',
                shape=shape, normalization_shift=shift, masks=masks, cc=cc, flags=0,
                pending=0, depth=1+serial%8, empty=0)
            add(row,0,sig); serial+=1
    for masks in (0x3e, 0x0c):
        for pattern in range(16):
            for kind, exponent, empty in (('unnormal',0x3fff,0),('pseudo_nan',0x7fff,0),
                ('signaling_nan',0x7fff,0),('empty_normal',0x3ffc,1),('empty_denormal',0,1),('empty_snan',0x7fff,1)):
                while True:
                    sig = rng.getrandbits(63)|1
                    if kind in ('signaling_nan','empty_snan'):
                        sig = (1<<63)|(sig&((1<<62)-1))
                    elif kind == 'empty_normal':
                        sig |= 1<<63
                    if f'{exponent:04x} {sig:016x}' not in used:
                        break
                row = dict(profile=f'I{masks:02x}_{pattern:02d}_{kind}', probe='invalid_C0',kind=kind,
                    shape='independent_payload',normalization_shift=None,masks=masks,
                    cc=numerical.cc_bits(pattern),flags=0,pending=0,depth=1+(pattern+serial)%8,empty=empty)
                add(row,exponent,sig); serial+=1
    assert len(rows) == len(used)
    return rows


def predictions(root, rows):
    values = numerical.numerical_predictions(root, rows)
    answer=[]
    for insn in ('fsin','fcos'):
        for pc,pc_bits in numerical.PC.items():
            for mode,rc_bits in numerical.RC.items():
                for row in rows:
                    top=(-row['depth'])&7
                    tag=((1<<row['depth'])-1)<<(8-row['depth'])
                    if row['empty']: tag &= ~(1<<top)
                    before=(top<<11)|row['cc']|row['flags']; cw=0x40|row['masks']|pc_bits|rc_bits
                    se,sig=(int(w,16) for w in row['operand'].split())
                    n=values[(insn,mode,row['operand'])]
                    result=completion.transition(se,sig,insn,enabled=True,finite_output=n['numerical_output'],
                        finite_C1=n['numerical_C1'],before_status=before,before_tag=tag,control_word=cw)
                    assert result.output is not None and result.status_known_mask==0xffff
                    case_id=f'C{len(answer)+1:06d}'
                    line=(f'{case_id} {insn} {mode} pc{pc} {row["masks"]:02x} {row["depth"]} '
                          f'{row["cc"]:04x} {row["flags"]:02x} 0 {row["empty"]} {row["operand"]}')
                    answer.append(dict(row,case_id=case_id,instruction=insn,mode=mode,pc=pc,
                        before_CW=cw,before_SW=before,before_FTW=tag,expected=asdict(result),numerical=n,
                        expected_A_VALID=1,expected_FAULT=int(result.delivery!='none'),
                        expected_FAULT_AT=2 if result.delivery!='none' else 0,
                        expected_TRAP=16 if result.delivery!='none' else 0,
                        unmodeled_bit_alternatives={},unmodeled_output_alternatives=None,capture_line=line,
                        relations='Full SW/output predicted before capture. Deeper registers unchanged; delivered fault state equals the no-wait snapshot including FOP/FIP/FDP.'))
    assert len(answer)==24*len(rows)==len({(r['instruction'],r['mode'],r['pc'],r['operand']) for r in answer})
    return answer


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path); p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(); root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    locks=dict(LOCKS)
    for name,sha in locks.items(): assert digest(root/name)==sha,name
    parent=json.loads((root/numerical.MODEL_DIR/'report.json').read_text())
    for name,sha in parent['sha256']['evidence'].items():
        assert digest(root/name)==sha,name
        locks[name]=sha
    rows=proposals(); answer=predictions(root,rows)
    counts=dict(unique_operands=len(rows),full_tuples=len(answer),
        unique_significands=len({r['operand'].split()[1] for r in rows}),
        probe_operands=dict(Counter(r['probe'] for r in rows)),
        normalization_shift_operands=dict(Counter(r['normalization_shift'] for r in rows if r['probe']=='normalization')))
    out.mkdir(parents=True)
    bank=dict(experiment='h1661_normalization_and_c0_proposals',capture_state='SOFTWARE_ONLY_NOT_FROZEN',
        counts=counts,operands=rows,predictions=answer,hardware_execution='none',private_ledger_access='none',
        production_or_paper_change='none',freshness='NOT AUDITED. Reject prior-visible significands before freeze; excluded shifts must be reported, not credited.',
        claim_boundary='All proposed outputs/full SW are predictions of a default-off completion, not established silicon laws. Proposal coverage is not hardware coverage.',
        sha256=dict(script=digest(Path(__file__)),evidence=locks,binaries=parent['sha256']['binaries']))
    save(out/'bank.json',bank)
    print(json.dumps(dict(counts=counts),sort_keys=True),flush=True)


if __name__=='__main__': main()
