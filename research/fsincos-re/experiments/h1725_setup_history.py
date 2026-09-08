#!/usr/bin/env python3
"""Prepare public remote audit configs; never include supplemental material."""
import json
import subprocess
import sys
from h1725_full_campaign import ROOT, BASE, HOSTS, save

for host in (() if len(sys.argv)>1 else HOSTS):
    cfg=json.loads((BASE/host/'legacy-source-exclusions.json').read_text())
    evidence=cfg['historical_input_files']
    inv=json.loads((ROOT/f'tmp/ledger33/current/h1719_two_host_replay/{host}-bulk/results/inventory.json').read_text())
    roots=json.loads((ROOT/f'tmp/ledger33/current/h1721_freshness/{host}-native-remote.json').read_text())['roots']
    roots=sorted(set(roots+['/root/h1722-policy2-confidence']))
    save(BASE/host/'public-history-config.json',dict(
        roots=roots,mapped_input_hashes=sorted({evidence[j['inputs']]['sha256'] for j in inv['jobs']}),
        software_only_roots=['/root/h1719-policy2-verifier','/root/review-p2','/root/fsincos-review-p2'],
        reason='Authenticated H1719 software replay/build copies are not fresh hardware evidence. Native original input banks are separately mapped.',
        private_material_included=False))
if len(sys.argv)==1:
    print('Public history configurations prepared for both hosts.')
else:
    host=sys.argv[1];address='root@'+HOSTS[host]
    remote='/root/h1725-full-corpus'
    subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',address,'mkdir -p '+remote],check=True)
    subprocess.run(['scp',str(ROOT/'experiments/h1725_public_history.py'),str(BASE/host/'public-history-config.json'),address+':'+remote+'/'],check=True)
    with (BASE/host/'public-history-possible-inputs.txt.gz').open('xb') as out,(BASE/host/'public-history.log').open('x') as log:
        subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',address,
            'python3 '+remote+'/h1725_public_history.py --config '+remote+'/public-history-config.json'],stdout=out,stderr=log,check=True)
    print(host,'public history audit completed.',flush=True)
