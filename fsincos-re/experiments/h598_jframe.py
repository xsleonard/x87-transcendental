#!/usr/bin/env python3
"""h598: THE J-FRAME ON CLEAN LABELS — attack on the four
state-flat strata ((9,2)up, (9,5)up, (9,6)dn, (9,7)dn @-72).

Ladder (h536/h546/h548): hardware = EU + req2 with
  req2_pred(j) = floor((4*Vlow - j*rfv) / 2^(kf+2)),
  j integer in [-16, 16]; per-row feasible interval
  J = [jlo, jhi] from the clean req2 label.
Selector (h553/h558/h559): j = round(q*tau + a*mf + b) fit per
(stratum, XD12 zone); q, a on a grid, b by exact interval
stabbing on the train half.  Variants:
  J0:  per-zone (q, a, b)
  J1:  J0 + per-(zone, SUM6-state) integer offset c in [-3,3]
Report per stratum: feasibility, base, J0, J1 (held-out), and
the h596b margin-model number for comparison.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h588_select import split_words

TARGETS = {((9, 2, -72), "up"), ((9, 5, -72), "up"),
           ((9, 6, -72), "dn"), ((9, 7, -72), "dn")}
QGRID = [2.0, 2.5, 3.0, 3.5, 4.0]
AGRID = [x * 2.5 for x in range(-12, 13)]
JMAX = 16


def _ws(args):
    f4v, rfv = args
    S, C = split_words(f4v, rfv)
    return S + C


def jinterval(Vlow, kf, rfv, req2):
    # 4*Vlow - j*rfv in [req2*2^(kf+2), (req2+1)*2^(kf+2))
    hi_num = 4 * Vlow - req2 * (1 << (kf + 2))
    lo_num = 4 * Vlow - (req2 + 1) * (1 << (kf + 2))
    # j <= hi_num/rfv ; j > lo_num/rfv
    jhi = hi_num // rfv
    jlo = -((-lo_num) // rfv) if lo_num >= 0 else \
        (lo_num // rfv) + 1
    jlo = max(jlo, -JMAX)
    jhi = min(jhi, JMAX)
    return jlo, jhi


ZROWS = None


def init_z(z):
    global ZROWS
    ZROWS = z


def fit_zone(args):
    zone_id, = args if isinstance(args, tuple) else (args,)
    rows = ZROWS[zone_id]
    best = (-1, None)
    for q in QGRID:
        for a in AGRID:
            # b intervals: [jlo-.5-x, jhi+.5-x) with
            # x = q*tau + a*mf
            ev = []
            for (tau, mf, jlo, jhi, st) in rows:
                if jlo > jhi:
                    continue
                x = q * tau + a * mf
                ev.append((jlo - 0.5 - x, 1))
                ev.append((jhi + 0.5 - x, -1))
            if not ev:
                continue
            ev.sort()
            cur = 0
            bestc = -1
            bestb = 0.0
            for pos, d in ev:
                cur += d
                if cur > bestc:
                    bestc = cur
                    bestb = pos + 1e-9
            if bestc > best[0]:
                best = (bestc, (q, a, bestb))
    return zone_id, best[1]


def main():
    rows_by = defaultdict(list)
    raw = []
    for line in open("h596_hard.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in TARGETS:
            continue
        raw.append((f[0], key, int(f[5]), int(f[6]),
                    int(f[7], 16), int(f[8], 16), int(f[9]),
                    int(f[10]), int(f[11]), int(f[12], 16),
                    int(f[13], 16), int(f[14], 16),
                    int(f[15], 16), int(f[16])))
    print(f"rows: {len(raw)}", flush=True)
    with Pool(15) as pool:
        wss = pool.map(_ws, [(r[4], r[5]) for r in raw],
                       chunksize=1000)
    data = defaultdict(list)
    infeas = defaultdict(int)
    for r, sc in zip(raw, wss):
        (mhex, key, theta, fire, f4v, rfv, rsh, lsh, kf, Vlow,
         rdisc, ldisc, t4, s4) = r
        side = key[1]
        req2 = (1 if fire else 0) if side == "up" else \
            (-1 if fire else 0)
        jlo, jhi = jinterval(Vlow, kf, rfv, req2)
        m = int(mhex, 16)
        half = (m * 2654435761) & 1
        tau = t4 / (1 << s4)
        mf = (m & ((1 << 63) - 1)) / (1 << 63)
        xd12 = min(11, (rdisc * 12) >> rsh)
        st = (sc >> max(rsh - 59, 0)) & 63
        if jlo > jhi:
            infeas[key] += 1
        data[key].append((half, tau, mf, jlo, jhi, st, xd12))
    for key in sorted(data):
        rows = data[key]
        n = len(rows)
        feas = 1 - infeas[key] / n
        # base: best constant j per zone? use global best const j
        cnt = defaultdict(int)
        for half, tau, mf, jlo, jhi, st, xd in rows:
            if half == 0:
                for j in range(jlo, jhi + 1):
                    cnt[j] += 1
        jconst = max(cnt, key=cnt.get) if cnt else 0
        okc = sum(1 for r in rows if r[0] == 1
                  and r[3] <= jconst <= r[4])
        nte = sum(1 for r in rows if r[0] == 1)
        # zones: fit on train half
        zrows = defaultdict(list)
        for half, tau, mf, jlo, jhi, st, xd in rows:
            if half == 0:
                zrows[xd].append((tau, mf, jlo, jhi, st))
        zlist = sorted(zrows)
        with Pool(min(12, len(zlist)),
                  initializer=init_z,
                  initargs=(dict(zrows),)) as pool:
            fits = dict(pool.map(fit_zone, zlist))
        # J0 held-out + residual c-offsets per (zone, state)
        coff = defaultdict(lambda: defaultdict(int))
        for half, tau, mf, jlo, jhi, st, xd in rows:
            if half != 0 or xd not in fits or fits[xd] is None:
                continue
            q, a, b = fits[xd]
            x = q * tau + a * mf + b
            for c in range(-3, 4):
                j = round(x + c)
                if jlo <= j <= jhi:
                    coff[(xd, st)][c] += 1
        cbest = {k: max(v, key=v.get) for k, v in coff.items()}
        ok0 = ok1 = 0
        for half, tau, mf, jlo, jhi, st, xd in rows:
            if half != 1:
                continue
            f = fits.get(xd)
            if f is None:
                j0 = j1 = jconst
            else:
                q, a, b = f
                x = q * tau + a * mf + b
                j0 = round(x)
                j1 = round(x + cbest.get((xd, st), 0))
            ok0 += jlo <= j0 <= jhi
            ok1 += jlo <= j1 <= jhi
        print(f"{key}: n={n} feas={feas:.4f} "
              f"const-j={okc / max(nte, 1):.4f} "
              f"J0={ok0 / max(nte, 1):.4f} "
              f"J1={ok1 / max(nte, 1):.4f}", flush=True)


if __name__ == "__main__":
    main()
