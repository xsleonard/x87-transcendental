#!/usr/bin/env python3
"""SYNTHETIC protocol fixture only. No FPATAN or numerical computation."""
import os
import sys
if sys.argv[1:]==['--identity']:
    print('CPUID1 00050654 0 0 0');raise SystemExit(0)
count=0
for line in sys.stdin:
    t=line.split();cw=0x7f|{24:0,53:0x200,64:0x300}[int(t[2])]|(('rn','rd','ru','rz').index(t[1])<<10)
    print(line.rstrip()+f' {cw:04x} 3000 3820 3ffe c90fdaa22168c235');count+=1
print(f'COMPLETE {count}',file=sys.stderr)
raise SystemExit(7 if os.environ.get('FPATAN_TEST_FAIL') else 0)
