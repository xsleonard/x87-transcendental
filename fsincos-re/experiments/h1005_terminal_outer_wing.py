#!/usr/bin/env python3
"""h1005: audit dyadic outer-wing terminal-borrow predicates.

The remaining active/top rows need an absolute -1 value-frame correction.
Test predicates of the structural form

    discarded / ulp > 1 - 2^-k

against every admissible integer set in the complete h975 census.  A row is
safe only when -1 is in its admissible set; pinned rows separately measure
decisions learned from hardware rather than merely output-invisible rows.
"""

from collections import Counter


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(row[fix["insn"]], row[fix["op"]]): row
            for row in feature_rows}


records = []
for nrow in nhw_rows:
    feature = features[(nrow[nix["insn"]], nrow[nix["op"]])]
    get = lambda name: feature[fix[name]]
    left_e2, right_e2 = int(get("lefte2")), int(get("righte2"))
    left = int(get("leftsig"), 16)
    right = int(get("rightsig"), 16)
    # This probe deliberately reads the counterfactual pre-gate payload.
    # The top-line qualification still comes from h975's real, post-gate
    # accumulator below.
    payload = int(get("payload"))
    scale = min(left_e2, right_e2,
                left_e2 - 8 if payload else left_e2)
    signed_left = (-1 if int(get("leftsign")) else 1) * (
        left << (left_e2 - scale))
    if payload:
        payload_sign = int(get("leftsign")) ^ (payload < 0)
        signed_left += (-1 if payload_sign else 1) * (
            abs(payload) << (left_e2 - 8 - scale))
    signed_right = (-1 if int(get("rightsign")) else 1) * (
        right << (right_e2 - scale))
    magnitude = abs(signed_left + signed_right)
    cut = magnitude.bit_length() - 67
    residue = magnitude & ((1 << cut) - 1) if cut > 0 else 0
    records.append({
        "act": int(nrow[nix["act"]]),
        "top": int(nrow[nix["sum8"]]) >= 0xF0,
        "cut": cut,
        "residue": residue,
        "target": -1 if signed_left + signed_right < 0 else 1,
        "nset": {int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1",
        "half": get("half"),
        "lab": nrow[nix["lab"]],
    })


print("k threshold fires safe bad pinned pinned_-1 FIT/HOL")
for k in range(1, 21):
    numerator = (1 << k) - 1
    fired = [row for row in records
             if row["act"] and row["top"] and row["cut"] > 0
             and row["residue"] * (1 << k)
             > numerator * (1 << row["cut"])]
    safe = [row for row in fired if row["target"] in row["nset"]]
    bad = [row for row in fired if row["target"] not in row["nset"]]
    pinned = [row for row in fired if row["pinned"]]
    pinned_target = [row for row in pinned
                     if row["nset"] == {row["target"]}]
    halves = Counter(row["half"] for row in pinned_target)
    print("%2d %d/%d %4d %4d %4d %4d %4d/%4d" % (
        k, numerator, 1 << k, len(fired), len(safe), len(bad),
        len(pinned), halves["FIT"], halves["HOL"]))

cutoff = 10
numerator = (1 << cutoff) - 1
fired = [row for row in records
         if row["act"] and row["top"] and row["cut"] > 0
         and row["residue"] * (1 << cutoff)
         > numerator * (1 << row["cut"])]
print("\nk=10 strata:")
for key, count in sorted(Counter(
        (row["lab"], row["pinned"], row["target"],
         tuple(sorted(row["nset"])),
         row["cut"]) for row in fired).items()):
    print("  %-10s pinned=%d target=%+d nset=%-18s cut=%2d n=%d" %
          (key[0], key[1], key[2], ",".join(map(str, key[3])),
           key[4], count))
