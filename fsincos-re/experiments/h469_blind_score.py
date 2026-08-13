#!/usr/bin/env python3
"""h469 scorer: grade the locked blind predictions against the fresh
captures.

Run strictly AFTER h469_blind_predict.py has written predictions.tsv
(this script is the first to read the fresh hardware files).  Each
fresh row is labeled with the same machinery as h465 (pre-patch probe
around prepay -> fire_pre); rows the probe cannot classify are dropped.
Reports: confusion for the FIRE and CLEAN calls, and calibration of
p_fire in ten bands.

Run from /tmp/stageA.
"""
from collections import defaultdict
from multiprocessing import Pool

from h437_gate_extraction import ROUNDING_MODES, parse_trace_line
from h465_label_contrast import label_row

PKG = "h469_package"


def main():
    hw_files = {m: open(f"{PKG}/hw_{m}.txt").read().splitlines()
                for m in ROUNDING_MODES}
    jobs = []
    keys = []
    with open(f"{PKG}/selected.tsv") as fh:
        for i, line in enumerate(fh):
            se, sig, theta, trace = line.rstrip("\n").split("\t")
            fields = parse_trace_line(trace)
            fields["_se"], fields["_sig"] = se, sig
            hw_sigs = {}
            for m in ROUNDING_MODES:
                tokens = hw_files[m][i].split()
                hw_sigs[m] = int(tokens[2], 16) if tokens[0] == "OK" else -1
            jobs.append((fields, hw_sigs))
            keys.append((se, sig))
    with Pool(8) as pool:
        labeled = pool.map(label_row, jobs, chunksize=1000)
    truth = {}
    for key, lab in zip(keys, labeled):
        if lab is not None:
            truth[key] = lab["fire_pre"]
    print(f"fresh rows: {len(jobs)}, classifiable: {len(truth)}, "
          f"fires: {sum(truth.values())}")

    confusion = defaultdict(lambda: [0, 0])
    bands = defaultdict(lambda: [0, 0])
    with open(f"{PKG}/predictions.tsv") as fh:
        fh.readline()
        for line in fh:
            se, sig, theta, nib, pay, rud, p, call = \
                line.rstrip("\n").split("\t")
            key = (se, sig)
            if key not in truth:
                continue
            fire = truth[key]
            confusion[call][fire] += 1
            bands[min(int(float(p) * 10), 9)][fire] += 1
    for call in ("FIRE", "CLEAN", "ABSTAIN"):
        n0, n1 = confusion[call]
        n = n0 + n1
        print(f"  call {call:7s}: n={n:6d}  actual fires {n1:5d} "
              f"({n1 / max(n, 1):.3f})")
    print("\ncalibration on fresh data (locked p bands):")
    for band in sorted(bands):
        n0, n1 = bands[band]
        print(f"  p~{band / 10:.1f}-{band / 10 + 0.1:.1f}: "
              f"{n1:5d}/{n0 + n1:6d} ({n1 / (n0 + n1):.3f})")


if __name__ == "__main__":
    main()
