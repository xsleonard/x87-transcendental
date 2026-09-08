#!/usr/bin/env python3
"""Verify default standalone promotion against open hardware and archived C.

Software only: never executes capture harnesses or reads private material.
The corpus contains retained appearances, not fresh hardware observations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import re
import subprocess
from collections import Counter
from pathlib import Path
import h1707_packaged_candidate_regression as regression
import h1707_build_standalone_candidate as package
from h1640_remaining_scope_freshness import save
from h1650_score_masked_state import digest

CURRENT = 'tmp/ledger33/current/'
OLD_SHA = '0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b'
OLD_CANDIDATE_SHA = '0ba16ad137fcb4c53acb0ebbf8586ba390461cc53d1647f87e29222267980ac7'


def run(binary, args, operands=()):
    return subprocess.run([str(binary), *args], input=''.join(x+'\n' for x in operands),
        text=True, capture_output=True, check=True)


def header_identity(root):
    checked = []
    for old, new in [('h1630_shared_polynomial.h', 'standalone_polynomial.h'),
                     ('h1633_shared_table.h', 'standalone_table.h'),
                     ('h1638_tiny_closed_form.h', 'standalone_tiny.h')]:
        historical = (root/'experiments'/old).read_text()
        promoted = (root/'src/general'/new).read_text()
        # Remove only the explicitly added promotion comment and observer
        # assignment/guard, restoring the original fprintf indentation.
        restored = promoted.split(' */\n', 1)[1]
        addition = ('    g_general_c1 = c1;\n    g_general_c1_known = 1;\n'
                    '    if (g_general_trace || g_dump_internals)\n        fprintf')
        assert restored.count(addition) == 1
        restored = restored.replace(addition, '    fprintf')
        assert restored == historical, new
        checked.append(dict(original=old, promoted=new, arithmetic_byte_identity=True,
            original_sha256=digest(root/'experiments'/old), promoted_sha256=digest(root/'src/general'/new)))
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); root = args.root.resolve(); out = args.output_dir.resolve()
    assert not out.exists()
    source = (root/'src/fsincos_skylake.c').read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == package.SOURCE_SHA
    old_source = root/CURRENT/'h1708_pre_promotion/fsincos_skylake.c'
    assert digest(old_source) == OLD_SHA
    original_candidate = root/CURRENT/'h1638_tiny_c_transfer/candidate_O2'
    assert digest(original_candidate) == OLD_CANDIDATE_SHA
    headers = header_identity(root)
    banks, evidence = regression.inventory(root)
    out.mkdir(parents=True)
    binaries = {}; warnings = {}
    configs = {'old': ['-O2'], 'default': ['-O2'], 'O0': ['-O0'],
        'O2': ['-O2'], 'O3': ['-O3'],
        'ubsan': ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=all']}
    for label, flags in configs.items():
        binary = out/label
        text = old_source.read_text() if label == 'old' else source
        trace = [] if label in ('old', 'default') else ['-DG_GENERAL_TRACE=1']
        result = subprocess.run(['cc', *flags, *trace, '-Wall', '-Wextra',
            '-Wno-unused-const-variable', '-std=c11', '-I', str(root/'src'),
            '-x', 'c', '-', '-lm', '-o', str(binary)], input=text, text=True,
            capture_output=True, check=True)
        (out/(label+'.build.log')).write_text(result.stderr)
        warnings[label] = Counter(re.findall(r'warning: (.+?) \[(-W[^\]]+)\]', result.stderr))
        test = run(binary, ['--selftest'])
        assert test.stdout == 'SELFTEST: ok\n' and not test.stderr
        binaries[label] = binary
    assert warnings['old'] == warnings['default'], 'New compiler diagnostic'
    operands = set()
    for bank in banks:
        lines = (root/bank['inputs']).read_text().splitlines()
        step = max(1, len(lines)//64)
        operands.update(lines[::step])
    rng = random.Random(0x1708)
    for _ in range(4096):
        # Valid finite inputs spanning tiny, polynomial, reduction and C2.
        exponent = rng.choice([0, 1, 0x3fbb, 0x3fde, 0x3ffd, 0x3ffe,
                               0x3fff, 0x4000, 0x403d, 0x403e, rng.randrange(0x7fff)])
        operands.add(f'{exponent | (rng.randrange(2)<<15):04x} {rng.getrandbits(63)|(1<<63):016x}')
    for exponent in (0, 1, 0x3fbb, 0x3fde, 0x3fff, 0x403e, 0x7fff):
        for sign in (0, 0x8000):
            for significand in (0, 1, (1<<63)-1, 1<<63, (1<<63)+1, 0xc000000000000000, (1<<64)-1):
                operands.add(f'{exponent|sign:04x} {significand:016x}')
    operands = sorted(operands)
    cross = Counter()
    for mode in ('rn', 'rd', 'ru', 'rz'):
        flags = ['--batch', '--rc='+mode]
        old = run(binaries['old'], flags, operands)
        new = run(binaries['default'], flags, operands)
        assert old.stdout == new.stdout and not old.stderr and not new.stderr
        cross['paired_FSINCOS_preserved'] += len(operands)
        for insn in ('fsin', 'fcos'):
            old = regression.cmodel.run(original_candidate, insn, mode, operands)
            for label in ('O0', 'O2', 'O3', 'ubsan'):
                new = regression.cmodel.run(binaries[label], insn, mode, operands)
                assert new == old, (label, insn, mode)
                cross['standalone_output_and_metadata_equal'] += len(operands)
            new = run(binaries['default'], flags+['--'+insn+'-standalone'], operands)
            assert new.stdout == old[2] and not new.stderr
            cross['quiet_default_output_equal'] += len(operands)
    interface = regression.cli_tests(root/'src/general/fsin_fcos_candidate')
    frontier = regression.frontier(root, binaries['O2'])
    assert not any(r['misses'] for r in frontier.values())
    totals = Counter()
    for index, bank in enumerate(banks):
        scored = regression.score_bank(root, binaries['O2'], bank)
        save(out/f'bank_{index:03d}.json', scored)
        totals.update(scored['counts'])
        print(bank['tag'], json.dumps(scored['counts'], sort_keys=True), flush=True)
    report = dict(experiment='h1708_verify_promotion', status='FAIL' if
        totals['output_misses'] or totals['C1_misses'] else 'PASS_DEFAULT_STANDALONE_PROMOTION',
        counts=dict(totals), banks=len(banks), cross_build=dict(cross), software_operands=len(operands),
        frontier=frontier, interface=interface, headers=headers,
        warning_count=sum(warnings['default'].values()), new_compiler_warnings=0,
        hardware_execution='none', private_access='none', paired_FSINCOS_promoted=False,
        boundary='Retained output/C1 appearances; paired tests establish no promotion drift, not hardware correctness.',
        sha256=dict(script=digest(Path(__file__)), main_source=digest(root/'src/fsincos_skylake.c'),
            old_main_source=OLD_SHA, old_candidate=OLD_CANDIDATE_SHA,
            binaries={k:digest(v) for k,v in binaries.items()}, evidence=evidence))
    save(out/'report.json', report)
    print(report['status'], json.dumps(dict(totals), sort_keys=True), flush=True)
    if report['status'] == 'FAIL': raise SystemExit(1)


if __name__ == '__main__': main()
