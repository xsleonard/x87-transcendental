#!/usr/bin/env python3
"""Regress the runnable standalone package against authenticated open banks.

No new captures or rules. Rechecks output and applicable numerical C1, not
unrelated architectural state. Appearance counts are not unique hardware tuples.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
import h1638_tiny_c_transfer as cmodel
import h1707_build_standalone_candidate as package
from h1640_remaining_scope_freshness import save
from h1650_score_masked_state import digest

CURRENT = 'tmp/ledger33/current/'
REPORTS = {
    CURRENT+'h1633_shared_table_audit/report.json': '935a4352843b0b0b96559fb4447fc1a329b0da9d5530c85790b622b3bc5bb51c',
    CURRENT+'h1638_tiny_c_transfer/report.json': 'db6c8cbc1e0e2c9acdb54da5e1e381407a6b8c5f6f62cc7b1c52c4d90f8510e0',
}


def inventory(root):
    evidence = dict(REPORTS); banks = []
    for name, sha in REPORTS.items():
        assert digest(root/name) == sha, name
        report = json.loads((root/name).read_text())
        for path, expected in report['sha256']['evidence'].items():
            assert evidence.get(path, expected) == expected
            evidence[path] = expected
        prep = Path(name).parent/'prepared.json'
        assert digest(root/prep) == report['sha256']['prepared']
        evidence[str(prep)] = digest(root/prep)
        for bank in json.loads((root/prep).read_text())['inventories']:
            if 'captures' in bank:
                banks.extend(dict(tag=bank['tag']+'_'+mode, instruction=bank['instruction'], mode=mode,
                    inputs=bank['inputs'], capture=path, count=bank['count']) for mode, path in bank['captures'].items())
            else: banks.append(bank)
    for bank in banks:
        for field in ('inputs', 'capture'):
            path = bank[field]
            assert path in evidence and digest(root/path) == evidence[path], path
    return banks, evidence


def cli_tests(binary):
    bad = [[], ['--batch'], ['--batch','--fsincos'],
        ['--batch','--fsin-standalone','--fcos-standalone'],
        ['--batch','--fsin-standalone','--fsin-standalone'],
        ['--batch','--fcos-standalone','--rc=rn','--rc=rd'],
        ['--batch','--fsin-standalone','--rc=bad'],
        ['--batch','--fcos-standalone','--round84-errata'],
        ['--batch','--fsin-standalone','--perturb=1'],
        ['--batch','--fptan'], ['--kernel-test'], ['--selftest','--fcos-standalone']]
    for args in bad:
        proc = subprocess.run([str(binary), *args], input='', text=True, capture_output=True)
        assert proc.returncode == 2 and not proc.stdout
        assert proc.stderr.startswith('Unsupported candidate arguments;')
    for args in (['--help'], ['--selftest']):
        proc = subprocess.run([str(binary), *args], text=True, capture_output=True)
        assert proc.returncode == 0 and not proc.stderr
    return dict(rejected_argument_cases=len(bad), help_and_selftest_pass=True,
        FSINCOS_exposed=False, runtime_experimental_switches_exposed=False)


def score_bank(root, binary, bank):
    operands = (root/bank['inputs']).read_text().splitlines()
    raw = (root/bank['capture']).read_text().splitlines()
    assert len(operands) == len(raw) == bank['count']
    counts = Counter(); misses = []; stamp = hashlib.sha256()
    for start in range(0, len(operands), 4096):
        batch = operands[start:start+4096]
        values, metadata, stdout = cmodel.run(binary, bank['instruction'], bank['mode'], batch)
        stamp.update(stdout.encode())
        for i, (operand, value) in enumerate(zip(batch, values)):
            expected, sw = cmodel.spec.raw_reader.raw(raw[start+i], True)
            meta = metadata.get(i)
            output_miss = value != expected
            c1_miss = meta is not None and meta['C1'] != (sw >> 9) & 1
            counts['rows'] += 1; counts['C1_checks'] += meta is not None
            counts['lane_'+(meta['lane'] if meta else 'special_or_range')] += 1
            counts['output_misses'] += output_miss; counts['C1_misses'] += c1_miss
            if output_miss or c1_miss:
                misses.append(dict(index=start+i, operand=operand, expected=expected, actual=value,
                    hardware_C1=(sw>>9)&1, metadata=meta, output_miss=output_miss, C1_miss=c1_miss))
    return dict(bank=bank, counts=dict(counts), misses=misses, stdout_sha256=stamp.hexdigest())


def frontier(root, binary):
    report = json.loads((root/CURRENT/'h1638_tiny_c_transfer/report.json').read_text())
    results = {}
    for group in ('frontier', 'legacy'):
        rows = report['frontier_checks'][group]['candidate_O2']; counts = Counter(); misses = []
        for insn, mode in sorted({(r['instruction'], r['mode']) for r in rows}):
            selected = [r for r in rows if (r['instruction'], r['mode']) == (insn, mode)]
            values, metadata, _ = cmodel.run(binary, insn, mode, [r['operand'] for r in selected])
            for i, row in enumerate(selected):
                output_miss = values[i] != row['output']
                metadata_miss = metadata.get(i) != row['metadata']
                counts['rows'] += 1
                counts['output_misses'] += output_miss; counts['metadata_misses'] += metadata_miss
                if output_miss or metadata_miss:
                    misses.append(dict(row=row, actual=values[i], metadata=metadata.get(i)))
        results[group] = dict(counts=dict(counts), misses=misses)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); root, binary, out = args.root.resolve(), args.binary.resolve(), args.output_dir.resolve()
    assert binary.is_file() and not out.exists()
    source = package.source_string(root)
    banks, evidence = inventory(root)
    out.mkdir(parents=True)
    interface = cli_tests(binary); save(out/'interface.json', interface)
    results = []; totals = Counter()
    for index, bank in enumerate(banks):
        scored = score_bank(root, binary, bank); results.append(scored); totals.update(scored['counts'])
        save(out/f'bank_{index:03d}.json', scored)
        print(bank['tag'], json.dumps(scored['counts'], sort_keys=True), flush=True)
    old = frontier(root, binary); save(out/'frontier.json', old)
    failed = totals['output_misses'] or totals['C1_misses'] or any(r['misses'] for r in old.values())
    report = dict(experiment='h1707_packaged_candidate_regression', status='FAIL' if failed else 'PASS_RETAINED_NUMERICAL_PACKAGE',
        counts=dict(totals), banks=len(banks), historical_frontier=old, interface=interface,
        source_arithmetic_changed=False, hardware_execution='none', new_labels_opened=False,
        private_ledger_access='none', production_or_paper_promotion=False,
        boundary='Retained output/applicable-C1 appearances, not unique observations or fresh adversarial credit. The arithmetic source is identical to the already challenged H1638 program. Full standalone packaging/evidence reconciliation and separate FSINCOS remain.',
        sha256=dict(script=digest(Path(__file__)), builder=digest(Path(package.__file__)),
            wrapper=digest(root/'src/general/fsin_fcos_candidate_cli.h'), binary=digest(binary),
            packaged_source=hashlib.sha256(source.encode()).hexdigest(), arithmetic_source=package.SOURCE_SHA,
            evidence=evidence))
    save(out/'report.json', report)
    print(report['status'], json.dumps(dict(totals), sort_keys=True), flush=True)
    if failed: raise SystemExit(1)


if __name__ == '__main__': main()
