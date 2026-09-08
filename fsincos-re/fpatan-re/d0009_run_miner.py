"""Preserve software mining output/receipts with exclusive creation."""
import hashlib
import json
from pathlib import Path
import subprocess
from prepare import save

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'tmp/fpatan-re'


def main():
    binary=Path('/private/tmp/fpatan-d9-mine');count=4194304
    sources={p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in
             ('d0009_separator_mine.c','d0008_schedule_audit.c','fpatan_candidate.c')}
    save(BASE/'d0009-miner-start.json',dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
         source_pins=sources,software_pairs=count,hardware_executed=False))
    with (BASE/'d0009-separators.txt').open('xb') as out:
        child=subprocess.Popen([str(binary),str(count)],stdout=out,stderr=subprocess.PIPE,text=True)
        log=[]
        for line in child.stderr:log.append(line);print(line,end='',flush=True)
        status=child.wait()
    save(BASE/'d0009-miner-complete.json',dict(returncode=status,progress=log,hardware_executed=False,
         output_sha256=hashlib.sha256((BASE/'d0009-separators.txt').read_bytes()).hexdigest()))
    assert status==0


if __name__=='__main__':main()
