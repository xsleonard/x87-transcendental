#!/usr/bin/env python3
"""Independent raw parser, arithmetic replay and exception-stage algebra.

No imports of H1652's transition model or H1657's parser/scorer. A failed
frozen prediction is preserved and independently classified, never repaired.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import h1638_tiny_c_transfer as cmodel
import h1636_retained_rz_pc_transfer as arithmetic
from h1640_remaining_scope_freshness import save

KIT = 'transfer-tests/h1656/'
SCORE = 'tmp/ledger33/current/h1657_score_exception_state/'
MODELS = 'tmp/ledger33/current/h1638_tiny_c_transfer/'
LOCKS = {
    KIT+'FREEZE.json': '5cf29bfe745c0752c6d1f6556517cbd29619f2409c81f1245820c7e67e3050a5',
    KIT+'manifest.json': 'abcb6a74b0aed0c0d41468a183f078cb7258ae622f42603e97b1ca94578901b6',
    'experiments/h1657_score_exception_state.py': '40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def predict(row, number, c1):
    se, sig = (int(w, 16) for w in row['operand'].split())
    e, j = se & 0x7fff, sig >> 63
    encoded = f'{se:04x}:{sig:016x}'
    top = (8-row['depth']) % 8
    tag = ((1 << row['depth'])-1) << (8-row['depth'])
    if row['empty']:
        tag &= ~(1 << top)
    before = (top << 11) | row['cc'] | row['flags'] | (0x8080 if row['pending'] else 0)
    masks = row['masks']
    assert bool(before & ~masks & 63) == bool(row['pending'])
    if row['empty']:
        cls = 'empty_stack'
    elif e and not j:
        cls = 'unsupported'
    elif e == 0x7fff:
        assert sig != (1 << 63)
        cls = 'quiet_nan' if sig & (1 << 62) else 'signaling_nan'
    elif not e:
        assert sig
        cls = 'pseudo_denormal' if j else 'denormal'
    else:
        cls = 'normal_out_of_range' if e >= 0x403e else 'normal_in_range'
    sf = before & 0x40
    if row['pending']:
        return dict(encoding_class=cls, output=encoded, response='MF_BEFORE', delivery='at_instruction',
            new_exception_flags=0, C1=(before>>9)&1, C2=(before>>10)&1, status_bits=before,
            status_known_mask=65535, physical_abridged_tag=tag, top=top)
    invalid = cls in ('empty_stack', 'unsupported', 'signaling_nan')
    early = 1 if invalid and not masks & 1 else 2 if cls in ('denormal', 'pseudo_denormal') and not masks & 2 else 0
    if early:
        known = 65535 ^ 0x4700
        c1 = None
        if row['empty']:
            sf = 0x40; c1 = 0; known |= 0x200
        sw = (top<<11) | (before&63) | sf | early | 0x8080
        return dict(encoding_class=cls, output=encoded, response='MF_AFTER', delivery='at_next_wait',
            new_exception_flags=early, C1=c1, C2=None, status_bits=sw, status_known_mask=known,
            physical_abridged_tag=tag, top=top)
    c2, response = 0, 'OK'
    if row['empty']:
        value, new, c1 = 'ffff:c000000000000000', 1, 0
        sf = 0x40; tag |= 1 << top
    elif cls == 'unsupported':
        value, new, c1 = 'ffff:c000000000000000', 1, 0
    elif e == 0x7fff:
        value, new, c1 = f'{se:04x}:{sig|(1<<62):016x}', int(not sig & (1<<62)), 0
    elif not e:
        value, new, c1 = number, 0x22 | (0x10 if row['instruction']=='fsin' and not j else 0), 0
    elif e >= 0x403e:
        value, new, c1, c2, response = encoded, 0, 0, 1, 'C2'
    else:
        value, new = number, 0x20
    assert c1 in (0, 1)
    triggered = new & ~masks & 63
    assert not triggered & 15
    sw = (top<<11) | (before&63) | sf | new | (c1<<9) | (c2<<10) | (before&0x4100)
    known = 65535
    if triggered:
        sw |= 0x8080; response = 'MF_AFTER'
    if triggered & 0x10:
        assert not e and not j and row['instruction']=='fsin'
        value, c1, c2 = None, None, None
        known ^= 0x4700; sw &= ~0x4700
    return dict(encoding_class=cls, output=value, response=response,
        delivery='at_next_wait' if triggered else 'none', new_exception_flags=new,
        C1=c1, C2=c2, status_bits=sw, status_known_mask=known, physical_abridged_tag=tag, top=top)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items():
        assert digest(root/name) == sha, name
    freeze = json.loads((root/KIT/'FREEZE.json').read_text())
    for name, sha in freeze['sha256']['evidence'].items():
        assert digest(root/name) == sha, name
    opened = json.loads((root/KIT/'OPENED.json').read_text())
    assert opened['capture_state'] == 'OPENED_ONCE' and opened['freeze_sha256'] == LOCKS[KIT+'FREEZE.json']
    assert digest(root/SCORE/'report.json') == opened['report_sha256']
    score_report = json.loads((root/SCORE/'report.json').read_text())
    assert digest(root/SCORE/'score.json') == score_report['sha256']['score']
    raw_path = root/KIT/'hardware-output/state-output.txt'
    assert digest(raw_path) == score_report['sha256']['raw_output']
    previous = {r['case_id']: r for r in json.loads((root/SCORE/'score.json').read_text())}
    rows = json.loads((root/KIT/'manifest.json').read_text())
    lines = raw_path.read_text().splitlines(); assert len(lines) == len(rows) == 36864
    arithmetic.initialize_proof(root)
    model_report = json.loads((root/MODELS/'report.json').read_text())
    numbers = {}; count = Counter()
    for insn in ('fsin', 'fcos'):
        for mode in ('rn', 'rd', 'ru', 'rz'):
            operands = list(dict.fromkeys(r['operand'] for r in rows if r['instruction']==insn and r['mode']==mode))
            assert len(operands) == 1536
            reference = None
            for label in ('candidate_O0', 'candidate_O2', 'candidate_O3', 'candidate_ubsan'):
                binary = root/MODELS/label
                assert digest(binary) == model_report['sha256']['binaries'][label]
                values, metadata, _ = cmodel.run(binary, insn, mode, operands)
                if reference is None:
                    reference = values, metadata
                assert reference == (values, metadata)
                count['four_build_software_points'] += len(operands)
            values, metadata = reference
            for i, op in enumerate(operands):
                meta = metadata.get(i); small = cmodel.spec.evaluate(op, insn, mode)
                if meta and meta['lane'] in ('polynomial', 'table'):
                    value, c1, _, _ = arithmetic.verify_hit(op, insn, mode, meta)
                else:
                    value, c1 = small['output'], small['C1']
                assert value == values[i]
                numbers[(insn, mode, op)] = value, c1, meta
                count['independent_arithmetic_points'] += 1
    recomputed = []; errors = Counter(); misses = []
    state_fields = ('cw', 'sw', 'top', 'ftw', *(f'r{i}' for i in range(8)), 'fop', 'fip', 'fdp')
    for row, line in zip(rows, lines):
        words = line.lower().split()
        assert len(words) == 60 and all(w.count('=') == 1 for w in words)
        parts = [w.split('=') for w in words]; fields = dict(parts)
        assert len(fields) == 60 and fields['case'] == row['case_id'].lower()
        number, c1, meta = numbers[(row['instruction'], row['mode'], row['operand'])]
        assert meta == row['numerical']['metadata']
        expected = predict(row, number, c1)
        assert expected == row['expected'], row['case_id']
        top = (8-row['depth'])%8
        sw = (top<<11) | row['cc'] | row['flags'] | (0x8080 if row['pending'] else 0)
        cw = 0x40 | row['masks'] | {24:0,53:0x200,64:0x300}[row['pc']] | {'rn':0,'rd':0x400,'ru':0x800,'rz':0xc00}[row['mode']]
        tag = ((1<<row['depth'])-1)<<(8-row['depth'])
        if row['empty']:
            tag &= ~(1<<top)
        before = dict(insn=row['instruction'], mode=row['mode'], pc=f'pc{row["pc"]}', masks=f'{row["masks"]:02x}',
            depth=str(row['depth']), cc=f'{row["cc"]:04x}', flags=f'{row["flags"]:02x}', pending=str(row['pending']),
            empty=str(row['empty']), b_cw=f'{cw:04x}', b_sw=f'{sw:04x}', b_top=str(top), b_ftw=f'{tag:02x}',
            b_r0=row['operand'].replace(' ',':'))
        for i in range(1,row['depth']):
            before[f'b_r{i}'] = f'3fff:{(1<<63)+8*i:016x}'
        valid, fault, site, trap = (int(fields[k]) for k in ('a_valid','fault','fault_at','trap'))
        assert (valid,fault,site) in ((1,0,0),(1,1,2),(0,1,1))
        want = {'none':(1,0,0,0),'at_next_wait':(1,1,2,16),'at_instruction':(0,1,1,16)}[expected['delivery']]
        selected = 'a' if valid else 'f'
        actual_sw = int(fields[selected+'_sw'],16)
        exact = dict(before=all(fields[k]==v for k,v in before.items()), delivery=(valid,fault,site,trap)==want,
            status=((actual_sw^expected['status_bits'])&expected['status_known_mask'])==0,
            CW=int(fields[selected+'_cw'],16)==cw, TOP=int(fields[selected+'_top'])==top,
            FTW=int(fields[selected+'_ftw'],16)==expected['physical_abridged_tag'],
            deeper=all(fields[selected+f'_r{i}']==fields[f'b_r{i}'] for i in range(1,8)))
        if expected['output'] is not None:
            exact['output'] = fields[selected+'_r0']==expected['output']
        if fault:
            reference = 'b' if site==1 else 'a'
            exact['fault_snapshot_relation'] = all(fields['f_'+k]==fields[reference+'_'+k] for k in state_fields)
        assert exact == previous[row['case_id']]['exact'], row['case_id']
        bad = [k for k,v in exact.items() if not v]
        item = dict(case_id=row['case_id'], expected=expected, exact=exact,
                    actual_output=fields[selected+'_r0'], actual_SW=actual_sw, actual_delivery_site=site)
        recomputed.append(item)
        if bad:
            misses.append(row['case_id'])
            errors.update(bad)
        count['independent_raw_rows'] += 1
    assert len(misses) == score_report['miss_rows']
    out.mkdir(parents=True); save(out/'recomputed.json', recomputed)
    report = dict(experiment='h1658_independent_exception_state',
        status='INDEPENDENT_FALSIFICATION_CONFIRMED' if misses else 'PASS_INDEPENDENT_FROZEN_STATE',
        counts=dict(count), miss_rows=len(misses), errors=dict(errors), miss_case_ids=misses,
        hardware_execution='none', private_ledger_access='none', production_or_paper_change='none',
        claim_boundary='Independent parser, class/exception algebra and exact arithmetic confirm the original scoring, including failures. No post-hoc prediction repair, extra hardware observation or all-input silicon proof.',
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS, score_report=digest(root/SCORE/'report.json'),
                    raw_output=digest(raw_path), recomputed=digest(out/'recomputed.json')))
    save(out/'report.json', report)
    print(json.dumps({k:report[k] for k in ('status','counts','miss_rows','errors')},sort_keys=True),flush=True)


if __name__ == '__main__':
    main()
