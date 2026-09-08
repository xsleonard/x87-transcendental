"""Verify a readability-only C change and literal ROM provenance.

All captures are read-only. Compiler token comparison excludes comments and
whitespace but includes every executable token and literal after preprocessing.
Original comments must survive in order. Output reports are exclusive-create.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

from compressed_guard import digest
from d0008_schedule_replay import BASE
from prepare import save

HERE = Path(__file__).resolve().parent


def compiler_tokens(path):
    result = subprocess.run(
        ['clang', '-fsyntax-only', '-I/opt/homebrew/include',
         '-Xclang', '-dump-tokens', str(path)],
        capture_output=True, text=True, check=True)
    lines = result.stderr.splitlines()
    assert lines and all('\t' in line and 'Loc=<' in line for line in lines)
    return [line.split('\t', 1)[0] for line in lines]


def provenance():
    source = HERE / 'fpatan_candidate.c'
    table = HERE.parent / 'data/pentium-rom/rom-constants.tsv'
    page = table.with_name('righto-pentium-fpu-rom.html')
    with table.open() as stream:
        rows = {int(r['row']): r for r in csv.DictReader(stream, delimiter='\t')}
    block = re.search(r'<table class="rom">(.*?)</table>', page.read_text(), re.S)[1]
    published = {}
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', block, re.S):
        cells = [html.unescape(re.sub('<[^>]+>', '', cell)).strip()
                 for cell in re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S)]
        if cells:
            published[int(cells[0])] = cells[1:5]
    literals = re.findall(
        r'\{\s*(\d+)\s*,\s*([01])\s*,\s*(-?\d+)\s*,\s*"([0-9a-f]+)"\s*\}',
        source.read_text())
    wanted = [19, 20, *range(114, 124), *range(125, 157)]
    assert [int(t[0]) for t in literals] == wanted
    for index, sign, scale, significand in literals:
        row = rows[int(index)]
        assert [row[k] for k in ('exp', 'sign', 'flag', 'sig68')] == published[int(index)]
        assert row['flag'] == '0'
        assert sign == row['sign'] and significand == row['sig68']
        assert int(scale) == int(row['exp'], 16) - 0xffff - 66
    return dict(constants_checked=len(literals), rows=wanted,
                all_literal_bits_match_published_p5=True,
                exponent_conversion='scale = published_exponent - 0xffff - 66',
                source_url='https://www.righto.com/2025/01/pentium-floating-point-ROM.html',
                tsv_sha256=digest(table), archived_page_sha256=digest(page),
                limit='P5 physical decode; not a physical Skylake ROM dump.')


def command(argv, label):
    result = subprocess.run(argv, cwd=HERE, capture_output=True, text=True)
    record = dict(command=argv, returncode=result.returncode,
                  stdout=result.stdout, stderr=result.stderr)
    save(BASE / f'd0029-{label}.json', record)
    assert result.returncode == 0, (label, record)
    return dict(command=argv, returncode=result.returncode)


def replay(binary, label):
    report_path = BASE / f'd0029-{label}-full-replay.json'
    argv = ['python3', str(HERE / 'verify_delivery.py'),
            '--binary', str(binary), '--out', str(report_path)]
    with (BASE / f'd0029-{label}-replay.log').open('x') as log:
        result = subprocess.run(argv, cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
    assert result.returncode == 0, label
    report = json.loads(report_path.read_text())
    baseline = json.loads((BASE / 'd0027-main-full-replay.json').read_text())
    assert report['counts'] == baseline['counts']
    assert report['jobs'].keys() == baseline['jobs'].keys()
    for name, row in report['jobs'].items():
        for field in ('hardware_sha256', 'output_sha256'):
            assert row[field] == baseline['jobs'][name][field]
    print('PASS', label, report['counts'], flush=True)
    return dict(report_sha256=digest(report_path), counts=report['counts'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    args = parser.parse_args()
    source = HERE / 'fpatan_candidate.c'
    old_delivery = json.loads((BASE / 'd0027-delivery-checks.json').read_text())
    assert digest(args.before) == old_delivery['source_sha256']['fpatan_candidate.c']
    tokens = compiler_tokens(source)
    assert tokens == compiler_tokens(args.before)
    assert tokens == compiler_tokens(HERE / 'fpatan_candidate_v7.c')
    comments = lambda p: [re.sub(r'\s+', ' ', s) for s in
                          re.findall(r'/\*.*?\*/', p.read_text(), re.S)]
    old_comments, new_comments = comments(args.before), comments(source)
    cursor = 0
    for comment in old_comments:
        cursor = new_comments.index(comment, cursor) + 1
    rom = provenance()
    source_hash = digest(source)
    archive = Path(old_delivery['bundle'])
    assert digest(archive) == old_delivery['bundle_sha256']
    record = dict(status='LOCAL_STYLE_VERIFICATION_STARTED',
                  hardware_executed=False, before_sha256=digest(args.before),
                  after_sha256=source_hash, before_snapshot=str(args.before),
                  compiler_tokens_identical=True,
                  token_count=len(tokens),
                  token_sha256=hashlib.sha256('\n'.join(tokens).encode()).hexdigest(),
                  original_comments_preserved=len(old_comments), provenance=rom)
    save(BASE / 'd0029-style-started.json', record)
    print('PASS compiler-token identity, all original comments, 44 literal ROM entries', flush=True)
    work = args.before.parent
    checks = {}
    checks['clang'] = command(
        ['make', 'all', 'check', 'CC=clang', f'BUILD_DIR={work / "clang"}'], 'clang-build')
    flags = '-O1 -g -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all'
    checks['sanitized'] = command(
        ['make', 'all', 'check', 'CC=clang', f'BUILD_DIR={work / "sanitized"}',
         f'CFLAGS={flags}'], 'sanitized-build')
    checks['gcc'] = command(
        ['make', 'all', 'check', 'CC=gcc-15', f'BUILD_DIR={work / "gcc15"}'], 'gcc-build')
    checks['static'] = command(
        ['clang', '--analyze', '-std=c11', '-Wall', '-Wextra', '-Werror',
         '-I/opt/homebrew/include', '-Xanalyzer', '-analyzer-output=text',
         'fpatan_candidate.c', 'fpatan_library.c'], 'static-analysis')
    assert not json.loads((BASE / 'd0029-static-analysis.json').read_text())['stderr']
    print('PASS Clang/GCC/sanitized builds, CLI/library checks and static analysis', flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(replay, work / 'clang/fpatan', 'clang')
        b = pool.submit(replay, work / 'sanitized/fpatan_batch', 'sanitized-library')
        replays = {'clang': a.result(), 'sanitized_library': b.result()}
    assert digest(source) == source_hash
    assert digest(archive) == old_delivery['bundle_sha256']
    checks['diff'] = command(['git', 'diff', '--check'], 'diff-check')
    record.update(status='PASS', checks=checks, replays=replays,
                  numerical_algorithm_changed=False, archive_unchanged=True,
                  archive_sha256=digest(archive), script_sha256=digest(Path(__file__)))
    save(BASE / 'd0029-style-verification.json', record)
    print('PASS readability/provenance audit; all saved observations still exact', flush=True)


if __name__ == '__main__':
    main()
