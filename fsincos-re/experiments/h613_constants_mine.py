#!/usr/bin/env python3
"""h613: MINE THE FITTED MODEL CONSTANTS AS DATA.

The merged Round-57 model (1,434 zones (q,a,b), 3,664 nonzero
c(zone,st) offsets) is the compressed physics of the gate.
Questions:
  1. q census per stratum-side (grid {2,2.5,3,3.5,4}; h559 said
     q ~ 3 wins broadly — where does it not?).
  2. b(xd12) per stratum-side (v3 zones): affine? slope snapped
     to simple rationals x/24?  (h574: -0.25/-0.125 ladder units
     per twelfth.)
  3. a census: distribution per stratum-side; sign structure.
  4. c(zone, st): per zone, is c monotone in st?  Fit the best
     per-zone STEP c = c0 + [st >= t] and the best per-zone
     LINEAR c = round(g*(st - s0)); report explained fraction.
     Then GLOBAL forms across zones.
  5. v5 zones: b(mf16) curvature per (key, xd12) — second
     difference census (is it quadratic? sign-constant?).
"""
from collections import defaultdict
from fractions import Fraction
from h609_ref_predictor import load_model

fits, cbest = load_model()

# ---- 1. q census ----
qc = defaultdict(lambda: defaultdict(int))
for zid, (q, a, b) in fits.items():
    key = zid[0]
    if q == 0.0 and a == 0.0:
        qc[key]["const"] += 1
    else:
        qc[key][q] += 1
print("=== q census per stratum-side (const = const-j zone) ===")
tot = defaultdict(int)
for key in sorted(qc, key=str):
    row = qc[key]
    for k, v in row.items():
        tot[k] += v
print("  GLOBAL:", dict(sorted(tot.items(), key=str)))
by_q = defaultdict(int)
for key in sorted(qc, key=str):
    best = max(qc[key], key=qc[key].get)
    by_q[best] += 1
print("  dominant q per stratum-side:", dict(sorted(by_q.items(),
                                                    key=str)))

# ---- 2. b(xd12) for v3 zones ----
print("\n=== b(xd12) affinity per stratum-side (v3, q,a fixed"
      " within) ===")
v3 = defaultdict(dict)
for zid, (q, a, b) in fits.items():
    if len(zid) == 2:
        v3[zid[0]][zid[1]] = (q, a, b)
nlin = ncand = 0
slope_census = defaultdict(int)
for key in sorted(v3, key=str):
    zs = v3[key]
    xs = sorted(zs)
    # only compare consecutive zones with SAME (q, a)
    diffs = []
    for x1, x2 in zip(xs, xs[1:]):
        if x2 == x1 + 1 and zs[x1][:2] == zs[x2][:2] and \
                not (zs[x1][0] == 0 and zs[x1][1] == 0):
            diffs.append(zs[x2][2] - zs[x1][2])
    if len(diffs) >= 4:
        ncand += 1
        med = sorted(diffs)[len(diffs) // 2]
        # snap to nearest x/24
        fr = Fraction(round(med * 24), 24)
        dev = max(abs(d - med) for d in diffs)
        ok = dev < 0.05
        nlin += ok
        if ok:
            slope_census[str(fr)] += 1
        print(f"  {key}: n_pairs={len(diffs)} med_db={med:+.4f} "
              f"snap={fr} maxdev={dev:.4f} "
              f"{'LINEAR' if ok else 'curved'}")
print(f"  affine-in-xd12: {nlin}/{ncand}; slope census "
      f"{dict(slope_census)}")

# ---- 3. a census ----
print("\n=== a census ===")
avals = defaultdict(int)
for zid, (q, a, b) in fits.items():
    if not (q == 0.0 and a == 0.0):
        avals[a] += 1
top = sorted(avals.items(), key=lambda kv: -kv[1])[:12]
print("  top a values:", [(f"{a:g}", n) for a, n in top])

# ---- 4. c(zone, st) structure ----
print("\n=== c(zone, st) structure ===")
byzone = defaultdict(dict)
for (zid, st), c in cbest.items():
    byzone[zid][st] = c
nmono = nstep = nlin2 = nz = 0
step_thr = defaultdict(int)
for zid, sts in byzone.items():
    if len(sts) < 6:
        continue
    nz += 1
    ks = sorted(sts)
    vs = [sts[k] for k in ks]
    inc = all(b >= a for a, b in zip(vs, vs[1:]))
    dec = all(b <= a for a, b in zip(vs, vs[1:]))
    if inc or dec:
        nmono += 1
    # best step: c = lo for st < t, hi for st >= t
    best_err = None
    for t in range(0, 65):
        lov = [v for k, v in sts.items() if k < t]
        hiv = [v for k, v in sts.items() if k >= t]
        def maj(vv):
            return max(set(vv), key=vv.count) if vv else 0
        lo, hi = maj(lov), maj(hiv)
        err = sum(1 for k, v in sts.items()
                  if v != (lo if k < t else hi))
        if best_err is None or err < best_err[0]:
            best_err = (err, t, lo, hi)
    if best_err[0] == 0:
        nstep += 1
        step_thr[best_err[1]] += 1
print(f"  zones with >=6 states: {nz}; monotone-in-st {nmono}; "
      f"exact 2-level step {nstep}")
print(f"  step thresholds: "
      f"{dict(sorted(step_thr.items())) if step_thr else {}}")
c_census = defaultdict(int)
for (zid, st), c in cbest.items():
    c_census[c] += 1
print("  c value census:", dict(sorted(c_census.items())))

# ---- 5. v5 b(mf16) curvature ----
print("\n=== v5 b(mf16) per (key, xd12): second differences ===")
v5 = defaultdict(dict)
for zid, (q, a, b) in fits.items():
    if len(zid) == 3:
        v5[(zid[0], zid[1])][zid[2]] = (q, a, b)
n2 = nquad = 0
for kk in sorted(v5, key=str):
    zs = v5[kk]
    xs = sorted(zs)
    runs = []
    for x in xs:
        if x - 1 in zs and x + 1 in zs and \
                zs[x - 1][:2] == zs[x][:2] == zs[x + 1][:2] and \
                not (zs[x][0] == 0 and zs[x][1] == 0):
            d2 = zs[x + 1][2] - 2 * zs[x][2] + zs[x - 1][2]
            runs.append(d2)
    if len(runs) >= 3:
        n2 += 1
        sgn = set(1 if d > 0.02 else (-1 if d < -0.02 else 0)
                  for d in runs)
        if sgn <= {0, 1} or sgn <= {0, -1}:
            nquad += 1
print(f"  (key,xd12) with mf-runs: {n2}; curvature "
      f"sign-consistent: {nquad}")
