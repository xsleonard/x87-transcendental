"""Explicit independent FPTAN campaign steps. No capture retries.

Inputs are frozen before the local candidate is executed. Only public input
streams and generic capture/guard code reach the authorized research hosts.
"""
import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from protocol import make_line, parse
from support import BASE, HERE, ROOT, copy, digest, lines, read, save

HOSTS = {'skylake': ('45.32.204.118', '00050654', '0x1', 't0002'),
         'i7': ('142.132.217.243', '000506e3', '0xf0', 't0003')}
AUDIT_REMOTE = '/root/fptan-audit-t0001'
PUBLIC = ('capture.c', 'protocol.py', 'support.py', 'guard.py')


def ssh(host):
    return ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', 'root@' + HOSTS[host][0]]


def local_clearance():
    out = BASE / 't0001-clearance'
    out.mkdir(exist_ok=False)
    pool = BASE / 't0001-inputs'
    receipt = read(pool / 'INPUT-POOL-FROZEN.json')
    for name, sha in receipt['files'].items():
        assert digest(pool / name) == sha
    sys.path.insert(0, str(ROOT / 'experiments'))
    from h1725_select_full import private_signatures
    from h1721_policy2_challenge import possible_old_generator
    private, _ = private_signatures()
    public = [sqlite3.connect('file:' + str(ROOT / 'tmp/ledger33/current/h1725_full_campaign' / host / 'possible-history.sqlite') + '?mode=ro', uri=True) for host in HOSTS]
    corpus = sqlite3.connect('file:' + str(ROOT / 'corpus-suite/corpus-v1/catalog.sqlite') + '?mode=ro', uri=True)
    counts = Counter()
    with gzip.open(out / 'proposals.txt.gz', 'xt') as proposals, gzip.open(out / 'categories.tsv.gz', 'xt') as categories:
        for line in lines(pool / 'operand-pool.tsv.gz'):
            operand, kind = line.rstrip().split('\t')
            se, sig = (int(v, 16) for v in operand.split())
            counts['generated_operands'] += 1
            if sig in private:
                counts['private_holds'] += 1
                continue
            if not sig & 2047:
                counts['binary64_domain_holds'] += 1
                continue
            if not 0 < se & 32767 < 32767 or not sig >> 63 or (se & 32767 == 16383 and sig == 1 << 63):
                counts['non_normal_or_unit_holds'] += 1
                continue
            if possible_old_generator(operand):
                counts['known_generator_holds'] += 1
                continue
            if corpus.execute('SELECT 1 FROM operands WHERE op=?', (operand,)).fetchone() or any(db.execute('SELECT 1 FROM possible WHERE op=?', (operand,)).fetchone() for db in public):
                counts['public_or_corpus_holds'] += 1
                continue
            proposals.write(operand + '\n')
            categories.write(operand + '\t' + kind + '\n')
            counts['locally_cleared_operands'] += 1
    for db in public + [corpus]:
        db.close()
    del private
    save(out / 'LOCAL-CLEARANCE.json', dict(status='LOCAL_CLEARANCE_COMPLETE_REMOTE_PENDING', counts=counts,
        input_pool_sha256=digest(pool / 'INPUT-POOL-FROZEN.json'), proposals_sha256=digest(out / 'proposals.txt.gz'),
        private_details_exported=False, hardware_executed=False,
        limits='Conservative visible-history holds; no claim of knowledge of unavailable records or unknown raw80 generator seeds.'))
    print('LOCAL CLEARANCE', json.dumps(counts), flush=True)


def history(host):
    out = BASE / 't0001-clearance'
    assert digest(out / 'proposals.txt.gz') == read(out / 'LOCAL-CLEARANCE.json')['proposals_sha256']
    subprocess.run(ssh(host) + ['mkdir ' + AUDIT_REMOTE], check=True)
    subprocess.run(['scp', str(out / 'proposals.txt.gz'), str(HERE / 'history.py'),
                    'root@' + HOSTS[host][0] + ':' + AUDIT_REMOTE + '/'], check=True)
    with (out / (host + '-history.json')).open('xb') as dest:
        subprocess.run(ssh(host) + ['python3 ' + AUDIT_REMOTE + '/history.py ' + AUDIT_REMOTE], stdout=dest, check=True)
    report = read(out / (host + '-history.json'))
    assert report['status'] == 'PUBLIC_HISTORY_INTERSECTION_COMPLETE'
    print(host, 'public history checked', report['counts'], 'holds', len(report['held_operands']), flush=True)


def freeze():
    source = BASE / 't0001-clearance'
    local = read(source / 'LOCAL-CLEARANCE.json')
    assert digest(source / 'proposals.txt.gz') == local['proposals_sha256']
    reports = {host: read(source / (host + '-history.json')) for host in HOSTS}
    assert all(r['status'] == 'PUBLIC_HISTORY_INTERSECTION_COMPLETE' for r in reports.values())
    held = set().union(*(set(r['held_operands']) for r in reports.values()))
    sky = BASE / 't0002'
    sky.mkdir()
    counts = Counter()
    with gzip.open(sky / 'inputs.txt.gz', 'xt') as inputs, gzip.open(sky / 'categories.tsv.gz', 'xt') as categories:
        for index, line in enumerate(lines(source / 'categories.tsv.gz')):
            operand, family = line.rstrip().split('\t')
            if operand in held:
                counts['remote_history_holds'] += 1
                continue
            se, sig = (int(v, 16) for v in operand.split())
            counts['operands'] += 1
            for pc in ((24, 53, 64) if index % 257 == 0 else (64,)):
                for rc in ('rn', 'rd', 'ru', 'rz'):
                    request = make_line(rc, pc, se, sig)
                    inputs.write(request + '\n')
                    categories.write(request.split()[0] + '\t' + family + '\n')
                    counts['rows'] += 1
                    counts['family:' + family] += 1
    save(sky / 'INPUTS-FROZEN.json', dict(status='FROZEN_BEFORE_CANDIDATE_PREDICTIONS', counts=counts,
        input_sha256=digest(sky / 'inputs.txt.gz'), category_sha256=digest(sky / 'categories.tsv.gz'),
        candidate_evaluated_on_these_inputs=False, hardware_executed=False))
    save(sky / 'CLEARANCE.json', dict(status='CLEARED_COMMON_TWO_HOST_INPUTS', rows=counts['rows'],
        input_sha256=digest(sky / 'inputs.txt.gz'),
        local_clearance_sha256=digest(source / 'LOCAL-CLEARANCE.json'),
        public_history_sha256={host: digest(source / (host + '-history.json')) for host in HOSTS},
        original_proposals_sha256=local['proposals_sha256'], local_counts=local['counts'], final_counts=counts,
        private_details_exported=False, binary64_domain_excluded=True,
        limits=local['limits']))
    sources = ['src/fsincos_skylake.c', 'src/ia64_sf.h', 'src/p5_rom_constants.h', 'src/f2xm1_constants.h',
               'data/frcpa-recip-table.h', 'src/general/standalone_polynomial.h', 'src/general/standalone_table.h',
               'src/general/standalone_tiny.h', 'src/general/paired.h']
    sources += ['fptan-re/' + name for name in ('predict.c', 'independent_inputs.py', 'math_bounds.c', 'campaign.py', 'history.py', *PUBLIC)]
    save(sky / 'SOURCE-PINS.json', {name: digest(ROOT / name) for name in sources})
    for name in sources:
        target = sky / 'local-only-source-snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copy(ROOT / name, target)
        assert digest(target) == digest(ROOT / name)
    publication = [ROOT / 'paper/skylake-x87.tex', ROOT / 'paper/skylake-x87.pdf',
                   ROOT.parent / 'output/pdf/skylake-fpatan.pdf', ROOT / 'fpatan-re/PSEUDOCODE.md',
                   ROOT / 'fpatan-re/paper/skylake-fpatan.tex']
    save(sky / 'PUBLICATION-PINS.json', {str(p.relative_to(ROOT.parent)): digest(p) for p in publication if p.is_file()})
    print('INPUTS FROZEN', json.dumps(counts), flush=True)
    # Execute the candidate only now; neither its outputs nor status can
    # remove an input from this immutable stream.
    original = gzip.decompress((sky / 'inputs.txt.gz').read_bytes())
    outputs = []
    for binary in ('/private/tmp/fptan-t0001-predict', '/private/tmp/fptan-t0001-predict-sanitized'):
        run = subprocess.run([binary], input=original, capture_output=True, check=True,
                             env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})
        assert not run.stderr
        assert len(run.stdout.splitlines()) == counts['rows']
        outputs.append(run.stdout)
    assert outputs[0] == outputs[1]
    with gzip.open(sky / 'predictions.txt.gz', 'xb') as dest:
        dest.write(outputs[0])
    save(sky / 'C-PREFLIGHT.json', dict(rows=counts['rows'], optimized_sanitized_differences=0,
        binaries={name: digest(name) for name in ('/private/tmp/fptan-t0001-predict', '/private/tmp/fptan-t0001-predict-sanitized')},
        candidate_source_sha256=digest(ROOT / 'src/fsincos_skylake.c'), source_pins_sha256=digest(sky / 'SOURCE-PINS.json'),
        expected_fields=['tangent', 'pushed_value', 'C2', 'C1'], exception_latch_prediction=False))
    for host, (address, signature, microcode, name) in HOSTS.items():
        job = BASE / name
        if job != sky:
            job.mkdir()
            for filename in ('inputs.txt.gz', 'categories.tsv.gz', 'predictions.txt.gz', 'INPUTS-FROZEN.json', 'CLEARANCE.json', 'SOURCE-PINS.json', 'C-PREFLIGHT.json'):
                copy(sky / filename, job / filename)
        save(job / 'MANIFEST.json', dict(status='FROZEN_UNOPENED', rows=counts['rows'], host=address,
            signature=signature, microcode=microcode,
            files={filename: digest(job / filename) for filename in ('inputs.txt.gz', 'predictions.txt.gz', 'categories.tsv.gz')},
            public_sources={filename: digest(HERE / filename) for filename in PUBLIC},
            clearance_sha256=digest(job / 'CLEARANCE.json'),
            candidate_source_sha256=digest(ROOT / 'src/fsincos_skylake.c'),
            privacy='No candidate code, predictions, private source or ledger is uploaded.'))
    print('PASS both complete C preflights and two-host freeze', counts['rows'], flush=True)


def stage(host):
    address, _, _, name = HOSTS[host]
    job, remote = BASE / name, '/root/fptan-re/' + name
    manifest = read(job / 'MANIFEST.json')
    for file, sha in manifest['files'].items():
        assert digest(job / file) == sha
    subprocess.run(ssh(host) + ['mkdir -p /root/fptan-re && mkdir ' + remote], check=True)
    files = [job / n for n in ('inputs.txt.gz', 'MANIFEST.json', 'CLEARANCE.json')] + [HERE / n for n in PUBLIC]
    subprocess.run(['scp', *(str(p) for p in files), 'root@' + address + ':' + remote + '/'], check=True)
    run = subprocess.run(ssh(host) + ['cd ' + remote + ' && gcc -O2 -std=c11 -Wall -Wextra -Werror capture.c -o capture && ./capture --identity && objdump -d capture'], capture_output=True, text=True, check=True)
    opcodes = [line for line in run.stdout.splitlines() if '\tfptan' in line]
    assert len(opcodes) == 1
    save(job / 'STAGED.json', dict(identity=run.stdout.splitlines()[0], fptan_opcodes=opcodes,
        files={p.name: digest(p) for p in files}, hardware_executed=False))
    print(host, run.stdout.splitlines()[0], opcodes, flush=True)


def capture(host):
    _, _, _, name = HOSTS[host]
    job = BASE / name
    assert (job / 'STAGED.json').exists()
    save(job / 'DISPATCHED.json', dict(status='DISPATCHED_DO_NOT_RETRY', host=host,
        manifest_sha256=digest(job / 'MANIFEST.json')))
    run = subprocess.run(ssh(host) + ['python3 /root/fptan-re/' + name + '/guard.py ' + name], capture_output=True, text=True)
    save(job / 'SSH-RETURN.json', dict(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr))
    print(run.stdout, run.stderr, flush=True)
    assert run.returncode == 0, 'Inspect reserved/partial results; never retry capture'


def fetch(host):
    _, _, _, name = HOSTS[host]
    job = BASE / name
    for filename in ('STARTED.json', 'COMPLETE.json', 'hardware.txt.gz', 'hardware.stderr'):
        with (job / filename).open('xb') as dest:
            subprocess.run(ssh(host) + ['cat /root/fptan-re/' + name + '/' + filename], stdout=dest, check=True)
    complete = read(job / 'COMPLETE.json')
    assert complete['manifest_sha256'] == digest(job / 'MANIFEST.json')
    assert complete['hardware_gzip_sha256'] == digest(job / 'hardware.txt.gz')
    print('Authenticated', host, complete['rows'], 'rows', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=('local-clearance', 'history', 'freeze', 'stage', 'capture', 'fetch'))
    parser.add_argument('--host', choices=HOSTS)
    args = parser.parse_args()
    if args.step == 'local-clearance':
        local_clearance()
    elif args.step == 'freeze':
        freeze()
    else:
        assert args.host
        globals()[args.step](args.host)
