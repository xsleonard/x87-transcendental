#!/usr/bin/env python3
"""h1019: solve the remaining gate in the total integer-decision frame.

Absolute +/-1 probes conflate the selector with an already-present model or
exact-tail carry.  Group the complete h975 admissible sets by structural
decision inputs and intersect each group's allowed values.  A nonempty
intersection gives a census-wide safe total decision for that state.
"""

from collections import Counter, defaultdict


def load_tsv(path):
    with open(path) as src:
        header = next(src).rstrip("\n").split("\t")
        index = {name: offset for offset, name in enumerate(header)}
        return index, [line.rstrip("\n").split("\t") for line in src]


fix, feature_rows = load_tsv("h970_features.tsv")
nix, nhw_rows = load_tsv("h975_nhw.tsv")
features = {(row[fix["insn"]], row[fix["op"]]): row
            for row in feature_rows}


rows = []
for nrow in nhw_rows:
    key = nrow[nix["insn"]], nrow[nix["op"]]
    feature = features[key]
    get = lambda name: feature[fix[name]]
    le, re = int(get("lefte2")), int(get("righte2"))
    left, right = int(get("leftsig"), 16), int(get("rightsig"), 16)
    payload = int(get("pay2")) if get("pay2") != "-" else 0
    scale = min(le, re, le - 8 if payload else le)
    s_value = left << (le - scale)
    if payload:
        s_value += payload << (le - 8 - scale)
    b_value = right << (re - scale)
    magnitude = s_value - b_value
    cut = magnitude.bit_length() - 67
    pmask = ~(s_value ^ b_value)
    prun = 0
    while prun < 32 and ((pmask >> (cut + prun)) & 1):
        prun += 1
    sum8 = int(nrow[nix["sum8"]])
    rows.append({
        "key": key, "line": "TOP" if sum8 >= 128 else "LOW",
        "act": int(nrow[nix["act"]]), "sum8": sum8,
        "nset": {int(value) for value in nrow[nix["nset"]].split(",")},
        "pinned": nrow[nix["pinned"]] == "1", "half": get("half"),
        "ncar": int(nrow[nix["ncar"]]),
        "nexact": int(nrow[nix["nexact"]]),
        "nexL": int(nrow[nix["nexL"]]),
        "pcut": (pmask >> cut) & 1, "prun": prun,
        "p8": (pmask >> cut) & 0xff,
        "g8": ((~s_value & b_value) >> cut) & 0xff,
        "low3": int(get("low3")), "dist": int(get("dist")),
        "rsh": int(get("rsh")), "rud": int(get("rud")),
        "payload": payload, "me2": int(get("me2")),
    })


def report(fields):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[name] for name in fields)].append(row)
    determined = safe_changed = pinned_changed = ambiguous = 0
    details = []
    for state, sample in groups.items():
        intersection = set(sample[0]["nset"])
        for row in sample[1:]:
            intersection &= row["nset"]
        if not intersection:
            ambiguous += len(sample)
            continue
        determined += len(sample)
        # Prefer the model carry if safe, then zero, then the smallest
        # magnitude value.  Count states where a different common decision
        # is forced or available.
        ncar_values = {row["ncar"] for row in sample}
        baseline = next(iter(ncar_values)) if len(ncar_values) == 1 else None
        if baseline in intersection:
            choice = baseline
        elif 0 in intersection:
            choice = 0
        else:
            choice = min(intersection, key=lambda value: (abs(value), value))
        changed = sum(choice != row["ncar"] for row in sample)
        pinchange = sum(row["pinned"] and choice != row["ncar"]
                        for row in sample)
        safe_changed += changed
        pinned_changed += pinchange
        if changed or pinchange:
            details.append((pinchange, changed, len(sample), state,
                            tuple(sorted(intersection)), choice,
                            Counter(tuple(sorted(row["nset"]))
                                    for row in sample)))
    print("\nfields", fields)
    print("  groups", len(groups), "determined rows", determined,
          "ambiguous rows", ambiguous, "safe-changed", safe_changed,
          "pinned-changed", pinned_changed)
    for item in sorted(details, reverse=True)[:60]:
        pinchange, changed, count, state, intersection, choice, shapes = item
        print("  state=%s n=%d common=%s rows=%d changed=%d pin=%d shapes=%s"
              % (state, choice, intersection, count, changed, pinchange,
                 dict(shapes)))


specs = (
    ("line", "act", "pcut", "ncar", "nexact"),
    ("line", "act", "p8", "ncar", "nexact"),
    ("line", "act", "prun", "ncar", "nexact"),
    ("line", "act", "pcut", "ncar", "nexact", "nexL"),
    ("line", "act", "p8", "ncar", "nexact", "nexL"),
    ("line", "act", "prun", "ncar", "nexact", "nexL"),
    ("line", "act", "prun", "ncar", "nexact", "nexL", "rsh",
     "rud"),
    ("line", "act", "prun", "ncar", "nexact", "nexL", "sum8"),
)
print("rows", len(rows), "pinned", sum(row["pinned"] for row in rows))
for fields in specs:
    report(fields)

