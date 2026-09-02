#!/usr/bin/env python3
"""h991: transfer the R59/R60 nonlinear square-residue frame to R95.

h984 found that the discarded fraction of ``sq * sq`` is the strongest
remaining marginal for the R95 integer decision.  h985 only changed the
rounding of the retained fourth-power carrier; it did not test the nonlinear
coordinate which closed the earlier standalone-cosine tie gate:

    M = low3 * (sq - 2**66) - (sq*sq mod 2**s4)

This script reconstructs that coordinate exactly, including the shipped
truncated-thirds bits, and scores it against the boundary-pinned ``n_hw``
truth.  Discovery and validation remain the banked FIT/HOL halves.
"""

from collections import Counter, defaultdict


FEATURES = "h970_features.tsv"
CORR = "h972_corr.tsv"
NHW = "h975_nhw.tsv"


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(header)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv(FEATURES)
cix, corr_rows = load_tsv(CORR)
nix, nhw_rows = load_tsv(NHW)

corr = {(r[cix["insn"]], r[cix["op"]]): r for r in corr_rows}
nhw = {(r[nix["insn"]], r[nix["op"]]): r for r in nhw_rows
       if r[nix["pinned"]] == "1"}


def floordiv(n, q):
    return n // q


def r60_u0(s4, side, distance, low3, b1, b2):
    if s4 == 66 and side == 1:
        qa, qg1, qg2, qp, qq, qk, qpar = 2, 2, 1, 0, 4, 1, 0
        wd = -5 * (distance - 7)
    elif s4 == 66 and side == 0:
        qa, qg1, qg2, qp, qq, qk, qpar = 4, 1, 0, 0, 2, 1, 0
        wd = -9 - 5 * (distance - 9)
    elif s4 == 67 and side == 0:
        qa, qg1, qg2, qp, qq, qk, qpar = 4, 2, 1, -2, 4, 2, 1
        wd = -5 * (distance - 7)
    else:
        qa, qg1, qg2, qp, qq, qk, qpar = 2, 2, 3, -3, 8, 2, 1
        wd = -4 - 2 * (distance - 7)
    lp = low3 & 1
    base = qa * low3 + qg1 * b1 + qg2 * b2 + qp * lp + wd
    return qk * floordiv(base, qq) + qpar * lp


rows = []
for f in feature_rows:
    key = f[fix["insn"]], f[fix["op"]]
    if key not in nhw:
        continue
    n = nhw[key]
    sq = int(f[fix["mulsig"]], 16)
    mag = int(f[fix["magsig"]], 16)
    low3 = int(f[fix["low3"]])
    distance = int(f[fix["dist"]])
    right_shift = int(f[fix["rsh"]])
    f4full = sq * sq
    s4 = f4full.bit_length() - 67
    t4 = f4full & ((1 << s4) - 1)
    sqlow = sq - (1 << 66)
    mreg = low3 * sqlow - t4
    side = int(mag >= 0xB504F333F9DE6800)

    rd = int(corr[key][cix["rdisc"]], 16)
    mexp = right_shift - 16 - (side == 0)
    mask = (1 << mexp) - 1
    rd3 = 3 * rd - ((2 * rd) & mask) - (rd & mask)
    b1 = int(rd3 >= (1 << right_shift))
    b2 = int(rd3 >= (1 << (right_shift + 1)))
    u0 = r60_u0(s4, side, distance, low3, b1, b2)
    tfire = int(mreg < u0 * (1 << 66))

    # All census corrections are negative, so n_hw=-1 is the
    # magnitude-up carry and n_hw=+1 is magnitude-down.
    nm = -int(n[nix["nset"]])
    half = f[fix["half"]]
    act = int(f[fix["act"]])
    sum8 = int(f[fix["sum8"]])
    line = "TOP" if sum8 >= 0xF0 else "LOW"
    rows.append({
        "key": key, "half": half, "nm": nm, "act": act,
        "sum8": sum8, "line": line, "d": distance,
        "low3": low3, "s4": s4, "side": side, "b1": b1,
        "b2": b2, "M": mreg, "u0": u0, "tfire": tfire,
    })


print("pinned rows:", len(rows))
print("labels:", dict(sorted(Counter(r["nm"] for r in rows).items())))
print("s4:", dict(sorted(Counter(r["s4"] for r in rows).items())))

print("\nR60 tie predicate vs magnitude decision:")
tab = Counter((r["line"], r["act"], r["tfire"], r["nm"])
              for r in rows)
for key, count in sorted(tab.items()):
    print("  %-4s act%d tfire%d nm%+d  %d" % (*key, count))


def best_cut(sample, positive):
    """Return best one-sided exact-M cut for positive vs zero labels."""
    grouped = defaultdict(lambda: [0, 0])
    for row in sample:
        if row["nm"] in (0, positive):
            grouped[row["M"]][row["nm"] == positive] += 1
    pts = sorted(grouped.items())
    if not pts:
        return None
    total_pos = sum(counts[1] for _, counts in pts)
    total_neg = sum(counts[0] for _, counts in pts)
    below_pos = below_neg = 0
    best = None
    for i in range(len(pts) + 1):
        total = total_pos + total_neg
        for sense in ("lt", "ge"):
            if sense == "lt":
                good = below_pos + (total_neg - below_neg)
            else:
                good = (total_pos - below_pos) + below_neg
            candidate = (good, sense, i, total_pos, total_neg, total)
            if best is None or candidate > best:
                best = candidate
        if i < len(pts):
            below_neg += pts[i][1][0]
            below_pos += pts[i][1][1]
    good, sense, i, npos, nneg, total = best
    if i == 0:
        cut = pts[0][0]
    elif i == len(pts):
        cut = pts[-1][0] + 1
    else:
        cut = (pts[i - 1][0] + pts[i][0] + 1) // 2
    return good, total, sense, cut, npos, nneg


print("\nGlobal M cuts, discovered on FIT and scored unchanged on HOL:")
for line, act, positive in (("TOP", 0, 1), ("TOP", 1, 1),
                            ("LOW", 0, -1), ("LOW", 1, -1)):
    fit = [r for r in rows if r["half"] == "FIT"
           and r["line"] == line and r["act"] == act]
    hol = [r for r in rows if r["half"] == "HOL"
           and r["line"] == line and r["act"] == act
           and r["nm"] in (0, positive)]
    result = best_cut(fit, positive)
    if result is None:
        continue
    good, total, sense, cut, npos, nneg = result
    pred = (lambda m: m < cut) if sense == "lt" else (lambda m: m >= cut)
    hgood = sum(pred(r["M"]) == (r["nm"] == positive) for r in hol)
    print("  %s act%d nm%+d: FIT %d/%d (%s M %d), HOL %d/%d"
          % (line, act, positive, good, total, sense, cut,
             hgood, len(hol)))


# Cellwise monotonicity is diagnostic only: cells are defined without M,
# and cuts are learned on FIT then transferred verbatim to HOL.
cell_fields = ("line", "act", "s4", "side", "d", "low3", "b1", "b2")
by_cell = defaultdict(list)
for row in rows:
    by_cell[tuple(row[name] for name in cell_fields)].append(row)

print("\nCellwise FIT->HOL M cuts (cells with both labels in FIT):")
summary = Counter()
shown = []
for cell, sample in sorted(by_cell.items()):
    positive = 1 if cell[0] == "TOP" else -1
    fit = [r for r in sample if r["half"] == "FIT"]
    hol = [r for r in sample if r["half"] == "HOL"
           and r["nm"] in (0, positive)]
    if not hol or not ({r["nm"] for r in fit} >= {0, positive}):
        continue
    result = best_cut(fit, positive)
    if result is None:
        continue
    good, total, sense, cut, _, _ = result
    pred = (lambda m: m < cut) if sense == "lt" else (lambda m: m >= cut)
    hgood = sum(pred(r["M"]) == (r["nm"] == positive) for r in hol)
    summary["fit_good"] += good
    summary["fit_total"] += total
    summary["hol_good"] += hgood
    summary["hol_total"] += len(hol)
    shown.append((len(hol), cell, good, total, sense, cut, hgood, len(hol)))
print("  aggregate FIT %d/%d; HOL %d/%d across %d mixed cells"
      % (summary["fit_good"], summary["fit_total"], summary["hol_good"],
         summary["hol_total"], len(shown)))
for _, cell, good, total, sense, cut, hgood, htotal in sorted(
        shown, reverse=True)[:30]:
    print("  %s: FIT %d/%d %s %d; HOL %d/%d"
          % (cell, good, total, sense, cut, hgood, htotal))


print("\nGranularity test: FIT-learned M cuts transferred to HOL")
group_specs = (
    ("line", "act", "s4", "side"),
    ("line", "act", "sum8", "s4", "side"),
    ("line", "act", "sum8", "s4", "side", "d"),
    ("line", "act", "sum8", "s4", "side", "d", "low3"),
    ("line", "act", "sum8", "s4", "side", "d", "low3", "b1", "b2"),
)
for fields in group_specs:
    cells = defaultdict(list)
    for row in rows:
        cells[tuple(row[name] for name in fields)].append(row)
    fit_good = fit_total = hol_good = hol_total = covered = exact_fit = 0
    for cell, sample in cells.items():
        positive = 1 if cell[0] == "TOP" else -1
        fit = [r for r in sample if r["half"] == "FIT"
               and r["nm"] in (0, positive)]
        hol = [r for r in sample if r["half"] == "HOL"
               and r["nm"] in (0, positive)]
        if not fit or not hol:
            continue
        result = best_cut(fit, positive)
        good, total, sense, cut, _, _ = result
        pred = (lambda m: m < cut) if sense == "lt" \
            else (lambda m: m >= cut)
        hgood = sum(pred(r["M"]) == (r["nm"] == positive) for r in hol)
        fit_good += good
        fit_total += total
        hol_good += hgood
        hol_total += len(hol)
        covered += 1
        exact_fit += good == total
    print("  %-50s cells %3d exact-fit %3d: FIT %d/%d HOL %d/%d"
          % ((",".join(fields)), covered, exact_fit, fit_good, fit_total,
             hol_good, hol_total))
