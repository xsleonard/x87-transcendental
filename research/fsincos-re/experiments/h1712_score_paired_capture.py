#!/usr/bin/env python3
"""Score immutable H1712 paired predictions, with a synthetic mutation preflight.

Only numerical lanes, cosine C1, C2 and the essential capture mapping/control
contract are claimed. Undefined condition flags and unused registers are not.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from h1709_paired_retained_census import digest, save


def parse(line):
    words = line.split(); fields = dict(w.split('=', 1) for w in words)
    assert len(words) == len(fields) == 31
    return fields


def inspect(row, fields, policy='last'):
    expected = row['predictions'][policy][row['mode']]
    cw = 0x7f | {24:0,53:0x200,64:0x300}[row['pc']] | {'rn':0,'rd':0x400,'ru':0x800,'rz':0xc00}[row['mode']]
    before = dict(CASE=row['case_id'], INSN='fsincos', MODE=row['mode'], PC=f'pc{row["pc"]}',
        MASKS='3f', DEPTH='1', PRIOR='clear', B_CW=f'{cw:04x}', B_SW='3800', B_TOP='7', B_FTW='80',
        B_R0=row['operand'].replace(' ',':'))
    c2 = expected['outputs'] is None
    checks = dict(before=all(fields.get(k) == v for k,v in before.items()),
        CW=fields['A_CW'] == f'{cw:04x}', C2=bool(int(fields['A_SW'],16)&0x400) == c2,
        stack_mapping=(fields['A_TOP'],fields['A_FTW']) == (('7','80') if c2 else ('6','c0')))
    if c2:
        checks['C2_operand_preserved'] = fields['A_R0'] == before['B_R0']
    else:
        checks['sine'] = fields['A_R1'] == expected['outputs'][0]
        checks['cosine'] = fields['A_R0'] == expected['outputs'][1]
        if expected['C1'] is not None: checks['C1'] = ((int(fields['A_SW'],16)>>9)&1) == expected['C1']
    return checks


def synthetic(row):
    pred = row['predictions']['last'][row['mode']]
    c2 = pred['outputs'] is None
    cw = 0x7f | {24:0,53:0x200,64:0x300}[row['pc']] | {'rn':0,'rd':0x400,'ru':0x800,'rz':0xc00}[row['mode']]
    fields = dict(CASE=row['case_id'], INSN='fsincos', MODE=row['mode'], PC=f'pc{row["pc"]}',
        MASKS='3f', DEPTH='1', PRIOR='clear')
    for phase in ('B','A'):
        before = phase == 'B'
        sw = 0x3800 if before else 0x3c00 if c2 else 0x3020 | ((pred['C1'] or 0)<<9)
        fields.update({phase+'_CW':f'{cw:04x}',phase+'_SW':f'{sw:04x}',
            phase+'_TOP':'7' if before or c2 else '6',phase+'_FTW':'80' if before or c2 else 'c0'})
        for i in range(8): fields[phase+f'_R{i}'] = '0000:0000000000000000'
    fields['B_R0'] = row['operand'].replace(' ',':')
    fields['A_R0'] = fields['B_R0'] if c2 else pred['outputs'][1]
    if not c2: fields['A_R1'] = pred['outputs'][0]
    return fields


def preflight(rows):
    counts = Counter()
    for row in rows:
        fields = synthetic(row); line = ' '.join(k+'='+v for k,v in fields.items())
        assert all(inspect(row, parse(line)).values()); counts['synthetic_rows'] += 1
        mutations = [('CASE','wrong','before'),('A_CW','0000','CW'),
            ('A_SW',f'{int(fields["A_SW"],16)^0x400:04x}','C2'),('A_TOP','0','stack_mapping')]
        if row['predictions']['last'][row['mode']]['outputs'] is not None:
            mutations += [('A_R1','0000:0000000000000000','sine'),('A_R0','0000:0000000000000000','cosine'),
                ('A_SW',f'{int(fields["A_SW"],16)^0x200:04x}','C1')]
        else: mutations += [('A_R0','0000:0000000000000000','C2_operand_preserved')]
        for key, value, check in mutations:
            altered = dict(fields); altered[key] = value
            assert not inspect(row, altered)[check]; counts['mutation_detections'] += 1
    return dict(counts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit', required=True, type=Path); p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--mark-opened', action='store_true')
    a = p.parse_args(); kit = a.kit.resolve(); out = a.output_dir.resolve(); assert not out.exists()
    assert not a.mark_opened or not (kit / 'OPENED.json').exists()
    freeze = json.loads((kit / 'FREEZE.json').read_text())
    assert digest(Path(__file__)) == freeze['sha256']['scorer']
    for line in (kit / 'CHECKSUMS.sha256').read_text().splitlines():
        sha, name = line.split(); assert Path(name).name == name and digest(kit / name) == sha
    rows = json.loads((kit / 'manifest.json').read_text()); assert len(rows) == freeze['unique_capture_tuples']
    assert (kit / 'inputs.txt').read_text().splitlines() == [r['capture_line'] for r in rows]
    assert preflight(rows) == freeze['scorer_preflight']
    hardware = kit / 'hardware-output'; assert (hardware / 'complete-utc.txt').is_file()
    assert (hardware / 'binary.sha256').read_text().split()[0] == freeze['capture_binary_sha256']
    sha, name = (hardware / 'outputs.sha256').read_text().split()
    assert name == 'hardware-output/state-output.txt' and digest(kit / name) == sha
    lines = (kit / name).read_text().splitlines(); assert len(lines) == len(rows)
    counts = {policy:Counter() for policy in ('baseline','last','all')}; misses = {policy:[] for policy in counts}
    paths = Counter(); discriminator_rows = 0
    for row, line in zip(rows, lines):
        fields = parse(line); paths[row['predictions']['last'][row['mode']]['path']] += 1
        discriminator_rows += row['predictions']['last'][row['mode']] != row['predictions']['baseline'][row['mode']]
        for policy in counts:
            checks = inspect(row, fields, policy)
            counts[policy]['rows'] += 1
            for key, good in checks.items():
                counts[policy][key+'_checks'] += 1; counts[policy][key+'_misses'] += not good
            if not all(checks.values()):
                misses[policy].append(dict(case_id=row['case_id'], operand=row['operand'], mode=row['mode'], pc=row['pc'],
                    expected=row['predictions'][policy][row['mode']], checks=checks, raw=line))
    out.mkdir(parents=True)
    report = dict(experiment='h1712_score_paired_capture', status='PASS_FROZEN_PAIRED' if not misses['last'] else 'FROZEN_PAIRED_FALSIFIED',
        counts={k:dict(v) for k,v in counts.items()}, miss_counts={k:len(v) for k,v in misses.items()},
        paths=dict(paths), discriminator_rows=discriminator_rows, unique_operands=freeze['unique_operands'],
        hardware_execution='ONCE', instruction_retries=0, promotion=False,
        claim_boundary='Fresh paired numerical/C1/C2 and relevant control/stack mapping test, not exhaustive silicon or full arbitrary-state closure.',
        sha256=dict(freeze=digest(kit / 'FREEZE.json'), manifest=digest(kit / 'manifest.json'), raw=sha, script=digest(Path(__file__))))
    save(out / 'misses.json', misses); save(out / 'report.json', report)
    if a.mark_opened:
        save(kit / 'OPENED.json', dict(status='OPENED_ONCE_DO_NOT_RERUN', instruction_retries=0,
            frozen_predictions_unchanged=True, sha256=dict(freeze=digest(kit / 'FREEZE.json'), raw=sha,
            score=digest(out / 'report.json'), misses=digest(out / 'misses.json'))))
    print(json.dumps({k:report[k] for k in ('status','counts','miss_counts','paths','discriminator_rows','unique_operands')},sort_keys=True))


if __name__ == '__main__': main()
