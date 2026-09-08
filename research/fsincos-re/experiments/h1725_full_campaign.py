#!/usr/bin/env python3
"""Full corpus campaign preparation. No hardware execution in this module.

Historical PC-unknown evidence is a reuse exclusion, never credited as a
PC64 capture. Public corpus membership is likewise not a hardware label.
The campaign preserves the default implementation and every old artifact.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'corpus-suite'))
import suite
from h1719_run_saved_suite import PINS

HOSTS = {'i7': '142.132.217.243', 'skylake': '45.32.204.118'}
BASE = ROOT / 'tmp/ledger33/current/h1725_full_campaign'
CORPUS = 'x87-trig-v1-2126cf9ff5272e9d'
INSNS = ('fsin', 'fcos', 'fsincos')
MODES = ('rn', 'rd', 'ru', 'rz')


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def bit(insn, mode):
    return 1 << (4 * INSNS.index(insn) + MODES.index(mode))


def prepare():
    BASE.mkdir(parents=True, exist_ok=False)
    manifest = suite.verify_dataset(ROOT / 'corpus-suite/corpus-v1')
    assert manifest['corpus_id'] == CORPUS
    for name, expected in PINS.items():
        assert suite.digest(ROOT / name) == expected, name
    save(BASE / 'CAMPAIGN.json', dict(
        status='PREPARING_FULL_MATRIX_NO_NEW_CAPTURE_YET',
        corpus_id=CORPUS, operands=42289770, cases_per_cpu=507477240,
        instructions=INSNS, rounding_modes=MODES, precision_control=64,
        hosts=HOSTS, model_pins=PINS,
        corpus_manifest_sha256=suite.digest(ROOT / 'corpus-suite/corpus-v1/MANIFEST.json'),
        authorization='User explicitly requested execution of the full corpus on both hosts.',
        policy='Reuse observations; preserve all old reservations; no recapture or automatic instruction retry.',
        created_unix=time.time(), paper_changed=False, algorithm_changed=False))
    sources = json.loads((ROOT / 'corpus-suite/corpus-v1/sources.json').read_text())
    by_hash = collections.defaultdict(list)
    for s in sources:
        if 'sha256' in s:
            by_hash[s['sha256']].append(s['index'])
        for e in s.get('evidence', []):
            if e.get('path', '').endswith('_inputs.txt'):
                by_hash[e['sha256']].append(s['index'])
    for host in HOSTS:
        d = BASE / host
        d.mkdir()
        old = ROOT / f'tmp/ledger33/current/h1719_two_host_replay/{host}-bulk/results'
        inv = json.loads((old / 'inventory.json').read_text())
        evidence = json.loads((old / 'evidence.json').read_text())
        masks = collections.defaultdict(int)
        unmapped = []
        for job in inv['jobs']:
            sha = evidence[job['inputs']]['sha256']
            groups = by_hash.get(sha, [])
            if not groups:
                unmapped.append(job)
            for group in groups:
                masks[group] |= bit(job['instruction'], job['mode'])
        save(d / 'legacy-source-exclusions.json', dict(
            source_masks=dict(masks), unmapped_jobs=unmapped,
            historical_input_files=evidence,
            inventory_sha256=suite.digest(old / 'inventory.json'),
            reason='Observed instruction/RC with legacy PC provenance: exclude recapture, do not credit full-PC64 coverage.',
            hardware_execution='none'))
    print(json.dumps(dict(status='PREPARED', corpus_id=CORPUS, cases_per_cpu=507477240)), flush=True)


def snapshot(host):
    """Read-only snapshots; old capture ledgers and files remain on each host."""
    dest = BASE / host
    paths = {'i7': ['/root/h1722-policy2-confidence/ledger.sqlite'],
             'skylake': ['/root/fsincos-h1715-suite/ledger.sqlite']}[host]
    for index, path in enumerate(paths):
        target = dest / f'prior-ledger-{index}.sqlite'
        with target.open('xb') as out:
            subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                            'root@' + HOSTS[host], 'cat ' + path], stdout=out, check=True)
        with sqlite3.connect('file:' + str(target) + '?mode=ro', uri=True) as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            counts = db.execute('SELECT cpu,state,count(*) FROM reservations GROUP BY cpu,state').fetchall()
        save(dest / f'prior-ledger-{index}.json', dict(remote_path=path,
            sha256=suite.digest(target), counts=counts, source_preserved=True))
        print(host, 'ledger snapshot', counts, flush=True)


def census(host):
    """Read every corpus operand; count exact per-source reuse exclusions."""
    cfg = json.loads((BASE / host / 'legacy-source-exclusions.json').read_text())
    masks = {int(k): v for k, v in cfg['source_masks'].items()}
    count = collections.Counter()
    db = sqlite3.connect('file:' + str(ROOT / 'corpus-suite/corpus-v1/catalog.sqlite') + '?mode=ro', uri=True)
    for op, profiles, sources in db.execute('SELECT op,profiles,sources FROM operands ORDER BY op'):
        mask = 0
        for index, value in masks.items():
            if sources & (1 << index):
                mask |= value
        count['operands'] += 1
        count['legacy_excluded_cases'] += mask.bit_count()
        count['not_yet_resolved_cases'] += 12 - mask.bit_count()
        if count['operands'] % 1000000 == 0:
            print(host, dict(count), flush=True)
    assert count['operands'] == 42289770
    save(BASE / host / 'initial-census.json', dict(counts=dict(count),
        status='INITIAL_SOURCE_CENSUS_NOT_FRESHNESS_CLEARANCE',
        limits='Additional public/private records, generated domains and persistent ledgers still require exclusion; missing is not fresh.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'snapshot', 'census'))
    p.add_argument('--host', choices=HOSTS)
    a = p.parse_args()
    if a.action == 'prepare': prepare()
    elif a.action == 'snapshot': snapshot(a.host)
    else: census(a.host)
