#!/usr/bin/env python3
"""Full retained regression of the promoted main executable, without recapture.

Authenticate historical inventories; retain all misses. Paired and standalone
modes run separately so each can report progress while the other completes.
"""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
import h1709_paired_retained_census as paired
import h1707_packaged_candidate_regression as standalone
from h1709_paired_retained_census import digest, save

SOURCE = '490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32'
HEADER = '3eb199714a2a6d2b67f501ab11a80427d7f389df4df43ed9a6a68329db151454'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--instruction',choices=('paired','standalone'),required=True)
    a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    assert digest(root/'src/fsincos_skylake.c')==SOURCE and digest(root/'src/general/paired.h')==HEADER
    binary=root/'src/fsincos_skylake'; stamp=digest(binary);out.mkdir(parents=True)
    counts=Counter(); reports=[]; frontier=None
    if a.instruction=='paired':
        banks,evidence=paired.inventory(root)
        old=root/'tmp/ledger33/current/h1710_last_retained_census'
        assert digest(old/'report.json')=='4e6300a1b0600c63786e9890d53e444eef8578c49fb846d43b02f23d97f60549'
        old_report=json.loads((old/'report.json').read_text())
        for bank in banks:
            expected=old/(bank['tag']+'.json');assert digest(expected)==old_report['sha256']['banks'][bank['tag']]
            result=paired.score(root,binary,bank,out);reports.append(result);counts.update(result['counts'])
            assert result['model_stdout_sha256']==json.loads(expected.read_text())['model_stdout_sha256']
        frontier=[dict(bank=r['bank']['tag'],**miss) for r in reports for miss in r['misses']]
    else:
        banks,evidence=standalone.inventory(root)
        old=root/'tmp/ledger33/current/h1708_default_promotion'
        assert digest(old/'report.json')=='e047633abe3d59bf08fe63132068e9991950071568f2a851e2820719d37b4685'
        # The canonical binary is run twice only in software: quiet stdout
        # parity and a trace-enabled equivalent build for the retained C1 scorer.
        trace=out/'trace_O2';source=(root/'src/fsincos_skylake.c').read_text()
        built=subprocess.run(['cc','-O2','-std=c11','-DG_GENERAL_TRACE=1','-I',str(root/'src'),
            '-x','c','-','-lm','-o',str(trace)],input=source,text=True,capture_output=True,check=True)
        assert not built.stderr
        for i,bank in enumerate(banks):
            result=standalone.score_bank(root,trace,bank)
            with (root/bank['inputs']).open() as inputs:
                proc=subprocess.run([str(binary),'--batch','--'+bank['instruction']+'-standalone',
                    '--rc='+bank['mode']],stdin=inputs,text=True,capture_output=True,check=True)
            assert not proc.stderr and len(proc.stdout.splitlines())==bank['count']
            sha=hashlib.sha256(proc.stdout.encode()).hexdigest()
            assert sha==result['stdout_sha256']==json.loads((old/f'bank_{i:03d}.json').read_text())['stdout_sha256']
            counts.update(result['counts']);reports.append(result);save(out/f'bank_{i:03d}.json',result)
            print(bank['tag'],json.dumps(result['counts'],sort_keys=True),flush=True)
        frontier=standalone.frontier(root,trace)
    save(out/'frontier.json',frontier)
    assert digest(binary)==stamp and digest(root/'src/fsincos_skylake.c')==SOURCE
    failed=any(v for k,v in counts.items() if 'miss' in k)
    failed|=bool(frontier) if a.instruction=='paired' else any(r['misses'] for r in frontier.values())
    report=dict(experiment='h1713_promoted_regression',instruction=a.instruction,
        status='FAIL' if failed else 'PASS_MAIN_DEFAULT',counts=dict(counts),banks=len(banks),
        hardware_execution='none',private_access='none',default_output_quiet=True,
        boundary='Retained overlapping appearances, not unique or fresh hardware observations.',
        sha256=dict(source=SOURCE,header=HEADER,binary=stamp,script=digest(Path(__file__)),evidence=evidence,
            frontier=digest(out/'frontier.json'),reports={p.name:digest(p) for p in sorted(out.glob('*.json'))}))
    save(out/'report.json',report);print(report['status'],dict(counts),flush=True)
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
