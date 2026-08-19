#!/usr/bin/env python3
# h768: reduction-frame contrast — 148 votes vs razor-band reduced
# negatives on operand/N/quotient-tail features.
import pickle, collections
M66 = (3<<64) | 0x243F6A8885A308D3
TOPI = (0xA2F9836E4E441529<<64) | 0xFC2757D1F534DDC0
def compat_N(sig, e):
    dividend = sig << (e+2)
    q, rem = divmod(dividend, M66)
    if (rem<<1) > M66: q += 1
    return q
def feats(se, sig):
    ce = int(se,16); e = (ce & 0x7fff) - 16383
    s = int(sig,16)
    N = compat_N(s, e)
    P = s * TOPI
    sh = 191 - e
    qf = P & ((1<<sh)-1)          # discarded quotient fraction (s bits)
    top8 = qf >> (sh-8)
    # distance of quotient to its rounding boundary (near-tie N)
    dh = abs(qf - (1<<(sh-1)))
    dh_l2 = dh.bit_length()
    def tz(x): return (x&-x).bit_length()-1 if x else 99
    return dict(e=e, sgn=ce>>15, stz=min(tz(s),13),
        N1=N&1, N2=(N>>1)&1, N4=(N>>2)&1, N8=(N>>3)&1, Nmod16=N%16,
        Ntz=min(tz(N),9), Npop=bin(N).count('1')&1,
        qtop8=top8, qlow8=P&0xff, qmid8=(P>>64)&0xff,
        qg=(qf>>(sh-1))&1, dhl2=sh-dh_l2,   # bigger = closer to N-tie
        )
votes = []
vrec = pickle.load(open('h761_state.pkl','rb'))
seen = set()
for r in vrec:
    k = (r['cls'],r['se'],r['sig'],r['insn'])
    if k in seen or r['cls']!='POS': continue
    seen.add(k)
    if ((int(r['se'],16)&0x7fff) - 16383) >= -1:   # reduced route only
        votes.append((r['se'], r['sig'], r['insn']))
print('reduced votes:', len(votes))
negs = []
for fn, insn in (('h767_ck1_cos.txt','cos'),('h767_ck1_sin.txt','sin'),
                 ('h767_rvl_cos.txt','cos'),('h767_rvl_sin.txt','sin')):
    for L in open(fn):
        t = L.split()
        m = int(t[8])
        if 0 <= m <= 5:
            negs.append((t[0], t[1], insn, m))
vset = set(votes)
negs = [n for n in negs if (n[0],n[1],n[2]) not in vset]
print('reduced razor negatives (m 0..5):', len(negs))
VF = [feats(se,sg) for se,sg,_ in votes]
NF = [feats(se,sg) for se,sg,_,_ in negs]
import statistics
KEYS = ['e','sgn','stz','N1','N2','N4','N8','Ntz','Npop','qg','dhl2']
print('%-6s %9s %9s' % ('feat','VOTEmean','NEGmean'))
for k in KEYS:
    print('%-6s %9.3f %9.3f' % (k, statistics.mean(x[k] for x in VF),
        statistics.mean(x[k] for x in NF)))
for k in ('qtop8','qlow8','qmid8','Nmod16'):
    vb = [0]*8; nb = [0]*8
    for x in VF:
        for b in range(8):
            if (x[k]>>b)&1: vb[b]+=1
    for x in NF:
        for b in range(8):
            if (x[k]>>b)&1: nb[b]+=1
    print(k, 'bit P(1) vote vs neg:',
          ' '.join('%d:%.2f/%.2f' % (b, vb[b]/len(VF), nb[b]/len(NF)) for b in range(8)))
pickle.dump({'votes':votes,'negs':negs,'VF':VF,'NF':NF}, open('h768_out.pkl','wb'))
print('DONE')
