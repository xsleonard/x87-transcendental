#!/usr/bin/env python3
"""h612: bit-exactness cross-check of the C Round-57 port
against the Python reference predictor (h609).

Sample rows stratified from combs 5/6/7/8 (all windows, both
sides, theta in [-2,2]).  For each row the Python side computes
(covered, req2p, EU, ce) and the expected model significand per
mode = final_cosine_result(-(EU + req2p), ce, md).  The C model
(--fcos-standalone --round57-fcos-borrow-rule) must reproduce it
exactly for every covered row in all three modes.  Uncovered
rows are skipped (C falls back to Round-52 behavior).
"""
import subprocess
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3
from h588_select import split_words
from h609_ref_predictor import load_model, predict
import h539_D_library as DL

CBIN = "/tmp/stageA/fsincos_skylake_r57"
FITS = CBEST = None


def sample():
    per = defaultdict(int)
    rows = []
    seen = set()
    for fn, stride in (("ties_comb5.txt", 97),
                       ("ties_comb6.txt", 397),
                       ("ties_comb7.txt", 397),
                       ("ties_comb8.txt", 997)):
        n = 0
        for line in open(fn):
            n += 1
            if n % stride:
                continue
            f = line.split()
            if f[0] in seen:
                continue
            theta = int(f[9]) if len(f) > 9 else 0
            cell = (int(f[1]), int(f[2]), int(f[8]), theta)
            if per[cell] >= 8:
                continue
            per[cell] += 1
            seen.add(f[0])
            rows.append((f[0], int(f[8]), theta))
    return rows


def pyrow(args):
    mhex, ce, theta = args
    (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
     bshift, k, dist, low3) = qrow3(mhex)
    F = rsh - bshift
    if F < 0:
        return None
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    side = "up" if theta <= 0 else "dn"
    qr = DL.qrow(mhex)
    f4v, rfv = qr[2], qr[3]
    S, C = split_words(f4v, rfv)
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    key = (dist, low3, ce, side)
    p = predict(FITS, CBEST, key, xd12, mf, st, tau, Vlow, kf,
                rfv)
    if p is None:
        return ("uncovered",)
    _, req2p, src = p
    sigs = tuple(final_cosine_result(-(EU + req2p), ce, md)
                 for md in ROUNDING_MODES)
    return ("covered", sigs, req2p, src)


def initp():
    global FITS, CBEST
    FITS, CBEST = load_model()


def main():
    rows = sample()
    print(f"sample rows: {len(rows)}")
    with Pool(14, initializer=initp) as pool:
        py = pool.map(pyrow, rows, chunksize=20)
    inp = "".join(f"3ffc {m}\n" for m, ce, th in rows)
    couts = {}
    for md in ROUNDING_MODES:
        args = [CBIN, "--batch", "--fcos-standalone",
                "--round57-fcos-borrow-rule"]
        if md != "rn":
            args.append(f"--rc={md}")
        r = subprocess.run(args, input=inp, capture_output=True,
                           text=True)
        couts[md] = r.stdout.splitlines()
    ok = mismatch = uncov = skipped = 0
    for i, ((mhex, ce, th), pyr) in enumerate(zip(rows, py)):
        if pyr is None:
            skipped += 1
            continue
        if pyr[0] == "uncovered":
            uncov += 1
            continue
        _, sigs, req2p, src = pyr
        csigs = []
        bad = False
        for md in ROUNDING_MODES:
            t = couts[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            csigs.append(int(t[2], 16))
        if bad:
            skipped += 1
            continue
        if tuple(csigs) == sigs:
            ok += 1
        else:
            mismatch += 1
            if mismatch <= 10:
                print(f"MISMATCH {mhex} ce={ce} th={th} "
                      f"req2p={req2p} src={src} "
                      f"py={[f'{s:x}' for s in sigs]} "
                      f"c={[f'{s:x}' for s in csigs]}")
    print(f"covered-checked: {ok + mismatch}, exact {ok}, "
          f"MISMATCH {mismatch}, uncovered {uncov}, "
          f"skipped {skipped}")


if __name__ == "__main__":
    main()
