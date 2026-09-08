#!/usr/bin/env python3
"""Strict, bounded-storage software replay of already-opened hardware banks.

No native x87 captures, private ledgers, new labels, or algorithm changes.
The inventory records missing modes instead of counting absent data as passes.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

MODES = ('rn', 'rd', 'ru', 'rz')
PINS = {
    'src/fsincos_skylake.c': '490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32',
    'src/general/paired.h': '4eeb671562969e39b334923cbf41a40cb86f2a5ecb3dbad23de320be315b9a5d',
    'src/general/standalone_polynomial.h': '5a73364533fae1ba7a687480863fc48e54f30ed93760696bc19394de0b34e637',
    'src/general/standalone_table.h': '9786c6bd0644ba3036a9c92f6c4adbc6f93934366f041a731df94175c945057b',
    'src/general/standalone_tiny.h': 'baf65c0eb699ac8925676a055ff0827dcb3e943d2293c8a9c80c99bb9e7d2d45',
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    with path.open('x') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write('\n')


def inventory(host):
    jobs, missing = [], []

    def add(tag, insn, inputs, pattern, origin, modes=MODES):
        for mode in modes:
            raw = Path(pattern.format(mode=mode))
            row = dict(tag=tag, instruction=insn, mode=mode,
                       inputs=str(inputs), labels=str(raw), label_origin=origin)
            if Path(inputs).is_file() and raw.is_file():
                jobs.append(row)
            else:
                missing.append(row)

    if host == 'i7':
        d = Path('/root/h491')
        for bank in ('randv1', 'hostv1'):
            for insn, lane in (('fsin', 'sin'), ('fcos', 'cos')):
                add(bank, insn, d / (bank + '_inputs.txt'),
                    str(d / (bank + '_' + lane + '_{mode}_hw_status.txt')), 'saved_i7_h491')
        for bank in [f'comb{i}' for i in range(3, 20)] + ['comb13n']:
            add(bank, 'fcos', d / (bank + '_inputs.txt'),
                str(d / (bank + '_{mode}_status.txt')), 'saved_i7_h491')
        for bank in ('comb4', 'comb7', 'comb9', 'comb10', 'h589', 'h590f', 'h590k'):
            name = 'comb4_sincos_inputs.txt' if bank == 'comb4' else bank + '_inputs.txt'
            add(bank + '_paired', 'fsincos', d / name,
                str(d / (bank + '_sc_{mode}_status.txt')), 'saved_i7_h491')
        for bank in ('h585', 'h588', 'h589', 'h590f', 'h590k', 'h597', 'h599', 'h603', 'h604', 'h606'):
            add(bank, 'fcos', d / (bank + '_inputs.txt'),
                str(d / (bank + '_{mode}_status.txt')), 'saved_i7_h491')
        # Explicit aliases resolved from the retained capture scripts, not
        # guessed from similar filenames or input lengths.
        for bank, prefix, insn in [('h491', 'cos', 'fcos'), ('h491', 'sincos', 'fsincos'),
                                  ('h494', 'vcos', 'fcos'), ('h495', 'fcos2', 'fcos'),
                                  ('h499', 'comb', 'fcos')]:
            add(bank + '_' + insn, insn, d / (bank + '_inputs.txt'),
                str(d / (prefix + '_{mode}_status.txt')), 'saved_i7_h491')
        add('sc_recheck', 'fsincos', d / 'sc_recheck_inputs.txt',
            str(d / 'sc_recheck_{mode}.txt'), 'saved_i7_h491')
    else:
        d = Path('/root/fsincos-r88')
        for bank, name, pattern in [('h347', 'h347_inputs.txt', 'fsin_{mode}_status.txt'),
                                    ('sweep', 'sweep_inputs.txt', 'sweep_fsin_{mode}.txt'),
                                    ('dense', 'dense_qn.txt', 'dense_fsin_{mode}.txt')]:
            add(bank, 'fsin', d / 'corpora' / name, str(d / 'banked' / pattern),
                'retained_historical_mirror_on_skylake', modes=MODES[:3])
            add(bank, 'fsin', d / 'corpora' / name, str(d / 'fresh' / (bank + '_fsin_{mode}.txt')),
                'previously_opened_skylake_capture', modes=('rz',))
    return jobs, missing


def validate_driver(root, output):
    binary = root / 'src/fsincos_skylake'
    driver = root / 'experiments/h1719_saved_verifier'
    subprocess.run([str(binary), '--selftest'], check=True)
    subprocess.run(['python3', str(root / 'src/test_general_paired.py'), str(binary)], check=True)
    # Exact raw80 software probes include the policy-1 separator, all bypass
    # classes, reduction extremes and deterministic significand patterns.
    ops = ['3ffc e79000000c3e46e7', '3ffc c060000000d78237', '0000 0000000000000000',
           '8000 0000000000000000', '0000 0000000000000001', '0000 8000000000000000',
           '7fff 8000000000000000', '7fff c000000000000000', '7fff 8000000000000001',
           '3fff 0000000000000001', '403e 8000000000000000', '403d ffffffffffffffff']
    for e in (-100, -69, -68, -33, -32, -31, -10, -3, -2, -1, 0, 10, 62):
        for sign in (0, 0x8000):
            for s in (0x8000000000000000, 0xc90fdaa22168c233, 0xc90fdaa22168c234,
                      0xd0d000000cc0b3f8, 0xffffffffffffffff):
                ops.append(f'{sign | (16383 + e):04x} {s:016x}')
    probes = output / 'driver-probes.txt'
    with probes.open('x') as f:
        f.write('\n'.join(ops) + '\n')
    checked = 0
    for insn in ('fsin', 'fcos', 'fsincos'):
        for mode in MODES:
            args = [str(binary), '--batch', '--general-trace', '--rc=' + mode]
            if insn != 'fsincos':
                args.append('--' + insn + '-standalone')
            cli = subprocess.run(args, input=probes.read_text(), text=True, capture_output=True, check=True)
            embedded = subprocess.run([str(driver), '--predict', insn, mode, str(probes)],
                                      text=True, capture_output=True, check=True)
            meta = {}
            for line in cli.stderr.splitlines():
                w = line.split(); i = int(w[1])
                if w[0] == 'HPAIR':
                    if int(w[3]): meta[i] = int(w[5])
                elif w[0] == 'HTINY': meta[i] = int(w[6])
                elif w[0] in ('HPOLY', 'HTABLE'): meta[i] = int(w[-2])
                else: raise AssertionError(line)
            actual = embedded.stdout.splitlines(); expected = cli.stdout.splitlines()
            assert len(actual) == len(expected) == len(ops)
            for i, (got, want) in enumerate(zip(actual, expected)):
                value, flags = got.split(' META '); known, c1 = map(int, flags.split())
                assert value == want and known == (i in meta), (insn, mode, ops[i], got, want, meta.get(i))
                if known: assert c1 == meta[i]
                checked += 1
    # The verifier must reject stream truncation and malformed records. These
    # synthetic expectations do not create or modify hardware evidence.
    one = output / 'one-input.txt'; one.write_text('3ffc e79000000c3e46e7\n')
    label = output / 'synthetic-good.txt'
    good = 'OK 3ffc e5980e1fae54d858 3ffe f97b7761040745d2 SW 3020\n'
    label.write_text(good)
    prefix = [str(driver), 'fsincos', 'rn', str(one)]
    assert subprocess.run(prefix + [str(label)], capture_output=True).returncode == 0
    cases = {'truncated': '', 'extra': good + good, 'malformed': 'bogus\n',
             'wrong-c1': good.replace('3020', '3220'),
             'policy1-output': good.replace('e5980e1fae54d858', 'e5980e1fae54d857')}
    for name, text in cases.items():
        path = output / ('synthetic-' + name + '.txt'); path.write_text(text)
        p = subprocess.run(prefix + [str(path)], capture_output=True)
        assert p.returncode != 0, name
    result = dict(status='PASS', actual_CLI_equivalence_cases=checked, negative_controls=len(cases))
    save(output / 'driver-validation.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--host', required=True, choices=('i7', 'skylake'))
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--validate-only', action='store_true')
    a = p.parse_args(); root = a.root.resolve(); output = a.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False); start = time.time()
    for file, expected in PINS.items(): assert digest(root / file) == expected, file
    validation = validate_driver(root, output)
    if a.validate_only: return
    jobs, missing = inventory(a.host); assert jobs
    save(output / 'inventory.json', dict(jobs=jobs, unavailable_modes=missing))
    files = sorted({j[k] for j in jobs for k in ('inputs', 'labels')})
    evidence = {file: dict(sha256=digest(file), bytes=Path(file).stat().st_size) for file in files}
    save(output / 'evidence.json', evidence)
    records = []

    def job(index, item):
        began = time.time(); stem = f'{index:03d}_{item["tag"]}_{item["instruction"]}_{item["mode"]}'
        command = ['nice', '-n', '10', str(root / 'experiments/h1719_saved_verifier'),
                   item['instruction'], item['mode'], item['inputs'], item['labels']]
        with (output / (stem + '.log')).open('x') as err:
            proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=err)
        counts = json.loads(proc.stdout) if proc.returncode in (0, 1) else None
        row = dict(job=item, returncode=proc.returncode, status='PASS' if proc.returncode == 0 else 'FAIL',
                   counts=counts, seconds=time.time() - began, stdout=proc.stdout)
        save(output / (stem + '.json'), row)
        print(stem, row['status'], counts, flush=True)
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = [pool.submit(job, i, item) for i, item in enumerate(jobs)]
        for future in concurrent.futures.as_completed(futures): records.append(future.result())
    # Rehash after scoring: provenance must describe the bytes actually held
    # stable for this run, not merely an initial name/size snapshot.
    for file in files: assert digest(file) == evidence[file]['sha256'], file
    totals = sum((Counter(r['counts']) for r in records if r['counts']), Counter())
    source_files = list(PINS) + ['src/ia64_sf.h', 'src/p5_rom_constants.h', 'src/f2xm1_constants.h',
                                'data/frcpa-recip-table.h', 'src/fsincos_skylake',
                                'experiments/h1719_saved_verifier.c', 'experiments/h1719_saved_verifier',
                                'experiments/h1719_run_saved_suite.py']
    result = dict(status='PASS' if all(r['status'] == 'PASS' for r in records) else 'FAIL',
                  host=a.host, jobs=len(jobs), counts=dict(totals), seconds=time.time() - start,
                  driver_validation=validation, source_sha256={s: digest(root / s) for s in source_files},
                  hardware_executions=0, records=records, unavailable_mode_count=len(missing),
                  scope='Saved numerical output/C1/C2 appearances; overlaps are not unique tuples. '
                        'Missing modes and undefined C1 are not passes. No full new-corpus Cartesian capture.',
                  compiler=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                  execution_cpu=Path('/proc/cpuinfo').read_text().split('\n\n')[0])
    save(output / 'report.json', result); print('FINAL', result['status'], dict(totals), flush=True)
    if result['status'] != 'PASS': raise SystemExit(1)


if __name__ == '__main__':
    main()
