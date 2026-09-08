#!/usr/bin/env python3
"""Build/test an autonomous package locally, without any hardware capture.

Only allowlisted public frozen model/capture code and already-cleared public
input records are exported. No selection/audit implementation, private ledger,
private path inventory, credentials, or historical private labels are copied.
"""
import argparse
import gzip
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'tmp/ledger33/current/h1725_full_campaign'
sys.path.insert(0, str(ROOT / 'corpus-suite'))
from h1725_autonomous import RECORD, CORPUS, save, sha, durable
import suite


def build(out, host, first):
    out.mkdir(); (out / 'src/general').mkdir(parents=True); (out / 'data').mkdir(); (out / 'experiments').mkdir()
    frozen = BASE / 'frozen-model'
    original = json.loads((frozen / 'MANIFEST.json').read_text())
    # Compilable public sources only: no binary, unrelated experiments, or
    # workstation paths from the broader provenance manifest are exported.
    source_pins = {n: h for n, h in original['files'].items()
                   if (n.startswith('src/') and n.endswith(('.c', '.h'))) or n == 'data/frcpa-recip-table.h'}
    for name, digest in source_pins.items():
        if suite.digest(frozen / name) != digest:
            raise ValueError('changed original frozen source')
        shutil.copyfile(frozen / name, out / name)
    for name, source in {
        'h1725_autonomous.py': ROOT / 'experiments/h1725_autonomous.py',
        'h1725_remote_capture.py': frozen / 'experiments/h1725_remote_capture.py',
        'h1725_run_full.py': frozen / 'experiments/h1725_run_full.py',
        'suite.py': ROOT / 'corpus-suite/suite.py',
        'run_capture.py': ROOT / 'corpus-suite/run_capture.py',
        'experiments/h1719_saved_verifier.c': ROOT / 'experiments/h1719_saved_verifier.c',
    }.items():
        shutil.copyfile(source, out / name)
    selection = json.loads((BASE / host / 'SELECTION.json').read_text())
    selected = BASE / host / 'selected.bin'
    if suite.digest(selected) != selection['selected_sha256']:
        raise ValueError('changed frozen selected input stream')
    jobs = {}; offset = 0; cases = 0; digest = hashlib.sha256()
    with selected.open('rb') as source, (out / 'plan.bin').open('xb') as dest:
        source.seek(first * 5000 * RECORD.size); number = first
        while raw := source.read(5000 * RECORD.size):
            if len(raw) % RECORD.size:
                raise ValueError('partial selected input record')
            packed = gzip.compress(raw, compresslevel=9, mtime=0)
            dest.write(packed); digest.update(packed)
            rows = sum(mask.bit_count() for _, _, _, mask in RECORD.iter_unpack(raw)); cases += rows
            jobs[str(number)] = dict(offset=offset, bytes=len(packed), operands=len(raw) // RECORD.size,
                rows=rows, records_sha256=sha(raw), packed_sha256=sha(packed))
            offset += len(packed); number += 1
    save(out / 'PLAN.json', dict(corpus_id=CORPUS, selection_sha256=selection['selected_sha256'],
        first_job=first, end_job=number, jobs=jobs, cases=cases, packed_bytes=offset,
        format='independently gzipped <QHQH> ordinal,se,sig,selected-mask; 5000 operands/job',
        generation='deterministic local expansion of the exact frozen finite corpus, not a new random stream'))
    save(out / 'BUILD.json', dict(host=host, algorithm_pins=original['source_pins'],
        public_source_pins=source_pins, original_mac_predictor_sha256=original['predictor_sha256'],
        plan_sha256=digest.hexdigest(), selection_sha256=selection['selected_sha256'],
        selection_counts=selection['counts'], hardware_executions=0))
    print(json.dumps(dict(host=host, package=str(out), first_job=first, end_job=number,
                          plan_MiB=offset / 2**20, cases=cases)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--host', choices=('i7', 'skylake'), required=True); p.add_argument('--first-job', type=int, required=True)
    a = p.parse_args(); build(a.out, a.host, a.first_job)
