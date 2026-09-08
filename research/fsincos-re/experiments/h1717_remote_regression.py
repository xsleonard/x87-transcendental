#!/usr/bin/env python3
"""Replay saved i7 paired labels locally through the promoted C; no hardware."""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--inputs',required=True,type=Path)
    p.add_argument('--labels',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();base=a.output_dir.resolve();base.mkdir(parents=True,exist_ok=False)
    binary=root/'src/fsincos_skylake'
    report=base/'report.json';assert not report.exists()
    assert digest(root/'src/general/paired.h')=='4eeb671562969e39b334923cbf41a40cb86f2a5ecb3dbad23de320be315b9a5d'
    records=[];separator=[]
    for bank in ('comb7','comb9','comb10'):
        inputs=a.inputs/(bank+'_inputs.txt')
        for mode in ('rn','rd','ru'):
            raw=a.labels/(bank+'_sc_'+mode+'_status.txt');counts=Counter();misses=[]
            with inputs.open() as f,raw.open() as hw:
                while True:
                    batch=[]
                    for _ in range(16384):
                        line=f.readline()
                        if not line:break
                        batch.append(line)
                    if not batch:break
                    p=subprocess.run([str(binary),'--batch','--rc='+mode,'--general-trace'],
                        input=''.join(batch),text=True,capture_output=True,check=True)
                    values=p.stdout.splitlines();assert len(values)==len(batch)
                    meta={}
                    for line in p.stderr.splitlines():
                        w=line.split();assert w[0]=='HPAIR' and len(w)==6
                        meta[int(w[1])]=(int(w[3]),int(w[5]))
                    for i,(op,got) in enumerate(zip(batch,values)):
                        want=hw.readline().split();assert want and want[-2]=='SW'
                        sw=int(want[-1],16);actual=got.split();counts['instruction_rows']+=1
                        bad=[]
                        if actual!=want[:-2]:bad.append('outputs');counts['output_misses']+=1
                        if actual[0]=='OK':
                            counts['lanes']+=2
                            if meta[i][0]:
                                counts['C1_checks']+=1
                                if meta[i][1]!=((sw>>9)&1):bad.append('C1');counts['C1_misses']+=1
                        else:
                            counts['C2_rows']+=1
                            if not sw&0x400:bad.append('C2')
                        if bad:misses.append(dict(operand=op.strip(),mode=mode,model=got,hardware=want,failed=bad))
                        if op.strip()=='3ffc e79000000c3e46e7':
                            separator.append(dict(bank=bank,operand=op.strip(),mode=mode,hardware=want,model=got))
                assert not hw.readline()
            item=dict(bank=bank,mode=mode,counts=dict(counts),misses=misses,
                sha256=dict(inputs=digest(inputs),raw=digest(raw),binary=digest(binary)))
            with (base/(bank+'_'+mode+'.json')).open('x') as f:json.dump(item,f,indent=2,sort_keys=True)
            records.append(item);print(bank,mode,dict(counts),flush=True)
    result=dict(status='PASS' if not any(r['misses'] for r in records) else 'FAIL',
        counts=dict(sum((Counter(r['counts']) for r in records),Counter())),
        records=records,hardware_executions=0,scope='Saved i7 labels; overlapping historical instruction appearances, not fresh tuples.',
        sha256=dict(source=digest(root/'src/fsincos_skylake.c'),paired=digest(root/'src/general/paired.h'),script=digest(Path(__file__))))
    with (base/'separator.json').open('x') as f:json.dump(separator,f,indent=2,sort_keys=True)
    with report.open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(result['status'],result['counts'],flush=True)
    if result['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
