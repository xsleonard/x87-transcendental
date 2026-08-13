#!/usr/bin/env python3
"""h619c: are the miss rows SEPARABLE from in-cell correct rows
by any unused coordinate?

Pooled over the dense h619 captures + h616 in-cell rows:
label each row correct/miss under the CURRENT model; within
each (key, xd12, mf16) cell holding >= 3 misses, compare
miss vs correct distributions of:
  theta, st (raw), st relative to zone threshold, tau fine
  position (tau*256 mod 1), mf fine position (mf*512 mod 1),
  and the selector residual frac(x) (distance of x to the
  round boundary .5).
Report per-variable AUC-style separation (rank statistic) and
the fraction of misses isolatable by a per-cell single
threshold on each variable at zero false positives.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h598_jframe import jinterval
from h609_ref_predictor import load_model, predict, V5_KEYS

FITS = CBEST = None


def initp():
    global FITS, CBEST
    FITS, CBEST = load_model()


def prep(args):
    rec, hw = args
    key = tuple(rec["key"])
    EU = int(rec["EU"])
    Vlow = int(rec["Vlow"])
    kf = rec["kf"]
    rfv = int(rec["rfv"])
    ce = rec["ce"]
    ivs = []
    for z in (-2, -1, 0, 1, 2):
        refs = [final_cosine_result(-(EU + z), ce, md)
                for md in ROUNDING_MODES]
        if refs == hw:
            lo, hi = jinterval(Vlow, kf, rfv, z)
            if lo <= hi:
                ivs.append((lo, hi))
    if not ivs:
        return None
    tau, mf, st, xd12 = (rec["tau"], rec["mf"], rec["st"],
                         rec["xd12"])
    pr = predict(FITS, CBEST, key, xd12, mf, st, tau, Vlow,
                 kf, rfv)
    if pr is None:
        return None
    _, req2p, _ = pr
    lo3, hi3 = jinterval(Vlow, kf, rfv, req2p)
    correct = any(not (h < lo3 or hi3 < l) for l, h in ivs)
    if key in V5_KEYS:
        zid = (key, xd12, min(15, int(mf * 16)))
    else:
        zid = (key, xd12)
    q, a, b = FITS[zid]
    c = CBEST.get((zid, st), 0)
    x = q * tau + a * mf + b + c
    fx = abs(x - round(x))
    return (key, xd12, min(15, int(mf * 16)),
            int(correct), rec["theta"], st,
            (tau * 256) % 1.0, (mf * 512) % 1.0, fx)


def main():
    initp()
    rows = []
    recs = json.load(open("h619_rows.json"))
    st_f = {md: open(f"h619_{md}_status.txt").read()
            .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(recs):
        hw = []
        ok = True
        for md in ROUNDING_MODES:
            t = st_f[md][i].split()
            if t[0] != "OK":
                ok = False
                break
            hw.append(int(t[2], 16))
        if ok:
            rows.append((rec, hw))
    print(f"rows: {len(rows)}", flush=True)
    with Pool(14, initializer=initp) as pool:
        ps = pool.map(prep, rows, chunksize=500)
    cells = defaultdict(lambda: ([], []))
    for p in ps:
        if p is None:
            continue
        key, xd12, mf16, correct, theta, st, tfin, mfin, fx = p
        cells[(key, xd12, mf16)][correct].append(
            (theta, st, tfin, mfin, fx))
    VN = ("theta", "st", "tau_fine", "mf_fine", "frac_x")
    sep = defaultdict(lambda: [0, 0])
    auc = defaultdict(list)
    nm_tot = 0
    for cell, (miss, corr) in cells.items():
        if len(miss) < 3 or len(corr) < 20:
            continue
        nm_tot += len(miss)
        for vi, name in enumerate(VN):
            mv = sorted(r[vi] for r in miss)
            cv = sorted(r[vi] for r in corr)
            # rank AUC
            import bisect
            s = sum(bisect.bisect_left(cv, v) for v in mv)
            a = s / (len(mv) * len(cv))
            auc[name].append(max(a, 1 - a))
            # zero-FP isolation: misses strictly beyond all
            # correct values on either side
            lo_iso = sum(1 for v in mv if v < cv[0])
            hi_iso = sum(1 for v in mv if v > cv[-1])
            sep[name][0] += max(lo_iso, hi_iso)
            sep[name][1] += len(mv)
    print(f"cells with >=3 misses: "
          f"{sum(1 for c, (m, cr) in cells.items() if len(m) >= 3 and len(cr) >= 20)}"
          f", misses covered: {nm_tot}")
    for name in VN:
        aa = auc[name]
        mean_auc = sum(aa) / max(len(aa), 1)
        iso, tot = sep[name]
        print(f"  {name:9s}: mean AUC {mean_auc:.3f}  zero-FP "
              f"isolation {iso}/{tot}")


if __name__ == "__main__":
    main()
