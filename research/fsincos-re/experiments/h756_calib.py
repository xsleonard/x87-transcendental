#!/usr/bin/env python3
# h756: verify h755 replica calibration — chain(mag, SHIP) must equal
# the shipped poly pd for ALL cached rows (the missing assert).
import pickle, sys
sys.path.insert(0, '.')
from fractions import Fraction
import importlib.util
# import h755's functions without running its sweep: exec up to CACHE load
src = open('h755_peredge.py').read()
head = src.split('CACHE = ')[0]
g = {}
exec(head, g)
chain, SHIP = g['chain'], g['SHIP']
ROWS = pickle.load(open('h755_rows.pkl','rb'))
bad = 0
from collections import Counter
cnt = Counter(r[0] for r in ROWS)
for cls, mag, pd, lsb in ROWS:
    pl = chain(mag, SHIP)
    if pl != pd:
        bad += 1
        if bad <= 5: print('MISCAL', cls, float(mag), float(pd), float(pl))
print('rows:', len(ROWS), dict(cnt), 'miscalibrated:', bad)
