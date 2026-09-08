"""Authenticate and replay retained FPTAN/F2XM1 captures from both CPU hosts.

This is an offline development check; the research archives are not included
in the library source package and no native instructions are executed here.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cli',type=Path)
    args=parser.parse_args();counts=Counter();sources=[]
    for op,job in [('fptan','fptan/verification-expansion-fptan-v1-xeon'),
                   ('fptan','fptan/verification-expansion-fptan-v1-i7'),
                   ('f2xm1','f2xm1/f0001'),('f2xm1','f2xm1/f0002')]:
        path=ROOT/'research/fsincos-re/tmp/verification-expansion'/job/'hardware.txt.gz'
        receipt=json.loads(path.with_name('COMPLETE.json').read_text())
        raw=gzip.decompress(path.read_bytes());sha=hashlib.sha256(raw).hexdigest()
        assert sha==receipt['hardware_sha256'],str(path)
        rows=[line.split() for line in raw.decode().splitlines()]
        requests=[f'{i} {op} {f[1]} {f[2]} {f[3]} {f[4]}' for i,f in enumerate(rows)]
        run=subprocess.run([str(args.cli.resolve())],input='\n'.join(requests)+'\n',
                           text=True,capture_output=True,check=True)
        answers=run.stdout.splitlines();assert len(answers)==len(rows)
        for index,(f,line) in enumerate(zip(rows,answers)):
            g=line.split();sw=int(f[7],16);flags=sw&63
            assert len(g)==13 and g[:2]==[str(index),'0'],(job,f[0],line)
            assert int(g[11],16)==63 and int(g[10],16)==flags,(job,f[0],'flags',line)
            ranged=op=='fptan' and sw&0x400
            required=0x400 if ranged else 0x600 if op=='fptan' else 0x200
            assert int(g[9],16)&required==required,(job,f[0],'missing metadata',line)
            assert (int(g[8],16)^sw)&required==0,(job,f[0],'C1/C2',line)
            if ranged:assert g[2:4]==['1','0'] and g[12]=='0'
            else:
                assert g[4:6]==f[9:11],(job,f[0],'primary',line)
                if op=='fptan':assert g[6:8]==f[11:13],(job,f[0],'pushed',line)
            counts[op]+=1;counts['flags']+=1
            if not ranged:counts['C1']+=1
            if op=='fptan':counts['C2']+=1
        sources.append(dict(path=str(path.relative_to(ROOT)),raw_sha256=sha,rows=len(rows)))
    print(json.dumps(dict(status='PASS',counts=counts,sources=sources,native_hardware_executed=False),indent=2))


if __name__=='__main__':main()
