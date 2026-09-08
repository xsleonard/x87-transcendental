#!/usr/bin/env python3
"""Replay opened H1641/H1694 values/C1 against the promoted C, never hardware."""
from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import h1638_tiny_c_transfer as cmodel
from h1642_score_remaining_scope import parse, digest, save

LOCKS = {
 'h1641/FREEZE.json': '066ac4f086d9132ba157195af02a3aaffaccb4f3e05c5337a4689b634f35f833',
 'h1641/OPENED.json': '4fcd80c8850575714eb111d88c7db2cf1bbebdf34371fb7edb4e10a044b426f8',
 'h1641/manifest.json': '453ecfe5ab81dc49c23cd045d85af341df3e8e6b2125cca6dd7c064568d06a84',
 'h1641/hardware-output/outputs.sha256': '296b803e99280afcce5485a2f5cf1a0305baf4c66255ba4006f6b89dc543a64c',
 'h1694/FREEZE.json': '2ae03aea2ed62ce06be21d45b7201dd28d472b7686e001c449366bffd18d22ed',
 'h1694/OPENED.json': '74ac5c9a09c8946158ad3638d0ad0aea224069e83852907e4c6ab1f5a5cda6b9',
 'h1694/manifest.json': '50f3b34b71647649e09d210d1aea294195bd49293823a785874133e96d5c0247',
 'h1694/hardware-output/state-output.txt': '9e43ee3840f7312d780f7dc50648c0cc20ef875c7b9c9d837a267c9ea4e2a57b',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); root = args.root.resolve(); kit = root/'transfer-tests'
    binary = args.binary.resolve(); assert not args.output.exists()
    evidence = dict(LOCKS)
    for name, sha in evidence.items(): assert digest(kit/name) == sha, name
    groups = defaultdict(list)
    rows = json.loads((kit/'h1641/manifest.json').read_text())
    for entry in (kit/'h1641/hardware-output/outputs.sha256').read_text().splitlines():
        sha, name = entry.split(); assert name.startswith('hardware-output/') and '..' not in name
        evidence['h1641/'+name] = sha
        assert digest(kit/'h1641'/name) == sha
        lane = Path(name).stem; selected = [r for r in rows if r['lane'] == lane]
        raw = (kit/'h1641'/name).read_text().splitlines(); assert len(raw) == len(selected)
        for row, line in zip(selected, raw):
            value, sw = parse(line)
            assert value == row['output']
            groups[('h1641', row['instruction'], row['mode'])].append(
                (row['operand'], value, int(sw,16), row['C1'], row['case_id']))
    rows = json.loads((kit/'h1694/manifest.json').read_text())
    raw = (kit/'h1694/hardware-output/state-output.txt').read_text().splitlines()
    assert len(rows) == len(raw) == 624
    for row, line in zip(rows, raw):
        fields = dict(word.lower().split('=') for word in line.split())
        assert fields['case'] == row['case_id'].lower()
        assert fields['insn'] == row['instruction'] and fields['mode'] == row['mode']
        assert fields['b_r0'] == row['operand'].replace(' ', ':')
        assert fields['a_valid'] == '1' and fields['fault'] == '0'
        groups[('h1694', row['instruction'], row['mode'])].append(
            (row['operand'], fields['a_r0'], int(fields['a_sw'],16), row['expected']['C1'], row['case_id']))
    counts = defaultdict(Counter); misses = []
    for (bank, insn, mode), group in sorted(groups.items()):
        values, metadata, _ = cmodel.run(binary, insn, mode, [r[0] for r in group])
        for i, (operand, expected, sw, c1, case) in enumerate(group):
            output_miss = values[i] != expected
            c1_miss = c1 is not None and (metadata.get(i,{}).get('C1') != c1 or c1 != (sw>>9)&1)
            counts[bank].update(rows=1, output_misses=output_miss, C1_checks=c1 is not None, C1_misses=c1_miss)
            if output_miss or c1_miss:
                misses.append(dict(bank=bank, case=case, expected=expected, actual=values[i], metadata=metadata.get(i)))
    report = dict(status='FAIL' if misses else 'PASS_OPENED_BOUNDARY_REGRESSION',
        counts={k:dict(v) for k,v in counts.items()}, misses=misses,
        hardware_execution='none', private_access='none', fresh_observation_credit=0,
        sha256=dict(script=digest(Path(__file__)), binary=digest(binary), evidence=evidence))
    save(args.output, report)
    print(json.dumps({k:v for k,v in report.items() if k != 'sha256'}, sort_keys=True))
    if misses: raise SystemExit(1)


if __name__ == '__main__': main()
