#!/usr/bin/env python3
"""Check the actual Makefile-built CLI against H1708's full retained outputs.

The audit build uses stdin source, so __FILE__ assertion strings can change
binary hashes without changing arithmetic. Verify actual runtime outputs.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import h1707_packaged_candidate_regression as regression
from h1642_score_remaining_scope import save, digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); root = args.root.resolve(); assert not args.output.exists()
    binary = root/'src/fsincos_skylake'
    directory = root/'tmp/ledger33/current/h1708_default_promotion'
    assert digest(directory/'report.json') == 'e047633abe3d59bf08fe63132068e9991950071568f2a851e2820719d37b4685'
    report = json.loads((directory/'report.json').read_text())
    assert digest(root/'src/fsincos_skylake.c') == report['sha256']['main_source']
    banks, _ = regression.inventory(root); rows = 0; hashes = {}
    for i, bank in enumerate(banks):
        expected = json.loads((directory/f'bank_{i:03d}.json').read_text())
        assert expected['bank'] == bank
        with (root/bank['inputs']).open() as inputs:
            proc = subprocess.run([str(binary), '--batch', '--'+bank['instruction']+'-standalone',
                '--rc='+bank['mode']], stdin=inputs, text=True, capture_output=True, check=True)
        assert not proc.stderr
        sha = hashlib.sha256(proc.stdout.encode()).hexdigest()
        assert sha == expected['stdout_sha256'], bank['tag']
        assert len(proc.stdout.splitlines()) == bank['count']
        rows += bank['count']; hashes[bank['tag']] = sha
    frontier = json.loads((directory/'report.json').read_text())['frontier']
    # The detailed golden rows are authenticated by the original report.
    golden = json.loads((root/'tmp/ledger33/current/h1638_tiny_c_transfer/report.json').read_text())
    assert digest(root/'tmp/ledger33/current/h1638_tiny_c_transfer/report.json') == regression.REPORTS['tmp/ledger33/current/h1638_tiny_c_transfer/report.json']
    extra = 0
    for group in ('frontier','legacy'):
        selected = golden['frontier_checks'][group]['candidate_O2']
        assert len(selected) == frontier[group]['counts']['rows']
        for row in selected:
            proc = subprocess.run([str(binary), '--batch', '--'+row['instruction']+'-standalone',
                '--rc='+row['mode']], input=row['operand']+'\n', text=True, capture_output=True, check=True)
            assert not proc.stderr and regression.cmodel.table.records.parse_output(proc.stdout.strip()) == row['output']
            extra += 1
    result = dict(status='PASS_CANONICAL_CLI', banks=len(banks), retained_output_appearances=rows,
        frontier_and_legacy_checks=extra, quiet_stderr=True, misses=0, hardware_execution='none',
        sha256=dict(script=digest(Path(__file__)), binary=digest(binary),
            source=digest(root/'src/fsincos_skylake.c'), bank_stdout=hashes))
    save(args.output, result)
    print(json.dumps({k:v for k,v in result.items() if k != 'sha256'}, sort_keys=True))


if __name__ == '__main__': main()
