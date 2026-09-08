#!/usr/bin/env python3
"""Copy sealed remote observations and optionally decode portable datasets.

Observer only: no dispatch, capture, remote deletion, or dependency of server
progress on this program. Transfers/decodes may be repeated, never native x87.
"""
import argparse
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import tarfile
import tempfile
from pathlib import Path

from h1725_full_campaign import BASE, HOSTS, suite
from h1725_decode_autonomous import decode
from h1725_autonomous import durable, save


def remote(host, command):
    return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                                    'root@' + HOSTS[host], command], timeout=60)


def collect(host, expand=False, limit=None):
    out = BASE / host; marker = json.loads((out / 'AUTONOMOUS_CUTOVER.json').read_text())
    root = marker['remote_package']; package = BASE / ('autonomous-' + host + '-20260907')
    dest = out / 'autonomous-observed'; dest.mkdir(exist_ok=True)
    script = '''import hashlib,json,pathlib
p=pathlib.Path(ROOT)/'observed'; files={}
for done in sorted(p.glob('job-*.DONE.json')):
 r=json.loads(done.read_text()); a=p/(done.name.replace('.DONE.json','.json.gz'))
 if hashlib.sha256(a.read_bytes()).hexdigest()!=r['archive_sha256']:raise ValueError('changed observation archive')
 files[a.name]=r['archive_sha256']; files[done.name]=hashlib.sha256(done.read_bytes()).hexdigest()
print(json.dumps(files))'''.replace('ROOT', repr(root))
    inventory = json.loads(remote(host, shlex.join(['python3', '-c', script])))
    assert all(re.fullmatch(r'job-[0-9]{6}\.(json\.gz|DONE\.json)', n) for n in inventory)
    jobs = sorted(n[:-len('.DONE.json')] for n in inventory if n.endswith('.DONE.json'))
    if limit is not None:
        jobs = jobs[:limit]
    names = [job + suffix for job in jobs for suffix in ('.json.gz', '.DONE.json')]
    missing = []
    for name in names:
        if (dest / name).exists():
            assert suite.digest(dest / name) == inventory[name], 'preserve changed local archive; do not overwrite'
        else:
            missing.append(name)
    # Bounded transfer bundles; files with DONE are immutable on the server.
    for start in range(0, len(missing), 100):
        batch = missing[start:start+100]
        data = remote(host, shlex.join(['tar', '-C', root + '/observed', '-cf', '-', *batch]))
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
            members = archive.getmembers()
            assert len(members) == len(batch) and {m.name for m in members} == set(batch)
            for member in members:
                assert member.isfile()
                raw = archive.extractfile(member).read()
                assert hashlib.sha256(raw).hexdigest() == inventory[member.name]
                durable(dest / member.name, raw)
    decoded = 0
    if expand:
        decoded_root = out / 'autonomous-portable'; decoded_root.mkdir(exist_ok=True)
        for job in jobs:
            target = decoded_root / job
            if target.exists():
                assert suite.verify_dataset(target / 'observations')['kind'] == 'hardware_observations'
                continue
            temporary = Path(tempfile.mkdtemp(prefix='decode-', dir=decoded_root)) / job
            decode(package, dest / (job + '.json.gz'), BASE / 'predictor', temporary)
            temporary.rename(target); decoded += 1
    report = dict(host=host, status='SEALED_OBSERVATIONS_COPIED', jobs=len(jobs), newly_copied_files=len(missing),
                  newly_decoded_jobs=decoded, hardware_executions=0, remote_files_removed=0)
    save(dest / ('COLLECTION-' + str(__import__('time').time_ns()) + '.json'), report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--host', choices=HOSTS, required=True)
    p.add_argument('--decode', action='store_true'); p.add_argument('--limit', type=int)
    a = p.parse_args(); collect(a.host, a.decode, a.limit)
