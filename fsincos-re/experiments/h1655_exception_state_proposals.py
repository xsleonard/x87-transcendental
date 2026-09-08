#!/usr/bin/env python3
"""Software-only future fault-stage/full-condition holdout, NOT a frozen campaign.

One prestate/mask per external operand keeps narrower old tuple keys unique.
No hardware, private-ledger access, or observed-label-driven endpoint selection.
"""
from __future__ import annotations
import argparse
import json
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import h1648_masked_state_proposals as numerical
import h1652_exception_transition as state
from h1640_remaining_scope_freshness import save

LOCKS = {**numerical.LOCKS,
    'experiments/h1652_exception_transition.py': '67d212535064d10b2be5e1d872d6ae7bd55a2f7bfd911c03258ddd3ccf51b1a1',
    'capture-kit/x87_exception_transition_capture.c': '7ac8b93ff9361fd4160d969c3fb4f750f1caa310479e8f282abc8131782e6fb7',
    'tmp/ledger33/current/h1654_capture_build/x87_exception_transition_capture': '1f0be29e0447c4b8390e3edf0b69a78f996d7c2e6293e0588ef7087cb870212e',
    'tmp/ledger33/current/h1654_capture_build/capture.disassembly.txt': 'eebc646467582d364cd6770d90895d7adf735f6f7c5851b9c2a53fa2b975e12f',
}


def proposals():
    profiles = []
    for n in range(16):
        masks = 0x0c | sum((1 << bit) for i, bit in enumerate((0, 1, 4, 5)) if n & (1 << i))
        profiles.append(dict(profile=f'U{n:02d}', masks=masks, cc=numerical.cc_bits((5*n+3)%16),
                             flags=0, pending=0, depth=1+n%8))
    for n in range(16):
        profiles.append(dict(profile=f'M{n:02d}', masks=63, cc=numerical.cc_bits(n),
                             flags=0, pending=0, depth=1+n%8))
    for n, flags in enumerate((1, 2, 4, 8, 16, 32, 0x41, 0x7f)):
        profiles.append(dict(profile=f'S{n:02d}', masks=63, cc=0x4700,
                             flags=flags, pending=0, depth=1+n))
    for bit in range(6):
        profiles.append(dict(profile=f'P{bit:02d}', masks=63^(1<<bit),
                             cc=numerical.cc_bits((3*bit+1)%16), flags=1<<bit,
                             pending=1, depth=1+bit))
    profiles.extend((dict(profile='P06', masks=0, cc=0x4700, flags=63, pending=1, depth=7),
                     dict(profile='P07', masks=31, cc=0, flags=0x7f, pending=1, depth=8)))
    assert len(profiles) == 48
    rng = random.Random(0x1655)
    rows = []
    for profile in profiles:
        payload = rng.getrandbits(63) | 1
        low = payload & ((1 << 62) - 1)
        normal = (1 << 63) | payload
        empty_normal = (1 << 63) | rng.getrandbits(63) | 1
        empty_denormal = rng.getrandbits(63) | 1
        empty_snan = (1 << 63) | rng.getrandbits(62) | 1
        kinds = [('denormal', 0, payload, 0), ('pseudo_denormal', 0, normal, 0),
                 ('equivalent_normal', 1, normal, 0), ('quiet_nan', 0x7fff, (3 << 62) | low, 0),
                 ('signaling_nan', 0x7fff, (1 << 63) | low, 0), ('unnormal', 0x3fff, payload, 0),
                 ('pseudo_nan', 0x7fff, payload, 0), ('tiny_bypass', 16383-69, normal, 0),
                 ('tiny_sticky', 16383-50, normal, 0), ('polynomial', 0x3ffc, normal, 0),
                 ('table', 0x3ffd, normal, 0), ('reduced', 0x400c, normal, 0),
                 ('out_of_range', 0x403e, normal, 0), ('empty_normal', 0x3ffc, empty_normal, 1),
                 ('empty_denormal', 0, empty_denormal, 1), ('empty_snan', 0x7fff, empty_snan, 1)]
        for kind, exponent, sig, empty in kinds:
            for sign in (0, 0x8000):
                rows.append(dict(profile, kind=kind, empty=empty, operand=f'{exponent|sign:04x} {sig:016x}'))
    assert len(rows) == len({r['operand'] for r in rows}) == 1536
    return rows


def predictions(root, rows):
    values = numerical.numerical_predictions(root, rows)
    result = []
    for insn in ('fsin', 'fcos'):
        for pc, pc_bits in numerical.PC.items():
            for mode, rc_bits in numerical.RC.items():
                for row in rows:
                    top = (-row['depth']) & 7
                    tag = ((1 << row['depth']) - 1) << (8-row['depth'])
                    if row['empty']:
                        tag &= ~(1 << top)
                    sw = (top << 11) | row['cc'] | row['flags'] | (0x8080 if row['pending'] else 0)
                    cw = 0x40 | row['masks'] | pc_bits | rc_bits
                    n = values[(insn, mode, row['operand'])]
                    se, sig = (int(w, 16) for w in row['operand'].split())
                    expected = state.transition(se, sig, insn, finite_output=n['numerical_output'],
                        finite_C1=n['numerical_C1'], before_status=sw, before_tag=tag,
                        control_word=cw, experimental_condition_mask=True)
                    alternatives = {}
                    for bit in (8, 9, 10, 14):
                        if not expected.status_known_mask & (1 << bit):
                            initial = (sw >> bit) & 1
                            alternatives[str(bit)] = dict(clear=0, set=1, preserve=initial, invert=1-initial)
                    outputs = None
                    if expected.output is None:
                        outputs = state.wrapped_underflow_alternatives(se, sig, insn, mode)
                    case_id = f'E{len(result)+1:05d}'
                    capture_line = (f'{case_id} {insn} {mode} pc{pc} {row["masks"]:02x} {row["depth"]} '
                                    f'{row["cc"]:04x} {row["flags"]:02x} {row["pending"]} {row["empty"]} {row["operand"]}')
                    result.append(dict(row, case_id=case_id, instruction=insn, mode=mode, pc=pc,
                        before_CW=cw, before_SW=sw, before_FTW=tag, expected=asdict(expected), numerical=n,
                        expected_A_VALID=int(expected.delivery != 'at_instruction'),
                        expected_FAULT=int(expected.delivery != 'none'),
                        expected_FAULT_AT={'none': 0, 'at_instruction': 1, 'at_next_wait': 2}[expected.delivery],
                        expected_TRAP=0 if expected.delivery == 'none' else 16,
                        unmodeled_bit_alternatives=alternatives, unmodeled_output_alternatives=outputs,
                        relations='All deeper raw registers preserved. A equals F for delivery at next wait; B equals F for pending delivery, including recorded FOP/FIP/FDP. Invalid A/F snapshots receive no credit.',
                        capture_line=capture_line))
    assert len(result) == len({(r['instruction'], r['mode'], r['pc'], r['operand']) for r in result}) == 36864
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    digest = numerical.numerical.candidate.table.records.digest
    locks = dict(LOCKS)
    for name, sha in locks.items():
        assert digest(root/name) == sha, name
    parent = json.loads((root/numerical.MODEL_DIR/'report.json').read_text())
    for name, sha in parent['sha256']['evidence'].items():
        assert digest(root/name) == sha, name
        locks[name] = sha
    rows = proposals(); predicted = predictions(root, rows)
    counts = dict(unique_operands=len(rows), full_tuples=len(predicted),
                  unique_significands=len({r['operand'].split()[1] for r in rows}),
                  profiles=48, null_output_predictions=sum(r['expected']['output'] is None for r in predicted),
                  full_SW_predictions=sum(r['expected']['status_known_mask']==0xffff for r in predicted))
    bank = dict(experiment='h1655_exception_state_proposals', capture_state='SOFTWARE_ONLY_NOT_FROZEN',
        operands=rows, predictions=predicted, counts=counts,
        deliveries=dict(Counter(r['expected']['delivery'] for r in predicted)),
        kind_counts=dict(Counter(r['kind'] for r in rows)),
        masks_scope='All16 IM/DM/UM/PM combinations with ZM/OM masked; pending faults from each of all six flags; separately all16 initial CC and eight sticky/SF profiles.',
        candidate_arithmetic_changed=False, hardware_execution='none', private_ledger_access='none',
        freshness='NOT AUDITED. Reject all prior-visible significands before freeze; new masks/state do not permit older operand tuples.',
        claim_boundary='Future predeclared full-CC holdout and manual-derived fault staging. Unmasked underflow output stays null with discriminators, not a fabricated prediction. Zero/infinity absent. No full-state or all-input silicon proof.',
        sha256=dict(script=digest(Path(__file__)), evidence=locks, binaries=parent['sha256']['binaries']))
    out.mkdir(parents=True); save(out/'bank.json', bank)
    print(json.dumps(dict(counts=counts, deliveries=bank['deliveries']), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
