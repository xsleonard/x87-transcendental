#!/usr/bin/env python3
"""Primary plus independent integer-ROM/raw-state checks for H1694.

The independent predictor/parser below does not call the numerical graph,
H1660 transition, or H1657 parser. Preflight is required before freezing.
Unknown pointers are not predicted. Frozen failures are never rewritten.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import h1657_score_exception_state as primary
import h1657_scorer_preflight as synthetic
from h1640_remaining_scope_freshness import save

ROM_SHA = '2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97'
PRIMARY_SHA = '40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808'


def rom_words(root):
    path = root / 'src/p5_rom_constants.h'
    assert primary.digest(path) == ROM_SHA
    pattern = r'\{ (\d+), \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \}, \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull \} \}'
    answer = {}
    for b, *parts in re.findall(pattern, path.read_text()):
        pair = []
        for offset in (0, 4):
            sign, exponent, high, low = parts[offset:offset + 4]
            assert sign == '0'
            pair.append((int(exponent), (int(high, 16) << 64) | int(low, 16)))
        answer[int(b)] = pair
    assert len(answer) == 8
    return answer


def predict(row, rom):
    se, sig = (int(word, 16) for word in row['operand'].split())
    sign, e = se >> 15, (se & 0x7fff) - 16383
    assert 1 <= se & 0x7fff < 0x7fff and 1 << 63 <= sig < 1 << 64
    n = int(row['instruction'] == 'fcos')
    if e < -1 or (e == -1 and sig < 0xc90fdaa22168c234):
        # For direct centers r=b/64, so b=sig*2^(e-57), exactly.
        b, discarded = divmod(sig, 1 << (57 - e))
        assert discarded == 0
        residual_sign = sign
    else:
        m = 0x3243f6a8885a308d3
        q, remainder = divmod(sig << (e + 2), m)
        q += int(2 * remainder > m)
        d = (sig << (e + 2)) - q * m
        b, discarded = divmod(abs(d), 1 << 59)
        assert discarded == 0
        n += -q if sign else q
        residual_sign = sign ^ int(d < 0)
    assert b in (18, 22, 26, 30, 36, 44)
    cosine = n & 1
    negative = ((n >> 1) & 1) ^ (0 if cosine else residual_sign)
    exponent, mantissa = rom[b][cosine]
    width = mantissa.bit_length()
    top = exponent + width - 1
    if width <= 64:
        kept, increment = mantissa << (64 - width), 0
    else:
        divisor = 1 << (width - 64)
        kept, remainder = divmod(mantissa, divisor)
        away = (negative and row['mode'] == 'rd') or (not negative and row['mode'] == 'ru')
        increment = int((row['mode'] == 'rn' and (2 * remainder > divisor or
                         (2 * remainder == divisor and kept & 1))) or (away and remainder != 0))
        kept += increment
        if kept == 1 << 64:
            kept >>= 1; top += 1
    output = f'{(negative << 15) | (top + 16383):04x}:{kept:016x}'
    assert row['masks'] == 63 and row['flags'] == row['pending'] == row['empty'] == 0
    stack_top = (-row['depth']) & 7
    tag = ((1 << row['depth']) - 1) << (8 - row['depth'])
    result = dict(encoding_class='normal_in_range', output=output, response='OK', delivery='none',
        new_exception_flags=32, C1=increment, C2=0,
        status_bits=(stack_top << 11) | (row['cc'] & 0x4100) | (increment << 9) | 32,
        status_known_mask=65535, physical_abridged_tag=tag, top=stack_top)
    return result, b


def independent_inspect(row, line, expected):
    words = line.lower().split()
    assert len(words) == 60 and all(word.count('=') == 1 for word in words)
    fields = dict(word.split('=') for word in words)
    assert len(fields) == 60
    top = (-row['depth']) & 7
    cw = 0x7f | {24: 0, 53: 0x200, 64: 0x300}[row['pc']] | {'rn': 0, 'rd': 0x400, 'ru': 0x800, 'rz': 0xc00}[row['mode']]
    before = dict(case=row['case_id'].lower(), insn=row['instruction'], mode=row['mode'],
        pc=f'pc{row["pc"]}', masks='3f', depth=str(row['depth']), cc=f'{row["cc"]:04x}',
        flags='00', pending='0', empty='0', b_cw=f'{cw:04x}',
        b_sw=f'{(top << 11) | row["cc"]:04x}', b_ftw=f'{expected["physical_abridged_tag"]:02x}',
        b_r0=row['operand'].replace(' ', ':'))
    for i in range(1, row['depth']):
        before[f'b_r{i}'] = f'3fff:{(1 << 63) + 8 * i:016x}'
    selected = 'a' if int(fields['a_valid']) else 'f'
    exact = dict(before=all(fields[k] == v for k, v in before.items()),
        delivery=tuple(int(fields[k]) for k in ('a_valid', 'fault', 'fault_at', 'trap')) == (1, 0, 0, 0),
        status=int(fields[selected + '_sw'], 16) == expected['status_bits'],
        CW=int(fields[selected + '_cw'], 16) == cw, TOP=int(fields[selected + '_top']) == top,
        FTW=int(fields[selected + '_ftw'], 16) == expected['physical_abridged_tag'],
        deeper=all(fields[selected + f'_r{i}'] == fields[f'b_r{i}'] for i in range(1, 8)),
        output=fields[selected + '_r0'] == expected['output'])
    if int(fields['fault']):
        reference = 'b' if fields['fault_at'] == '1' else 'a'
        names = ('cw', 'sw', 'top', 'ftw', *(f'r{i}' for i in range(8)), 'fop', 'fip', 'fdp')
        exact['fault_snapshot_relation'] = all(fields['f_' + k] == fields[reference + '_' + k] for k in names)
    return exact


def verify(root, rows, lines=None):
    rom = rom_words(root)
    counts, results, misses, groups = Counter(), [], [], defaultdict(list)
    for index, row in enumerate(rows):
        expected, b = predict(row, rom)
        assert expected == row['expected'], row['case_id']
        line = lines[index] if lines is not None else ' '.join(f'{k}={v}' for k, v in synthetic.synthetic(row).items())
        fields = primary.parse(line)
        first = primary.inspect(row, fields)
        second = independent_inspect(row, line, expected)
        assert first['exact'] == second, row['case_id']
        results.append(dict(first, independent_expected=expected, independent_exact=second, center=b))
        if not all(second.values()):
            misses.append(results[-1])
        counts['rows'] += 1
        for key, good in second.items():
            counts[key + '_checks'] += 1; counts[key + '_exact'] += good
        selected = first['selected_snapshot']
        groups[(row['operand'], row['instruction'], row['mode'])].append(
            (fields[selected + '_R0'], fields[selected + '_SW'], fields[selected + '_FTW']))
        if lines is None:
            for key, value, check in (('A_R0', 'ffff:ffffffffffffffff', 'output'),
                    ('A_SW', f'{int(fields["A_SW"], 16) ^ 0x100:04x}', 'status'),
                    ('B_R0', 'ffff:ffffffffffffffff', 'before')):
                changed = dict(fields); changed[key] = value
                altered = ' '.join(f'{k}={v}' for k, v in changed.items())
                assert not primary.inspect(row, changed)['exact'][check]
                assert not independent_inspect(row, altered, expected)[check]
                counts['independent_' + check + '_mutation_detected'] += 1
    assert all(len(values) == 3 for values in groups.values())
    return results, misses, counts, sum(len(set(v)) != 1 for v in groups.values())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument('--bank', type=Path); choice.add_argument('--kit', type=Path)
    p.add_argument('--output-dir', required=True, type=Path); p.add_argument('--mark-opened', action='store_true')
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists() and primary.digest(Path(primary.__file__)) == PRIMARY_SHA
    assert not a.mark_opened or a.kit
    lines, anchors = None, {}
    if a.bank:
        bank = json.loads(a.bank.read_text()); rows = bank['predictions']
        assert bank['capture_state'] == 'SOFTWARE_ONLY_NOT_FROZEN'
        anchors['bank'] = primary.digest(a.bank)
    else:
        kit = a.kit.resolve()
        assert not a.mark_opened or not (kit / 'OPENED.json').exists()
        freeze = json.loads((kit / 'FREEZE.json').read_text())
        assert freeze['experiment'] == 'h1694_remaining_exact_centers'
        assert freeze['sha256']['scorer'] == primary.digest(Path(__file__))
        for line in (kit / 'CHECKSUMS.sha256').read_text().splitlines():
            sha, name = line.split(); path = Path(name)
            assert not path.is_absolute() and '..' not in path.parts and primary.digest(kit / path) == sha
        rows = json.loads((kit / 'manifest.json').read_text())
        assert len(rows) == freeze['unique_capture_tuples'] == 624
        assert (kit / 'inputs.txt').read_text().splitlines() == [r['capture_line'] for r in rows]
        output = kit / 'hardware-output'
        assert (output / 'complete-utc.txt').is_file()
        assert (output / 'binary.sha256').read_text().split()[0] == freeze['hardware_target']['capture_binary_sha256']
        sha, name = (output / 'outputs.sha256').read_text().split()
        assert name == 'hardware-output/state-output.txt' and primary.digest(kit / name) == sha
        lines = (kit / name).read_text().splitlines(); assert len(lines) == len(rows)
        anchors.update(freeze=primary.digest(kit / 'FREEZE.json'), manifest=primary.digest(kit / 'manifest.json'), raw=sha)
    assert len(rows) == len({(r['instruction'], r['mode'], r['pc'], r['operand']) for r in rows}) == 624
    results, misses, counts, pc_differences = verify(root, rows, lines)
    out.mkdir(parents=True); save(out / 'score.json', results); save(out / 'misses.json', misses)
    report = dict(experiment='h1693_center_state_verifier',
        status=('PREFLIGHT_PASS' if lines is None else 'FROZEN_CENTER_PREDICTIONS_PASS') if not misses else 'FROZEN_CENTER_PREDICTIONS_FAIL',
        counts=dict(counts), miss_rows=len(misses), PC_differences=pc_differences,
        hardware_execution='none', scoring='synthetic' if lines is None else 'already captured once',
        independent_scope='Separate integer ROM rounder, external center/quadrant reducer and raw-state parser; no graph/transition or primary-parser calls in those functions. Finite evidence, not universal silicon/state closure.',
        candidate_or_paper_change=False,
        sha256=dict(script=primary.digest(Path(__file__)), ROM=ROM_SHA, primary_helper=PRIMARY_SHA,
            evidence=anchors, score=primary.digest(out / 'score.json'), misses=primary.digest(out / 'misses.json')))
    save(out / 'report.json', report)
    if a.mark_opened:
        save(kit / 'OPENED.json', dict(experiment=freeze['experiment'], capture_state='OPENED_ONCE', retries=0,
            verdict=report['status'], miss_rows=len(misses), counts=dict(counts),
            freeze_sha256=anchors['freeze'], report_sha256=primary.digest(out / 'report.json'),
            candidate_changed=False, paper_change='none'))
    print(json.dumps({k: report[k] for k in ('status', 'counts', 'miss_rows', 'PC_differences')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
