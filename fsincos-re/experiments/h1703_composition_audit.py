#!/usr/bin/env python3
"""Actual C numerical backend plus partial state composition; retained replay.

This audits integration and lazy execution, not new silicon behavior. Frozen
historical unknowns/failures stay historical; no hardware tuple is repeated.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
import h1703_composed_transition as bridge
import h1638_tiny_c_transfer as cmodel
import h1636_retained_rz_pc_transfer as independent
from h1640_remaining_scope_freshness import save
from h1650_score_masked_state import digest

MODEL = 'tmp/ledger33/current/h1638_tiny_c_transfer/'
LOCKS = {
    'experiments/h1645_masked_status_model.py': 'd00bbf0adf069be0e2553712c45df96eb1e457dfe74b8403e27b61f69eda0fc5',
    'experiments/h1652_exception_transition.py': '67d212535064d10b2be5e1d872d6ae7bd55a2f7bfd911c03258ddd3ccf51b1a1',
    'experiments/h1660_scalar_state_completion.py': 'ca97e612effca75c47d592e9bdaca360c95f219cee8a736072b623c464dd17c9',
    'experiments/h1659_wrapped_underflow.py': 'e80ed534a8b1300fe68c6f6e8c9be0fb569797311e4534ebca4f63bb6046b004',
    'experiments/h1638_tiny_c_transfer.py': 'db99dc020ab7372af7f8018a11c4e81a7c73afd227c4dccbbcc080d3b38a4fd1',
    'experiments/h1636_retained_rz_pc_transfer.py': '9d44c92b5c6267752da7bab906e160ae82bb1eda338f93c86c8e7732adb45707',
    MODEL+'report.json': 'db6c8cbc1e0e2c9acdb54da5e1e381407a6b8c5f6f62cc7b1c52c4d90f8510e0',
}
HISTORY = {
    'h1649': ('00ba74c08d8f4154cfdc74e0fdd0bd876dca2b69282e6656c23d5a3f9b1c19ee', 'a17f677286efed87d7563c8ed76b37cda314598b9e9db218d365f217c17f67ef', '49ae75da9a8589672b5547fa82c795e10310f946199e1299317a7ab73fb89820'),
    'h1656': ('abcb6a74b0aed0c0d41468a183f078cb7258ae622f42603e97b1ca94578901b6', '132a1eefcdb6855922aaa4ab2f88d262d2a358547e155e988eaa151074efbecb', '1074ffca4a37a5d217247603c3d8439ef2a19238c42612b011b0d30d0dd4d555'),
    'h1662': ('90ddbdf8ec19f3be57307d061a5812e57734f25b22dc08d66303427a90264e45', 'ef993c7a7f7c315f967bc31da9074f85b2810d0f574a946f86d89c131ee062c7', '5d56fc2803d9a0b4d60ece5d79ab766c7c1e0de660e984eb1c8c69a0aaab6321'),
}


def context(row):
    return dict(before_status=row['before_SW'], before_tag=row['before_FTW'], control_word=row['before_CW'])


def key(row):
    se, sig = (int(w, 16) for w in row['operand'].split())
    return se, sig, row['instruction'], bridge.MODES[(row['before_CW'] >> 10) & 3]


def synthetic():
    # Encoding classes plus all three arithmetic paths and exact thresholds.
    operands = ['0000 0000000000000000', '8000 0000000000000000',
        '0000 0000000000000001', '8000 000000000000000f',
        '0000 8000000000000001', '0001 8000000000000001',
        '0001 0000000000000000', '7fff 8000000000000000',
        'ffff 8000000000000000', '7fff 8000000000000001',
        '7fff c000000000000001', '3fba 8000000000000000',
        '3fbb 8000000000000000', '3fdf 8000000000000000',
        '3ffd 8000000000000000', '3ffe c90fdaa22168c234',
        '403d ffffffffffffffff', '403e 8000000000000000']
    for index, operand in enumerate(operands):
        for instruction in ('fsin', 'fcos'):
            for rc in range(4):
                for pc in (0, 0x200, 0x300):
                    for masks in range(64):
                        for flags in (0, 1, 2, 16, 32, 63):
                            # Deterministically cover TOP, condition bits,
                            # existing SF and empty/occupied without pretending
                            # this finite bank spans all arbitrary histories.
                            top = (index + rc + masks) & 7
                            empty = (flags + masks + index) % 5 == 0
                            tag = 0xff & ~(1 << top) if empty else 0xff
                            cc = ((masks >> 2) & 1) * 0x100 | ((masks >> 3) & 1) * 0x200 | ((masks >> 4) & 1) * 0x400 | ((masks >> 5) & 1) * 0x4000
                            sw = (top << 11) | cc | flags | (0x40 if masks & 1 else 0)
                            if flags & ~masks: sw |= 0x8080
                            yield dict(operand=operand, instruction=instruction, before_CW=0x40|pc|(rc<<10)|masks,
                                before_SW=sw, before_FTW=tag)


def collect_numbers(root, rows, output):
    groups = defaultdict(set)
    for row in rows:
        se, sig, insn, mode = key(row)
        if bridge.plan(se, sig, insn, **context(row)) == 'number':
            groups[(insn, mode)].add(f'{se:04x} {sig:016x}')
    report = json.loads((root/MODEL/'report.json').read_text())
    independent.initialize_proof(root)
    numbers = {}; counts = Counter(); evidence = []
    for (insn, mode), ops in sorted(groups.items()):
        operands = sorted(ops); reference = None
        for build in ('candidate_O0', 'candidate_O2', 'candidate_O3', 'candidate_ubsan'):
            binary = root/MODEL/build
            assert digest(binary) == report['sha256']['binaries'][build]
            values, metadata, stdout = cmodel.run(binary, insn, mode, operands)
            if reference is None: reference = values, metadata
            assert reference == (values, metadata)
            counts['C_build_comparisons'] += len(operands)
            evidence.append(dict(instruction=insn, mode=mode, build=build, rows=len(operands),
                binary_sha256=digest(binary), stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest()))
        values, metadata = reference
        for i, operand in enumerate(operands):
            meta = metadata.get(i)
            if meta and meta['lane'] in ('polynomial', 'table'):
                number, c1, _, _ = independent.verify_hit(operand, insn, mode, meta)
            else:
                evaluated = cmodel.spec.evaluate(operand, insn, mode)
                number, c1 = evaluated['output'], evaluated['C1']
            assert number == values[i], (operand, number, values[i])
            se, sig = (int(w,16) for w in operand.split())
            numbers[(se,sig,insn,mode)] = bridge.Number('C2' if number == 'C2' else 'OK', None if number == 'C2' else number, c1)
            counts['independent_numerical_keys'] += 1
            counts['lane_'+(meta['lane'] if meta else 'special_or_range')] += 1
    save(output/'numerical_backend.json', dict(counts=dict(counts), evidence=evidence))
    return numbers, dict(counts)


def execute(row, numbers):
    se,sig,insn,mode = key(row); calls=[]
    def backend(*args):
        calls.append(args)
        return numbers[args]
    result = bridge.compose(se,sig,insn,backend,enabled=True,**context(row))
    assert calls == ([(se,sig,insn,mode)] if result.numerical_requested else [])
    # Cross-check request/writeback against the independently implemented
    # existing transition result, not merely the bridge's own planning flag.
    tr = result.transition
    early = tr.delivery == 'at_next_wait' and tr.new_exception_flags in (1, 2)
    pending = tr.delivery == 'at_instruction'
    expected_request = not (pending or early or tr.encoding_class == 'empty_stack')
    expected_writeback = not (pending or early or tr.response == 'C2')
    assert result.numerical_requested == expected_request
    assert result.writeback == expected_writeback
    return result


def negative_controls():
    def poison(*args): raise AssertionError('Numerics must not run here')
    tests = []
    for name, args in (
        ('default_off', dict()),
        ('reserved_PC', dict(enabled=True, control_word=0x017f)),
        ('incoherent_summary', dict(enabled=True, before_status=0xb880))):
        try: bridge.compose(0x3ffd,1<<63,'fsin',poison,**args)
        except NotImplementedError: tests.append(name)
        else: raise AssertionError(name)
    # Unknown C0/C3 (and infinity C2) remain unknown, not zero-filled claims.
    unknowns=[]
    for se,sig,value in ((0,0,'0000:0000000000000000'),(0x7fff,1<<63,'ffff:c000000000000000')):
        result=bridge.compose(se,sig,'fsin',lambda *a:bridge.Number('OK',value,None),enabled=True)
        assert result.transition.status_known_mask != 0xffff
        unknowns.append(asdict(result))
    # A pseudo-denormal and its equal-valued E=1 alias differ before arithmetic
    # when DM is unmasked; canonicalizing before state classification is wrong.
    before=dict(before_status=0x3800,before_tag=0x80,control_word=0x037d)
    a=bridge.compose(0,(1<<63)+1,'fsin',poison,enabled=True,**before)
    assert not a.writeback and not a.numerical_requested and a.transition.new_exception_flags==2
    b=bridge.compose(1,(1<<63)+1,'fsin',lambda *a:bridge.Number('OK','0001:8000000000000001',0),enabled=True,**before)
    assert b.writeback and b.numerical_requested and b.transition.new_exception_flags==0x20
    return dict(rejected=tests, unknown_masks_preserved=unknowns, raw_class_negative_pair=[asdict(a),asdict(b)])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    args=p.parse_args();root,out=args.root.resolve(),args.output_dir.resolve();assert not out.exists()
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    history={};evidence=dict(LOCKS)
    for tag, hashes in HISTORY.items():
        directory=root/'transfer-tests'/tag
        for name,sha in zip(('manifest.json','OPENED.json','hardware-output/state-output.txt'),hashes):
            assert digest(directory/name)==sha
            evidence[str((directory/name).relative_to(root))]=sha
        assert json.loads((directory/'OPENED.json').read_text())['capture_state']=='OPENED_ONCE'
        history[tag]=json.loads((directory/'manifest.json').read_text())
    software=list(synthetic()); all_rows=software+[row for rows in history.values() for row in rows]
    out.mkdir(parents=True)
    numbers,numeric_counts=collect_numbers(root,all_rows,out)
    neg=negative_controls();save(out/'negative_controls.json',neg)
    counts=Counter(); fingerprint=hashlib.sha256()
    for row in software:
        result=execute(row,numbers); tr=result.transition
        # This is composition equivalence to the existing partial model,
        # not an independent silicon oracle or a completed unknown-bit mask.
        se,sig,insn,mode=key(row); numeric=numbers.get((se,sig,insn,mode))
        reference=bridge.state.transition(se,sig,insn,enabled=True,
            finite_output=numeric.output if numeric else None,finite_C1=numeric.C1 if numeric else None,**context(row))
        assert tr==reference
        counts['rows']+=1;counts['stage_'+result.commit_kind]+=1
        counts['numerical_requests']+=result.numerical_requested
        counts['unknown_mask_rows']+=tr.status_known_mask!=0xffff
        fingerprint.update((json.dumps(asdict(result),sort_keys=True)+'\n').encode())
    save(out/'software.json',dict(counts=dict(counts),composed_rows_sha256=fingerprint.hexdigest()))
    banks=[]
    for tag,rows in history.items():
        lines=(root/'transfer-tests'/tag/'hardware-output/state-output.txt').read_text().splitlines()
        assert len(lines)==len(rows); bank=Counter();misses=[];stamp=hashlib.sha256()
        for row,line in zip(rows,lines):
            result=execute(row,numbers);tr=result.transition
            tokens=[w.lower().split('=') for w in line.split()]; raw=dict(tokens)
            assert len(raw)==len(tokens) and raw['case']==row['case_id'].lower()
            assert raw['insn']==row['instruction'] and raw['mode']==key(row)[3]
            assert int(raw['b_cw'],16)==row['before_CW'] and int(raw['b_sw'],16)==row['before_SW'] and int(raw['b_ftw'],16)==row['before_FTW']
            assert raw['b_r0']==row['operand'].replace(' ',':')
            selected='a' if tag=='h1649' or int(raw['a_valid']) else 'f'
            exact=dict(output=raw[selected+'_r0']==tr.output,
                known_status=((int(raw[selected+'_sw'],16)^tr.status_bits)&tr.status_known_mask)==0,
                TOP=int(raw[selected+'_top'])==tr.top,FTW=int(raw[selected+'_ftw'],16)==tr.physical_abridged_tag,
                CW=raw[selected+'_cw']==raw['b_cw'],deeper=all(raw[selected+f'_r{i}']==raw[f'b_r{i}'] for i in range(1,8)))
            if tag!='h1649':
                want={'none':(1,0,0),'at_next_wait':(1,1,2),'at_instruction':(0,1,1)}[tr.delivery]
                exact['delivery']=tuple(int(raw[k]) for k in ('a_valid','fault','fault_at'))==want
            if not all(exact.values()):misses.append(dict(case_id=row['case_id'],exact=exact,composed=asdict(result)))
            bank['rows']+=1;bank['writebacks']+=result.writeback;bank['numerical_requests']+=result.numerical_requested
            bank['stage_'+result.commit_kind]+=1;bank['known_full_SW_rows']+=tr.status_known_mask==65535
            bank['original_frozen_unknown_output_rows']+=row['expected']['output'] is None
            stamp.update((json.dumps(dict(case_id=row['case_id'],result=asdict(result),exact=exact),sort_keys=True)+'\n').encode())
        saved=dict(campaign=tag,counts=dict(bank),misses=misses,composed_rows_sha256=stamp.hexdigest())
        save(out/(tag+'.json'),saved);banks.append(saved)
        print(json.dumps(dict(campaign=tag,counts=dict(bank),misses=len(misses))),flush=True)
    report=dict(experiment='h1703_composition_audit',status='PASS_PARTIAL_STATE_COMPOSITION' if not any(b['misses'] for b in banks) else 'COMPOSITION_MISMATCH',
        software=dict(counts),numerical_backend=numeric_counts,retained_banks=[dict(campaign=b['campaign'],counts=b['counts'],misses=len(b['misses'])) for b in banks],
        boundary='Existing numerical graph composed with an explicitly partial/default-off state model. Retained replay, not new capture or retroactive frozen success; historical96 unknown underflow outputs stay historical. PC01/incoherent summary reject; zero/infinity masks remain partial. No universal silicon or full-state closure.',
        hardware_execution='none',private_ledger_access='none',new_labels_opened=False,production_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)),bridge=digest(Path(bridge.__file__)),evidence=evidence))
    save(out/'report.json',report);print(report['status'],flush=True)


if __name__=='__main__':main()
