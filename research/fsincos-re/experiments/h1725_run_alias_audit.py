#!/usr/bin/env python3
"""Public-only read-only alias audit with results retained locally."""
import json
import subprocess
import sys
from h1725_full_campaign import BASE,ROOT,HOSTS,save
host=sys.argv[1];out=BASE/host
cfg=json.loads((out/'public-history-config.json').read_text())
old=ROOT/f'tmp/ledger33/current/h1719_two_host_replay/{host}-bulk/results'
inv=json.loads((old/'inventory.json').read_text());ev=json.loads((old/'evidence.json').read_text())
cfg['known_inputs']={j['inputs']:ev[j['inputs']] for j in inv['jobs']}
path=out/'alias-config.json';save(path,cfg)
remote='/root/h1725-full-corpus';address='root@'+HOSTS[host]
subprocess.run(['scp',str(path),str(ROOT/'experiments/h1725_alias_audit.py'),address+':'+remote+'/'],check=True)
with (out/'alias-audit.json').open('x') as f:
    subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',address,
        'python3 '+remote+'/h1725_alias_audit.py --config '+remote+'/alias-config.json'],stdout=f,check=True)
result=json.loads((out/'alias-audit.json').read_text())
print(host,'additional input aliases',len(result['aliases']),flush=True)
