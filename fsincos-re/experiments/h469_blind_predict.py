#!/usr/bin/env python3
"""h469: hardware-blind prediction for the fresh batch.

Discipline step for the (theta, rs low nibble, payload, rud) structure
found in h468: predictions for every fresh selected row are computed
and WRITTEN TO DISK from model-side state only (this script never reads
the fresh hardware files); scoring against the captures happens in a
separate later step (h469_blind_score.py) after predictions are locked.

The predictor is the h468 lookup trained on ALL 19,962 labeled rows
(no split — the fresh batch is the held-out set), with Laplace
smoothing toward the training prior.  Output: h469_package/
predictions.tsv with columns se, sig, theta, key..., p_fire, and a
confidence class: FIRE (p >= 0.8), CLEAN (p <= 0.02), ABSTAIN.

Run from /tmp/stageA (expects h464_package/labels.tsv and
h469_package/selected.tsv; must be run BEFORE fetching h469 hw files).
"""
import os
from collections import defaultdict

from h437_gate_extraction import parse_trace_line

TRAIN_PKG = "h464_package"
PKG = "h469_package"
KEY_FEATURES = ("theta", "rs_nib0", "payload", "rud")


def train_table():
    table = defaultdict(lambda: [0, 0])
    n = f = 0
    with open(f"{TRAIN_PKG}/labels.tsv") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            r = dict(zip(header, line.rstrip("\n").split("\t")))
            key = (int(r["theta"]), int(r["rs_low16"]) & 0xF,
                   int(r["payload"]), int(r["rud"]))
            table[key][int(r["fire_pre"])] += 1
            n += 1
            f += int(r["fire_pre"])
    return table, f / n


def main():
    table, prior = train_table()
    print(f"trained on labels.tsv, prior {prior:.4f}, "
          f"{len(table)} lookup keys")
    counts = {"FIRE": 0, "CLEAN": 0, "ABSTAIN": 0}
    os.makedirs(PKG, exist_ok=True)
    with open(f"{PKG}/selected.tsv") as fin, \
            open(f"{PKG}/predictions.tsv", "w") as fout:
        fout.write("se\tsig\ttheta\trs_nib0\tpayload\trud\tp_fire\tcall\n")
        for line in fin:
            se, sig, theta, trace = line.rstrip("\n").split("\t")
            fields = parse_trace_line(trace)
            if fields["active"] != "1" or fields["lsign"] != "1" \
                    or fields["rsign"] != "0":
                continue
            key = (int(theta), int(fields["rs"], 16) & 0xF,
                   int(fields["payload"]), int(fields["rud"]))
            n0, n1 = table.get(key, [0, 0])
            p = (n1 + 5 * prior) / (n0 + n1 + 5)
            call = "FIRE" if p >= 0.8 else ("CLEAN" if p <= 0.02
                                            else "ABSTAIN")
            counts[call] += 1
            fout.write(f"{se}\t{sig}\t{theta}\t{key[1]}\t{key[2]}\t"
                       f"{key[3]}\t{p:.4f}\t{call}\n")
    print(f"predictions locked: {counts}")


if __name__ == "__main__":
    main()
