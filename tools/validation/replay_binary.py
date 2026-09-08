"""Authenticate and replay the full retained FPATAN/logarithm hardware corpus.

Offline only. Each pack must match both its completion receipt and the prior
acceptance inventory. Numerical bits, C1 and all arithmetic flags are compared;
capture controls and stack-pop transitions are independently checked as well.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cli', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    atan = json.loads((ROOT/'research/fsincos-re/tmp/fpatan-re/d0027-main-full-replay.json').read_text())
    log = json.loads((ROOT/'research/fsincos-re/paper/evidence/logarithm-replay.json').read_text())
    jobs = [('fpatan-re', job, data['hardware_sha256']) for job, data in atan['jobs'].items()]
    jobs += [('fyl2x-re', data['job'], data['hardware_sha256']) for data in log['jobs']]
    counts, sources = Counter(), []
    for family, job, pinned in jobs:
        directory = ROOT/'research/fsincos-re/tmp'/family/job
        receipt = json.loads((directory/'COMPLETE.json').read_text())
        path = directory/'hardware.txt'
        if path.exists(): raw = path.read_bytes()
        else:
            path = directory/'hardware.txt.gz'
            compressed = path.read_bytes()
            assert hashlib.sha256(compressed).hexdigest() == receipt['hardware_gzip_sha256'], job
            raw = gzip.decompress(compressed)
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == receipt['hardware_sha256'] == pinned, job
        lines = raw.decode().splitlines()
        assert len(lines) == receipt['rows'], job
        for start in range(0, len(lines), 32768):
            saved, requests = [], []
            for line in lines[start:start+32768]:
                f = line.split()
                if family == 'fpatan-re': f.insert(1, 'fpatan')
                assert len(f) == 13, (job,line)
                ident, op, rc, pc, ys, ym, xs, xm = f[:8]
                key = f'{op}-v1-masked-clear-depth2:{rc}:{pc}:{ys}:{ym}:{xs}:{xm}'
                assert hashlib.sha256(key.encode()).hexdigest()[:40] == ident, (job,ident)
                cw, before, after = (int(v,16) for v in f[8:11])
                expected_cw = 0x7f | {24:0,53:0x200,64:0x300}[int(pc)] | (('rn','rd','ru','rz').index(rc)<<10)
                assert cw == expected_cw and before & 63 == 0, (job,ident,'control/preload')
                assert (before>>11)&7 == 6 and (after>>11)&7 == 7, (job,ident,'pop')
                requests.append(f'{ident} {op} {rc} {pc} 3f {xs} {xm} {ys} {ym}')
                saved.append((f,after))
            result = subprocess.run([str(args.cli.resolve())],input='\n'.join(requests)+'\n',
                                    text=True,capture_output=True,check=True)
            answers = result.stdout.splitlines()
            assert len(answers) == len(saved), job
            for (f,sw), line in zip(saved,answers):
                g = line.split()
                assert len(g) == 14 and g[:4] == [f[0],'0','0','1'], (job,f[0],line)
                assert g[4:6] == f[11:13], (job,f[0],'value',line,f)
                assert int(g[8],16) == sw & 0x200 and int(g[9],16) == 0x200, (job,f[0],'C1',line)
                assert int(g[10],16) == sw & 63 and int(g[11],16) == 63, (job,f[0],'flags',line)
                assert g[6:8] == ['0000','0000000000000000'] and g[12:] == ['3','00'], (job,f[0],'metadata',line)
                counts[f[1]] += 1
        sources.append(dict(path=str(path.relative_to(ROOT)),raw_sha256=digest,rows=len(lines)))
        print(f'{job}: {len(lines)} passed', flush=True)
    report = dict(status='PASS',comparisons=sum(counts.values()),counts=counts,sources=sources,
                  native_hardware_executed=False)
    text = json.dumps(report,indent=2,sort_keys=True)+'\n'
    if args.output: args.output.write_text(text)
    print(text,end='')


if __name__ == '__main__': main()
