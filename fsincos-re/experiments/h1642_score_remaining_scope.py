#!/usr/bin/env python3
"""Score frozen H1641 outputs and only explicitly predicted status fields.

Preserve raw status on every row, including C2. Null predictions stay
unscored; measured unknown fields are not retroactive successful predictions.
No hardware execution, model adjustment or overwriting of prior scores.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as target:
        json.dump(value, target, indent=2, sort_keys=True)
        target.write('\n')


def parse(line):
    found = re.fullmatch(r'OK ([0-9a-fA-F]{4}) ([0-9a-fA-F]{16}) SW ([0-9a-fA-F]{4})', line)
    if found:
        se, sig, sw = (s.lower() for s in found.groups())
        assert not int(sw, 16) & 0x400
        return se + ':' + sig, sw
    found = re.fullmatch(r'C2 SW ([0-9a-fA-F]{4})', line)
    assert found, 'Malformed capture record'
    sw = found[1].lower()
    assert int(sw, 16) & 0x400
    return 'C2', sw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--mark-opened', action='store_true')
    args = parser.parse_args()
    kit, output = args.kit.resolve(), args.output_dir.resolve()
    assert not output.exists() and not (args.mark_opened and (kit / 'OPENED.json').exists())
    freeze = json.loads((kit / 'FREEZE.json').read_text())
    assert freeze['experiment'] == 'h1641_remaining_scope' and freeze['capture_state'] == 'FROZEN_UNOPENED'
    assert freeze['sha256']['scorer'] == digest(Path(__file__))
    checked = set()
    for line in (kit / 'CHECKSUMS.sha256').read_text().splitlines():
        sha, name = line.split(None, 1); path = Path(name.strip())
        assert not path.is_absolute() and '..' not in path.parts and str(path) not in checked
        assert digest(kit / path) == sha
        checked.add(str(path))
    assert checked == {'FREEZE.json','manifest.json','run_capture.sh','candidate_signatures.txt',
        *(f'inputs/{lane}.txt' for lane in freeze['lanes'])}
    assert freeze['one_observation_maximum_per_tuple'] and freeze['candidate_changed'] is False
    assert digest(kit / 'manifest.json') == freeze['sha256']['manifest']
    assert digest(kit / 'run_capture.sh') == freeze['sha256']['runner']
    rows = json.loads((kit / 'manifest.json').read_text())
    assert len(rows) == freeze['unique_capture_tuples'] == 6432
    assert len({r['case_id'] for r in rows}) == len({(r['instruction'],r['precision_control'],r['mode'],r['operand']) for r in rows}) == len(rows)
    assert len({r['operand'] for r in rows}) == freeze['unique_operands'] == 268
    raw = kit / 'hardware-output'
    assert (raw / 'binary.sha256').read_text().split()[0] == freeze['hardware_target']['capture_binary_sha256']
    cpu = (raw / 'cpu-summary.txt').read_text()
    assert re.search(r'vendor_id\s*:\s*GenuineIntel', cpu)
    assert re.search(r'cpu family\s*:\s*6\s*$', cpu, re.M)
    assert re.search(r'^model\s*:\s*85\s*$', cpu, re.M)
    assert (raw / 'complete-utc.txt').is_file()
    hashes = {}
    for line in (raw / 'outputs.sha256').read_text().splitlines():
        sha, name = line.split(None, 1); path = Path(name.strip())
        assert str(path) == 'hardware-output/' + path.name and path.name not in hashes
        hashes[path.name] = sha
    assert set(hashes) == {lane + '.txt' for lane in freeze['lanes']}
    observed = {}
    for name, lane in freeze['lanes'].items():
        selected = [r for r in rows if r['lane'] == name]
        inputs = kit / 'inputs' / (name + '.txt')
        assert inputs.read_text().splitlines() == [r['operand'] for r in selected]
        assert digest(inputs) == lane['sha256']
        path = raw / (name + '.txt')
        assert digest(path) == hashes[path.name]
        lines = path.read_text().splitlines()
        assert len(lines) == len(selected) == lane['rows']
        for row, line in zip(selected, lines):
            observed[row['case_id']] = parse(line)
    counts, cells, statuses, pcs = Counter(), defaultdict(Counter), defaultdict(Counter), defaultdict(dict)
    scored = []
    for row in rows:
        value, sw = observed[row['case_id']]
        c1, flags = (int(sw,16) >> 9) & 1, int(sw,16) & 0x3f
        record = dict(row, hardware=value, hardware_SW=sw, hardware_C1=c1, hardware_exception_flags=flags,
            output_exact=value == row['output'], C1_exact=None if row['C1'] is None else c1 == row['C1'],
            exception_flags_exact=None if row['exception_flags'] is None else flags == row['exception_flags'])
        metrics = {'observed':1, 'output_exact':int(record['output_exact'])}
        for field in ('C1','exception_flags'):
            metrics[field + '_scored'] = int(record[field + '_exact'] is not None)
            metrics[field + '_exact'] = int(record[field + '_exact'] is True)
        for key, n in metrics.items():
            counts[key] += n
            for kind in row['kinds']:
                cells[kind][key] += n
        for kind in row['kinds']:
            statuses[kind][sw] += 1
        key = (row['instruction'],row['mode'],row['operand'])
        pcs[key][row['precision_control']] = (value,sw)
        scored.append(record)
    assert all(set(v) == {24,53,64} for v in pcs.values())
    pc_differences = [dict(instruction=k[0],mode=k[1],operand=k[2],observed=v) for k,v in pcs.items() if len(set(v.values())) != 1]
    misses = [r for r in scored if not r['output_exact'] or r['C1_exact'] is False or r['exception_flags_exact'] is False]
    output.mkdir(parents=True)
    save(output / 'score.json', scored)
    report = dict(experiment='h1642_score_remaining_scope', capture_state='OPENED_ONCE', repeats=0,
        counts=dict(counts), cells={k:dict(v) for k,v in cells.items()}, status_words={k:dict(v) for k,v in statuses.items()},
        misses=misses, precision_control_differences=pc_differences,
        verdict='FROZEN_PREDICTIONS_SURVIVE_FINITE_BANK' if not misses else 'FROZEN_PREDICTIONS_FALSIFIED',
        claim_boundary='Only frozen output/C2, C1 and exception-mask predictions are scored. Null fields are observations, not predicted passes. Full status/stack/load/unmasked semantics and universal silicon correctness remain open. No candidate adjustment or promotion.',
        sha256=dict(freeze=digest(kit/'FREEZE.json'), manifest=digest(kit/'manifest.json'), scorer=digest(Path(__file__)),
            score=digest(output/'score.json'), raw_outputs=hashes,
            raw_metadata={p.name:digest(p) for p in raw.iterdir() if p.is_file() and p.name not in hashes}))
    save(output / 'report.json', report)
    if args.mark_opened:
        save(kit / 'OPENED.json', dict(experiment=freeze['experiment'],capture_state='OPENED_ONCE',repeats=0,
            counts=dict(counts),verdict=report['verdict'], report_sha256=digest(output/'report.json'),
            freeze_sha256=report['sha256']['freeze'], candidate_changed=False, paper_change='none'))
    print(json.dumps(dict(counts=dict(counts),verdict=report['verdict'],misses=len(misses),
        precision_control_differences=len(pc_differences)),sort_keys=True),flush=True)


if __name__ == '__main__':
    main()
