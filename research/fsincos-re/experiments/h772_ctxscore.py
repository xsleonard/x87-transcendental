#!/usr/bin/env python3
# h772: score context-test captures — does each vote still fire?
import collections
def norm(l):
    t = l.split()
    return ('C2',) if t[0]=='C2' else tuple(t[1:3])
orig = collections.defaultdict(set)   # (se,sig,insn) -> set of modes that fired originally
for fn in ('h753_allvotes.txt','h759_miner2_votes.txt'):
    for L in open(fn):
        t = L.split()
        orig[(t[3],t[4],t[1])].add(t[2])
res = {}
for insn in ('cos','sin'):
    for ctx in ('plain','mix'):
        inp = open('ctx_%s_%s.txt' % (ctx,insn)).read().splitlines()
        for mode in ('rn','rd','ru'):
            hw = open('ctxhw_%s_%s_%s.txt' % (ctx,insn,mode)).read().splitlines()
            mo = open('ctxmo_%s_%s_%s.txt' % (ctx,insn,mode)).read().splitlines()
            assert len(hw)==len(mo)==len(inp), (ctx,insn,mode,len(hw),len(mo),len(inp))
            for i,(a,b) in enumerate(zip(hw,mo)):
                se,sg = inp[i].split()
                k = (se,sg,insn)
                if k in orig:
                    res.setdefault(k, {}).setdefault(ctx, set())
                    if norm(a)!=norm(b): res[k][ctx].add(mode)
kept = lost = gained = 0
tot = 0
for k, om in orig.items():
    if k not in res: continue
    tot += 1
    for ctx in ('plain','mix'):
        got = res[k].get(ctx,set())
        if got == om: kept += 1
        elif not got: lost += 1
        else: gained += 1
print('vote ops tested:', tot)
print('context results (per op x context): identical-fire %d  no-fire %d  changed %d' % (kept, lost, gained))
diffs = [(k,om,res[k]) for k,om in orig.items() if k in res and (res[k].get('plain')!=om or res[k].get('mix')!=om)]
print('ops with any context difference:', len(diffs))
for k,om,r in diffs[:10]:
    print('  ', k, 'orig:', sorted(om), 'plain:', sorted(r.get('plain',[])), 'mix:', sorted(r.get('mix',[])))
