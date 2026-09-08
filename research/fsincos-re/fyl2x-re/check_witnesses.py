"""Replay bundled public hardware witnesses through C, API and Python.

Only saved observations are read. No native x87 or network is executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from model import predict_full
from protocol import validate_output

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,default=HERE/'build');a=p.parse_args()
    manifest=json.loads((HERE/'witnesses.json').read_text())
    raw=(HERE/'witnesses.txt').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==manifest['sha256']
    rows=raw.decode().splitlines();inputs=[' '.join(s.split()[:8]) for s in rows]
    assert len(rows)==manifest['rows']
    expected=[]
    for line,source in zip(rows,inputs):
        h=validate_output(line,source)
        expected.append((h['se'],h['sig'],h['C1'],h['sw']&63,h['before']&63))
    for name in ('x87-log','log_batch'):
        result=subprocess.run([str((a.build/name).resolve())],input='\n'.join(inputs)+'\n',text=True,capture_output=True,check=True)
        lines=result.stdout.splitlines();assert len(lines)==len(rows)
        for source,line,want in zip(inputs,lines,expected):
            t=line.split();assert t[0]==source.split()[0]
            got=int(t[1],16),int(t[2],16),int(t[3]),int(t[4],16),int(t[5],16)
            assert got==want,(name,source,got,want)
    for source,want in zip(inputs,expected):
        assert (*predict_full(source),0)==want,source
    n=1<<65;s=0x95f619980c4336f7
    assert 2*(n-s)**2>=n*n and 2*(n-s-1)**2<n*n
    print(f'PASS {len(rows)} saved logarithm witnesses: C CLI, C API, independent rational model; exact domain-bound proof')


if __name__=='__main__':main()
