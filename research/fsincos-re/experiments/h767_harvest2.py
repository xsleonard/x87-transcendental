#!/usr/bin/env python3
# h767: razor-band harvest v2 — tracks DI_IN so every kept row carries
# its operand.  Usage: h767_harvest2.py INPUTFILE INSN OUTFILE
import subprocess, sys
inf, insn, outf = sys.argv[1], sys.argv[2], sys.argv[3]
flag = '--fcos-standalone' if insn=='cos' else '--fsin-standalone'
def pw(s):
    sg,e2,hx = s.split(':'); return int(sg), int(e2), int(hx,16)
proc = subprocess.Popen(['./model_h235','--batch',flag,'--dump-internals'],
    stdin=open(inf), stdout=subprocess.DEVNULL,
    stderr=subprocess.PIPE, text=True, bufsize=1<<20)
out = open(outf,'w')
cur = red = None
nin = nsine = nkeep = 0
for L in proc.stderr:
    if L.startswith('DI_IN '):
        cur = L.split()[1:3]; nin += 1
    elif L.startswith('DI_RED '):
        d = dict(x.split('=',1) for x in L.split()[1:])
        red = (d['i0'], d['rsn'], d['mag'])
    elif L.startswith('DI_SPOLY '):
        d = dict(x.split('=',1) for x in L.split()[1:])
        nsine += 1
        so,eo,ho = pw(d['odd']); se_,ee,he = pw(d['even'])
        sh = eo - ee
        if sh >= 0: no, ne = ho << sh, he
        else: no, ne = ho, he << -sh
        N = (no if not so else -no) + (ne if not se_ else -ne)
        aN = abs(N)
        cR = aN.bit_length()-1-64
        if cR < 0: continue
        half = 1 << cR
        m = half - (aN & ((half<<1)-1))
        if -16 <= m <= 16:
            nkeep += 1
            out.write('%s %s %s %s %s %s %s %s %d %d\n' % (
                cur[0], cur[1], red[0], red[1], red[2], d['odd'], d['even'],
                d['poly'], m, eo-ee))
out.close(); proc.wait()
print(outf, 'in:', nin, 'sine:', nsine, 'kept:', nkeep, flush=True)
