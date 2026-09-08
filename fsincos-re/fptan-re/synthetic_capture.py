#!/usr/bin/env python3
"""Synthetic protocol fixture. Never executes an x87 instruction."""
import os
import sys


def main():
    if sys.argv[1:] == ['--identity']:
        print('CPUID1 00050654 0 0 0')
        return 0
    count = 0
    for line in sys.stdin:
        ident, rc, pc, se, sig = line.split()
        control = 0x7f | {24: 0, 53: 0x200, 64: 0x300}[int(pc)] | ('rn', 'rd', 'ru', 'rz').index(rc) << 10
        c2 = (int(se, 16) & 32767) >= 16383 + 63
        after, end = (0x3c00, 0x400) if c2 else (0x3020, 0x20)
        pushed = '0000 0000000000000000' if c2 else '3fff 8000000000000000'
        print(f'{line.strip()} {control:04x} 3800 {after:04x} {end:04x} {se} {sig} {pushed}')
        count += 1
    print(f'COMPLETE {count}', file=sys.stderr)
    return 7 if os.environ.get('FPTAN_SYNTHETIC_FAIL') else 0


if __name__ == '__main__':
    raise SystemExit(main())
