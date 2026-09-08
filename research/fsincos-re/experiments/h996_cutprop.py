#!/usr/bin/env python3
"""h996: test the terminal subtraction's cut-relative propagate bit.

The absolute two-bit hunt in h995 exposed an interaction between the retained
left and right carrier words.  Those absolute columns are only shadows of the
actual adder coordinate: align the two signed terminal inputs, find the
67-bit output cut, and inspect the subtraction propagate bit at that cut.

This script tests the resulting predicate against the boundary-pinned n_hw
truth and, separately, checks every fired row against the admissible n-set so
that invisible architectural roundings cannot hide a contradiction.
"""

from collections import Counter, defaultdict


FEATURES = "h970_features.tsv"
NHW = "h975_nhw.tsv"


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        ix = {name: i for i, name in enumerate(header)}
        return ix, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv(FEATURES)
nix, nhw_rows = load_tsv(NHW)
features = {(r[fix["insn"]], r[fix["op"]]): r for r in feature_rows}


def terminal_frame(feature):
    """Return the aligned terminal subtraction and its retained-bit cut."""
    get = lambda name: feature[fix[name]]
    le = int(get("lefte2"))
    re = int(get("righte2"))
    left = int(get("leftsig"), 16)
    right = int(get("rightsig"), 16)
    # Frame the subtraction with the post-gate payload actually accumulated.
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    ls = int(get("leftsign"))
    rs = int(get("rightsign"))
    scale = min(le, re, le - 8 if payload else le)
    left_input = left << (le - scale)
    payload_input = abs(payload) << (le - 8 - scale) if payload else 0
    # The h970 cosine rows all have the same terminal sign geometry, but keep
    # this exact so the experiment fails loudly if that assumption changes.
    signed_left = -left_input if ls else left_input
    payload_sign = ls ^ (payload < 0)
    signed_payload = -payload_input if payload_sign else payload_input
    signed_right = -(right << (re - scale)) if rs else right << (re - scale)
    total = signed_left + signed_payload + signed_right
    magnitude = abs(total)
    cut = magnitude.bit_length() - 67
    if cut < 0:
        raise ValueError("terminal magnitude has fewer than 67 bits")

    # All census rows are a negative left(+payload) minus positive right in
    # magnitude space.  S is the magnitude-side minuend, B the subtrahend.
    if signed_left + signed_payload < 0 and signed_right >= 0:
        s_value = -(signed_left + signed_payload)
        b_value = signed_right
    elif signed_right < 0 and signed_left + signed_payload >= 0:
        s_value = -signed_right
        b_value = signed_left + signed_payload
    else:
        raise ValueError("unexpected terminal sign geometry")
    if s_value <= b_value or s_value - b_value != magnitude:
        raise ValueError("unexpected terminal magnitude ordering")

    propagate = (~(s_value ^ b_value) >> cut) & 1
    generate = ((~s_value & b_value) >> cut) & 1
    return {
        "S": s_value, "B": b_value, "mag": magnitude, "cut": cut,
        "pcut": propagate, "gcut": generate,
    }


rows = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    f = features[key]
    frame = terminal_frame(f)
    nset = {int(value) for value in nrow[nix["nset"]].split(",")}
    pinned = nrow[nix["pinned"]] == "1"
    nvalue = next(iter(nset)) if pinned else None
    sum8 = int(nrow[nix["sum8"]])
    # The two terminal ladders are separated by an enormous empty interval:
    # lower sums are 4..11 and upper sums are 249..262 in this census.
    line = "TOP" if sum8 >= 128 else "LOW"
    rows.append({
        "key": key, "half": f[fix["half"]], "line": line,
        "sum8": sum8, "act": int(nrow[nix["act"]]),
        "distance": int(nrow[nix["d"]]), "nset": nset,
        "ncar": int(nrow[nix["ncar"]]),
        "nexact": int(nrow[nix["nexact"]]),
        "label": nrow[nix["lab"]],
        "pinned": pinned, "n": nvalue, **frame,
    })


print("rows:", len(rows), "pinned:", sum(r["pinned"] for r in rows))
print("sum8 ranges:", {
    line: (min(r["sum8"] for r in rows if r["line"] == line),
           max(r["sum8"] for r in rows if r["line"] == line))
    for line in ("LOW", "TOP")
})

print("\nPinned lower-ladder cut-bit truth table (value n):")
table = Counter((r["half"], r["pcut"], r["n"])
                for r in rows if r["pinned"] and r["line"] == "LOW")
for key, count in sorted(table.items()):
    print("  %-3s pcut=%d n=%+d  %d" % (*key, count))

print("\nLower predicate n=+1 iff pcut=0:")
for half in ("FIT", "HOL"):
    sample = [r for r in rows
              if r["pinned"] and r["line"] == "LOW"
              and r["half"] == half]
    correct = sum((r["pcut"] == 0) == (r["n"] == 1) for r in sample)
    positives = sum(r["n"] == 1 for r in sample)
    print("  %s %d/%d correct, positives %d/%d" %
          (half, correct, len(sample), positives, positives))

fires = [r for r in rows if r["line"] == "LOW" and r["pcut"] == 0]
bad = [r for r in fires if 1 not in r["nset"]]
print("\nAll-census admissibility for fired lower rows:")
print("  fires", len(fires), "pinned", sum(r["pinned"] for r in fires),
      "unpinned", sum(not r["pinned"] for r in fires),
      "contradictions", len(bad))
print("  fired n-set shapes:",
      dict(sorted(Counter(tuple(sorted(r["nset"])) for r in fires).items())))
if bad:
    for row in bad[:20]:
        print("  BAD", row["key"], sorted(row["nset"]), row["sum8"],
              row["act"], row["distance"], row["cut"])

print("  fired (label,ncar,nexact,pinned):")
for cell, count in sorted(Counter((r["label"], r["ncar"], r["nexact"],
                                   r["pinned"]) for r in fires).items()):
    print("   ", cell, count)

print("\nCut-relative bit/run scan on pinned rows:")
for line, positive in (("LOW", 1), ("TOP", -1)):
    print(" ", line, "positive n", positive)
    sample = [r for r in rows if r["pinned"] and r["line"] == line]
    for offset in range(-8, 17):
        tabs = {}
        for half in ("FIT", "HOL"):
            cell = Counter()
            for row in sample:
                if row["half"] != half or row["n"] not in (0, positive):
                    continue
                position = row["cut"] + offset
                bit = ((~(row["S"] ^ row["B"]) >> position) & 1
                       if position >= 0 else 0)
                cell[bit, row["n"] == positive] += 1
            # Best polarity accuracy is an intentionally simple diagnostic.
            same = cell[0, 0] + cell[1, 1]
            flip = cell[0, 1] + cell[1, 0]
            tabs[half] = max(same, flip), sum(cell.values()), same >= flip
        if (tabs["FIT"][0] / max(1, tabs["FIT"][1]) >= .7
                or tabs["HOL"][0] / max(1, tabs["HOL"][1]) >= .7):
            print("    P[%+d] FIT %d/%d HOL %d/%d polarity=%s/%s" %
                  (offset, tabs["FIT"][0], tabs["FIT"][1],
                   tabs["HOL"][0], tabs["HOL"][1],
                   tabs["FIT"][2], tabs["HOL"][2]))

    runs = Counter()
    for row in sample:
        run = 0
        mask = ~(row["S"] ^ row["B"])
        while run < 80 and ((mask >> (row["cut"] + run)) & 1):
            run += 1
        runs[row["n"], run] += 1
    print("    propagate runs:", dict(sorted(runs.items())))


print("\nUpper-ladder relative P/G words by act and label (diagnostic):")
for act in (0, 1):
    sample = [r for r in rows
              if r["pinned"] and r["line"] == "TOP" and r["act"] == act]
    for width in (4, 8, 12, 16):
        patterns = defaultdict(Counter)
        for row in sample:
            mask = (1 << width) - 1
            pword = (~(row["S"] ^ row["B"]) >> row["cut"]) & mask
            gword = ((~row["S"] & row["B"]) >> row["cut"]) & mask
            patterns[row["n"]][(pword, gword)] += 1
        unique_pos = sum(count for word, count in patterns[-1].items()
                         if word not in patterns[0])
        print("  act%d width%d: carrier-only patterns %d/%d, distinct %d/%d" %
              (act, width, unique_pos, sum(patterns[-1].values()),
               len(patterns[-1]), len(patterns[0])))
        if width in (4, 8):
            for nvalue in (-1, 0):
                desc = ", ".join("P=%0*x G=%0*x:%d" %
                                 ((width + 3) // 4, word[0],
                                  (width + 3) // 4, word[1], count)
                                 for word, count in
                                 patterns[nvalue].most_common(16))
                print("    n=%+d %s" % (nvalue, desc))


def check_rule(name, choose):
    """Score a total integer-n rule against every admissible census set."""
    failed = [(r, choose(r)) for r in rows if choose(r) not in r["nset"]]
    pinned_failed = [(r, value) for r, value in failed if r["pinned"]]
    print("\n%s:" % name)
    print("  admissible %d/%d; pinned %d/%d" %
          (len(rows) - len(failed), len(rows),
           sum(r["pinned"] for r in rows) - len(pinned_failed),
           sum(r["pinned"] for r in rows)))
    print("  failures by (line,act,label,pinned,ncar,nexact,want):")
    failures = Counter((r["line"], r["act"], r["label"], r["pinned"],
                        r["ncar"], r["nexact"], value)
                       for r, value in failed)
    for cell, count in failures.most_common(24):
        print("   ", cell, count)


def upper_act0_rule(row):
    if row["line"] == "TOP" and row["act"] == 0:
        p4 = (~(row["S"] ^ row["B"]) >> row["cut"]) & 0xF
        return -1 if p4 == 0xF else 0
    return row["ncar"]


check_rule("replace upper act0 with P[cut:cut+4]==0xf", upper_act0_rule)


print("\nPinned upper categories by act/n/P8/G8/ncar/nexact:")
upper_categories = Counter()
for row in rows:
    if not row["pinned"] or row["line"] != "TOP":
        continue
    p8 = (~(row["S"] ^ row["B"]) >> row["cut"]) & 0xFF
    g8 = ((~row["S"] & row["B"]) >> row["cut"]) & 0xFF
    upper_categories[(row["act"], row["n"], p8, g8,
                      row["ncar"], row["nexact"])] += 1
for cell, count in upper_categories.most_common():
    print("  act%d n%+d P=%02x G=%02x ncar%+d nex%+d: %d" %
          (*cell, count))
