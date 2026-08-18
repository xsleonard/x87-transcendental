#!/usr/bin/env python3
# h762: razor-band harvest — every sine-branch row of randv1 within
# 16 even-lsb of the final RN64 boundary (from DI_SPOLY, exact int math).
import subprocess, sys
insn = sys.argv[1]
flag = '--fcos-standalone' if insn=='cos' else '--fsin-standalone'
def pw(s):
    sg, e2, hx = s.split(':')
    return int(sg), int(e2), int(hx,16)
proc = subprocess.Popen(['./model_h235','--batch',flag,'--dump-internals'],
    stdin=open('/root/h491/randv1_inputs.txt'), stdout=subprocess.DEVNULL,
    stderr=subprocess.PIPE, text=True, bufsize=1<<20)
out = open('h762_wall_%s.txt' % insn, 'w')
nrow = nsine = nkeep = 0
red = None
for L in proc.stderr:
    if L.startswith('DI_RED '):
        d = dict(x.split('=',1) for x in L.split()[1:])
        red = (d['i0'], d['rsn'], d['mag']); nrow += 1
    elif L.startswith('DI_SPOLY '):
        d = dict(x.split('=',1) for x in L.split()[1:])
        nsine += 1
        so, eo, ho = pw(d['odd']); se_, ee, he = pw(d['even'])
        # exact sum in units of 2^min(eo,ee); odd/even opposite signs
        sh = eo - ee
        if sh >= 0: no, ne, base = ho << sh, he, ee
        else: no, ne, base = ho, he << -sh, eo
        N = (no if not so else -no) + (ne if not se_ else -ne)
        aN = abs(N)
        top = aN.bit_length()-1
        cR = top - 64            # round-bit position within aN
        if cR < 0: continue
        half = 1 << cR
        rem = aN & ((half<<1)-1)
        m = half - rem           # + = below boundary, 0 = tie, - = above
        if -16 <= m <= 16:
            nkeep += 1
            out.write('%s %s %s %s %s %s %d %d %d\n' % (
                red[0], red[1], red[2], d['odd'], d['even'], d['poly'],
                m, eo-ee, top))
out.close()
proc.wait()
print(insn, 'rows(RED):', nrow, 'sine:', nsine, 'kept:', nkeep)
