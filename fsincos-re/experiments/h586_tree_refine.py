#!/usr/bin/env python3
"""h586: tree refinement round — 4:2 d-input choices, chunk
overlap, last-hot-one placement, seam-carry retirement; JOINT
objective over (9,1)+(9,2)@-72 up bands.

Config = (hot, ovl, lasthot, ret, gname, pname, dvec):
  hot     'next' | 'drop'      (h584 semantics)
  ovl     0 | 1                (chunk Booth overlap = 0 | prev top bit)
  lasthot 'drop' | 'fb' | 'r13' (a pass's trailing pend hot-one:
          lost | OR into fbS slot | OR into row 13; 'drop' only
          meaningful choice when hot='drop')
  ret     'shift' | 'addS'     (retire = plain shift | seam carry
          of the retired low fields resolved into S)
  gname   level-1 grouping (nat/fb1/spl, h584)
  pname   level-2 pairing (h584)
  dvec    7 ints 0..3: which input each 4:2 holds out as 'd'
          (4 level-1 groups, level-2 a, level-2 b, level-3);
          dvec=(3,)*7 == h584's csa(csa(a,b,c),d)
Role fixed 'fr' (f4 x rf), w=27, low-first — the h584 winners.
Baseline continuity: ('next',0,'drop','shift',nat,14_23,(3,)*7)
must reproduce h584's split_state bit-for-bit (mode 'check').

Modes:
  check                  verify baseline == h584 split_state
  search STRIDE SAMP     random sample per (hot,ovl) + anchors
  refine STRIDE          hill-climb from h586_top.json
  final STRIDE           rescore h586_top.json configs
Band rows from h586_band.tsv (h586a).  Split-half by m-hash.
"""
import json
import random
import sys
from collections import defaultdict
from multiprocessing import Pool

WIDTH = 200
MASK = (1 << WIDTH) - 1
W = 27
DIG = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}
TARGETS = [((9, 1, -72), "up"), ((9, 2, -72), "up")]
GROUPINGS = {
    "nat": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11],
            [12, 13, 14, 15]],
    "fb1": [[14, 15, 0, 1], [2, 3, 4, 5], [6, 7, 8, 9],
            [10, 11, 12, 13]],
    "spl": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 14],
            [11, 12, 13, 15]],
}
PAIRINGS = {"12_34": ((0, 1), (2, 3)),
            "13_24": ((0, 2), (1, 3)),
            "14_23": ((0, 3), (1, 2))}


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def c42v(v0, v1, v2, v3, dsel):
    if dsel == 0:
        d, a, b, c = v0, v1, v2, v3
    elif dsel == 1:
        d, a, b, c = v1, v0, v2, v3
    elif dsel == 2:
        d, a, b, c = v2, v0, v1, v3
    else:
        d, a, b, c = v3, v0, v1, v2
    s1, c1 = csa(a, b, c)
    return csa(s1, c1, d)


def booth_chunks(f4v, rfv, hot, ovl):
    """Per-chunk (rows14, pend) for role fr, w=27, low-first.
    rows are chunk-local columns; pend = trailing hot-one (col of
    the top negative digit) or 0."""
    nb = rfv.bit_length()
    out = []
    pos = 0
    while pos < nb:
        y = (rfv >> pos) & ((1 << W) - 1)
        ob = ((rfv >> (pos - 1)) & 1) if (pos > 0 and ovl) else 0
        y2 = (y << 1) | ob
        nb2 = max(y2.bit_length(), 1)
        rows = []
        pend = 0
        for i in range(0, nb2, 2):
            d = DIG[(y2 >> i) & 7]
            row = 0
            if d > 0:
                row = (d * f4v << i) & MASK
            elif d < 0:
                row = ((((~((-d) * f4v)) & MASK) << i) & MASK)
            if hot == "next":
                row |= pend
                pend = (1 << i) if d < 0 else 0
            elif d < 0 and i >= W:
                rows.append(1 << i)
            rows.append(row)
        rows = rows[:14]
        while len(rows) < 14:
            rows.append(0)
        out.append((rows, pend if hot == "next" else 0))
        pos += W
    return out


def split_state(chunks, rsh, lasthot, ret, grouping, pairing,
                dvec):
    S = C = 0
    col0 = 0
    wm = (1 << W) - 1
    last = len(chunks) - 1
    for ci, (rows, pend) in enumerate(chunks):
        it = rows + [S, C]
        if pend:
            if lasthot == "fb":
                it[14] |= pend
            elif lasthot == "r13":
                it[13] |= pend
        gs = []
        for gi, grp in enumerate(grouping):
            gs.append(c42v(it[grp[0]], it[grp[1]], it[grp[2]],
                           it[grp[3]], dvec[gi]))
        (i1, i2), (i3, i4) = pairing
        l2a = c42v(gs[i1][0], gs[i1][1], gs[i2][0], gs[i2][1],
                   dvec[4])
        l2b = c42v(gs[i3][0], gs[i3][1], gs[i4][0], gs[i4][1],
                   dvec[5])
        S, C = c42v(l2a[0], l2a[1], l2b[0], l2b[1], dvec[6])
        if ci < last:
            if ret == "addS":
                cout = ((S & wm) + (C & wm)) >> W
                S = ((S >> W) + cout) & MASK
                C >>= W
            else:
                S >>= W
                C >>= W
            col0 += W
    cs = rsh - col0
    if cs < 0:
        cs = 0
    return ((S >> cs) & 1, (C >> (cs + 1)) & 1)


ROWS = None
CACHE = {"key": None, "data": None}


def init_rows(r):
    global ROWS
    ROWS = r


def get_chunks(key, hot, ovl):
    ck = (key, hot, ovl)
    if CACHE["key"] != ck:
        tr, te = ROWS[key]
        CACHE["data"] = [
            [booth_chunks(f4v, rfv, hot, ovl)
             for mb, fire, f4v, rfv, rsh in part]
            for part in (tr, te)]
        CACHE["key"] = ck
    return CACHE["data"]


def fit_score(bytr, byte):
    ok = n = 0
    for st2, hist in byte.items():
        htr = bytr.get(st2)
        if htr:
            mbs = sorted(htr)
            tot1 = sum(htr[mb][1] for mb in mbs)
            # threshold t: predict fire iff mb >= t
            best, bt = -1, mbs[0]
            c0 = c1 = 0  # counts below t
            for t in mbs + [mbs[-1] + 1]:
                acc = c0 + (tot1 - c1)
                if acc > best:
                    best, bt = acc, t
                if t <= mbs[-1]:
                    c0 += htr[t][0] if t in htr else 0
                    c1 += htr[t][1] if t in htr else 0
        else:
            bt = 0
        for mb, (n0, n1) in hist.items():
            ok += n1 if mb >= bt else n0
            n += n0 + n1
    return ok, n


def fit_score_exact(bytr, byte):
    """h584-exact scoring: thresholds from candidate set of train
    mb values."""
    ok = n = 0
    for st2, hist in byte.items():
        htr = bytr.get(st2)
        if htr:
            cands = sorted(htr)
            cands.append(cands[-1] + 1)
            best = (-1, 0)
            for t in cands:
                acc = sum((n1 if mb >= t else n0)
                          for mb, (n0, n1) in htr.items())
                if acc > best[0]:
                    best = (acc, t)
            bt = best[1]
        else:
            bt = 0
        for mb, (n0, n1) in hist.items():
            ok += n1 if mb >= bt else n0
            n += n0 + n1
    return ok, n


def eval_cfg(cfg):
    hot, ovl, lasthot, ret, gname, pname, dvec = cfg
    grouping = GROUPINGS[gname]
    pairing = PAIRINGS[pname]
    tot_ok = tot_n = 0
    per = {}
    for key in ROWS:
        chtr, chte = get_chunks(key, hot, ovl)
        tr, te = ROWS[key]
        hists = []
        for part, ch in ((tr, chtr), (te, chte)):
            by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
            for row, chunks in zip(part, ch):
                mb, fire, f4v, rfv, rsh = row
                st2 = split_state(chunks, rsh, lasthot, ret,
                                  grouping, pairing, dvec)
                by[st2][mb][fire] += 1
            hists.append(by)
        ok, n = fit_score_exact(hists[0], hists[1])
        per[str(key)] = (ok, n)
        tot_ok += ok
        tot_n += n
    return cfg, tot_ok / max(tot_n, 1), per


def load_rows(stride):
    rowsd = defaultdict(lambda: ([], []))
    cnt = defaultdict(int)
    for line in open("h586_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        cnt[key] += 1
        if (cnt[key] - 1) % stride:
            continue
        m = int(f[0], 16)
        half = (m * 2654435761) & 1
        rowsd[key][half].append(
            (int(f[5]), int(f[6]), int(f[7], 16), int(f[8], 16),
             int(f[9])))
    return dict(rowsd)


def run_eval(rowsd, cfgs, nw=15):
    # sort so same (hot, ovl) configs are contiguous per worker
    cfgs = sorted(set(cfgs))
    with Pool(nw, initializer=init_rows,
              initargs=(rowsd,)) as pool:
        res = pool.map(eval_cfg, cfgs,
                       chunksize=max(1, len(cfgs) // (nw * 4)))
    return res


def anchors():
    out = []
    for hot in ("next", "drop"):
        for ovl in (0, 1):
            lhs = ("drop", "fb", "r13") if hot == "next" \
                else ("drop",)
            for lh in lhs:
                for ret in ("shift", "addS"):
                    for g in GROUPINGS:
                        for p in PAIRINGS:
                            out.append((hot, ovl, lh, ret, g, p,
                                        (3,) * 7))
    return out


def mode_check():
    sys.path.insert(0, ".")
    import h584_constrained_tree as H
    rowsd = load_rows(64)
    bad = tot = 0
    for key, (tr, te) in rowsd.items():
        for mb, fire, f4v, rfv, rsh in tr[:200] + te[:200]:
            ref = H.split_state(f4v, rfv, rsh,
                                ("fr", 27, "next", "nat",
                                 "14_23"))
            chunks = booth_chunks(f4v, rfv, "next", 0)
            got = split_state(chunks, rsh, "drop", "shift",
                              GROUPINGS["nat"],
                              PAIRINGS["14_23"], (3,) * 7)
            tot += 1
            if ref != got:
                bad += 1
    print(f"check: {tot} rows, {bad} mismatches")


def mode_search(stride, samp):
    rowsd = load_rows(stride)
    for key, (tr, te) in rowsd.items():
        print(f"{key}: tr={len(tr)} te={len(te)}", flush=True)
    rng = random.Random(58601)
    cfgs = anchors()
    for hot in ("next", "drop"):
        for ovl in (0, 1):
            lhs = ("drop", "fb", "r13") if hot == "next" \
                else ("drop",)
            for _ in range(samp):
                cfgs.append((
                    hot, ovl, rng.choice(lhs),
                    rng.choice(("shift", "addS")),
                    rng.choice(list(GROUPINGS)),
                    rng.choice(list(PAIRINGS)),
                    tuple(rng.randrange(4) for _ in range(7))))
    print(f"configs: {len(set(cfgs))}", flush=True)
    res = run_eval(rowsd, cfgs)
    res.sort(key=lambda r: -r[1])
    for cfg, acc, per in res[:20]:
        print(f"{acc:.4f}  {cfg}  {per}")
    top = [{"cfg": list(cfg[:6]) + [list(cfg[6])], "acc": acc}
           for cfg, acc, per in res[:40]]
    json.dump(top, open("h586_top.json", "w"), indent=1)
    print("wrote h586_top.json")


def neighbors(cfg):
    hot, ovl, lasthot, ret, g, p, dvec = cfg
    out = []
    for i in range(7):
        for v in range(4):
            if v != dvec[i]:
                dv = list(dvec)
                dv[i] = v
                out.append((hot, ovl, lasthot, ret, g, p,
                            tuple(dv)))
    for g2 in GROUPINGS:
        if g2 != g:
            out.append((hot, ovl, lasthot, ret, g2, p, dvec))
    for p2 in PAIRINGS:
        if p2 != p:
            out.append((hot, ovl, lasthot, ret, g, p2, dvec))
    lhs = ("drop", "fb", "r13") if hot == "next" else ("drop",)
    for lh in lhs:
        if lh != lasthot:
            out.append((hot, ovl, lh, ret, g, p, dvec))
    for r2 in ("shift", "addS"):
        if r2 != ret:
            out.append((hot, ovl, lasthot, r2, g, p, dvec))
    out.append((hot, 1 - ovl, lasthot, ret, g, p, dvec))
    return out


def mode_refine(stride, nseed=6, rounds=8):
    rowsd = load_rows(stride)
    top = json.load(open("h586_top.json"))
    seeds = []
    for t in top[:nseed]:
        c = t["cfg"]
        seeds.append((c[0], c[1], c[2], c[3], c[4], c[5],
                      tuple(c[6])))
    best = {}
    cur = seeds
    evald = {}
    for rnd in range(rounds):
        cand = set(cur)
        for c in cur:
            cand.update(neighbors(c))
        cand = [c for c in cand if c not in evald]
        if not cand:
            break
        res = run_eval(rowsd, cand)
        for cfg, acc, per in res:
            evald[cfg] = (acc, per)
        allr = sorted(evald.items(), key=lambda kv: -kv[1][0])
        print(f"round {rnd}: evaluated {len(cand)}, "
              f"best {allr[0][1][0]:.4f} {allr[0][0]}",
              flush=True)
        newcur = [cfg for cfg, _ in allr[:nseed]]
        if newcur == cur:
            break
        cur = newcur
    allr = sorted(evald.items(), key=lambda kv: -kv[1][0])
    for cfg, (acc, per) in allr[:15]:
        print(f"{acc:.4f}  {cfg}  {per}")
    top = [{"cfg": list(cfg[:6]) + [list(cfg[6])], "acc": acc}
           for cfg, (acc, per) in allr[:20]]
    json.dump(top, open("h586_top.json", "w"), indent=1)
    print("wrote h586_top.json (refined)")


def mode_final(stride):
    rowsd = load_rows(stride)
    for key, (tr, te) in rowsd.items():
        print(f"{key}: tr={len(tr)} te={len(te)}", flush=True)
    top = json.load(open("h586_top.json"))
    cfgs = []
    for t in top[:12]:
        c = t["cfg"]
        cfgs.append((c[0], c[1], c[2], c[3], c[4], c[5],
                     tuple(c[6])))
    # baseline for reference
    cfgs.append(("next", 0, "drop", "shift", "nat", "14_23",
                 (3,) * 7))
    res = run_eval(rowsd, cfgs)
    res.sort(key=lambda r: -r[1])
    for cfg, acc, per in res:
        pp = {k: f"{ok}/{n}={ok / max(n, 1):.4f}"
              for k, (ok, n) in per.items()}
        print(f"{acc:.4f}  {cfg}\n        {pp}")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "check":
        mode_check()
    elif mode == "search":
        mode_search(int(sys.argv[2]), int(sys.argv[3]))
    elif mode == "refine":
        mode_refine(int(sys.argv[2]))
    elif mode == "final":
        mode_final(int(sys.argv[2]))
