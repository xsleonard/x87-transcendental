#!/usr/bin/env python3
"""h470: merge both family batches into one labeled corpus.

Labels the h469 batch with the identical h465 machinery (both codings,
same probe, same feature columns) and concatenates with the existing
h464 labels (which already include the pre-third-pass corpus),
deduplicated by input.  Output: h464_package/combined_labels.tsv.

Run from /tmp/stageA.
"""
from multiprocessing import Pool

from h437_gate_extraction import ROUNDING_MODES, parse_trace_line
from h465_label_contrast import label_row

PKG_NEW = "h469_package"
OUT = "h464_package/combined_labels.tsv"


def main():
    hw_files = {m: open(f"{PKG_NEW}/hw_{m}.txt").read().splitlines()
                for m in ROUNDING_MODES}
    jobs = []
    with open(f"{PKG_NEW}/selected.tsv") as fh:
        for i, line in enumerate(fh):
            se, sig, theta, trace = line.rstrip("\n").split("\t")
            fields = parse_trace_line(trace)
            fields["_se"], fields["_sig"] = se, sig
            hw_sigs = {}
            for m in ROUNDING_MODES:
                tokens = hw_files[m][i].split()
                hw_sigs[m] = int(tokens[2], 16) if tokens[0] == "OK" else -1
            jobs.append((fields, hw_sigs))
    with Pool(8) as pool:
        labeled = [r for r in pool.map(label_row, jobs, chunksize=1000)
                   if r is not None and -3 <= r["theta"] <= 3]
    print(f"h469 labeled rows: {len(labeled)}")

    unique = {}
    cols = None
    with open("h464_package/labels.tsv") as fh:
        cols = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            r = dict(zip(cols, line.rstrip("\n").split("\t")))
            unique[(r["se"], r["sig"])] = r
    n_old = len(unique)
    for r in labeled:
        unique[(str(r["se"]), str(r["sig"]))] = {c: str(r[c]) for c in cols}
    print(f"old rows: {n_old}, merged total: {len(unique)}")

    with open(OUT, "w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in unique.values():
            fh.write("\t".join(r[c] for c in cols) + "\n")
    fires = sum(int(r["fire_pre"]) for r in unique.values())
    print(f"wrote {OUT}: {len(unique)} rows, {fires} fires (pre coding)")


if __name__ == "__main__":
    main()
