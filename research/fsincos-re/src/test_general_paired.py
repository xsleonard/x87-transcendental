#!/usr/bin/env python3
"""Small saved-hardware regression wall for the general paired entry; no FPU."""
import subprocess
import sys
from pathlib import Path

# These are test expectations, never an operand ledger in the algorithm.
# H1709 comb4/comb7 raw-label frontier and H1717 comb10 separator replay.
CASES=(
    ('rd','3ffc c060000000d78237','3ffc bf3ed1ea9755cbd7 3ffe fb7ee49efb569156',0),
    ('ru','3ffc c060000000d78237','3ffc bf3ed1ea9755cbd8 3ffe fb7ee49efb569157',1),
    ('rd','3ffc b400000004ea29f8','3ffc b3130fc9731657e8 3ffe fc0e1abb7dd28ccd',0),
    ('rn','3ffc e79000000c3e46e7','3ffc e5980e1fae54d858 3ffe f97b7761040745d2',0),
    ('rd','3ffc e79000000c3e46e7','3ffc e5980e1fae54d857 3ffe f97b7761040745d2',0),
    ('ru','3ffc e79000000c3e46e7','3ffc e5980e1fae54d858 3ffe f97b7761040745d3',1),
)


def main():
    binary=Path(sys.argv[1] if len(sys.argv)>1 else './fsincos_skylake').resolve()
    for mode,op,want,c1 in CASES:
        p=subprocess.run([str(binary),'--batch','--rc='+mode,'--general-trace'],
            input=op+'\n',text=True,capture_output=True,check=True)
        assert p.stdout=='OK '+want+'\n',(mode,op,p.stdout,want)
        trace=p.stderr.strip().split();assert trace[:4]==['HPAIR','0','polynomial','1'] and int(trace[5])==c1
    print(f'PAIRED saved-hardware regressions: {len(CASES)} output/C1 cases pass')


if __name__=='__main__':main()
