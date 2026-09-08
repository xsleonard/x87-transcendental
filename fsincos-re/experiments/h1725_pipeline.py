#!/usr/bin/env python3
"""Continue audit -> fixed selection -> one-shot capture without manual gates.

No retries are implemented. Failure stops this host's pipeline and preserves
all reservations and evidence. This can be left running for the full job.
"""
import argparse
import json
import subprocess
import sys
import time
from h1725_full_campaign import ROOT,BASE,HOSTS,save
from h1725_run_full import setup,run


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',choices=HOSTS,required=True)
    a=p.parse_args();host=a.host;out=BASE/host
    setup(host)
    save(out/'PIPELINE_STARTED.json',dict(status='AUDIT_THEN_SELECT_THEN_CAPTURE',started=time.time(),
        automatic_retries=False,hardware_started=False))
    print(host,'pipeline active; waiting for the public audit to seal, then selecting and capturing automatically.',flush=True)
    while True:
        path=out/'public-history.log'
        lines=path.read_text().splitlines() if path.exists() else []
        if lines:
            try:last=json.loads(lines[-1])
            except json.JSONDecodeError:last={}
            if last.get('status')=='PUBLIC_HISTORY_EXPORT_COMPLETE':break
            if any('Traceback' in line or 'Connection' in line or 'terminated' in line.lower() for line in lines):
                raise RuntimeError('public audit failed; no capture permitted')
        time.sleep(10)
    subprocess.run([sys.executable,str(ROOT/'experiments/h1725_select_full.py'),'--host',host],check=True)
    run(host)


if __name__=='__main__':main()
