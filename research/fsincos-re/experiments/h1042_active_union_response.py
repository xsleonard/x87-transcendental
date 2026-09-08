#!/usr/bin/env python3
"""h1042: build exact union response sets for TOP/act1 and LOW/act1.

Run the absolute-one-quantum force probes against every h989 hardware leg,
retain operands with a consistent FIX or BREAK label, and reconstruct the
same terminal/R60 coordinates used for the closed inactive-upper law.
"""

import csv
from collections import Counter, defaultdict

import h1035_top0_response_score as response_score
import h1039_top0_union_block_phase as runner


CONFIG = {
    "top1": ("/tmp/x87-r96-force2", 1),
    "low1": ("/tmp/x87-r96-force3", 0),
}


def normalized_residue(product):
    shift = product.bit_length() - 67
    if shift <= 0:
        return 0
    return ((product & ((1 << shift) - 1)) << 66) >> shift


def terminal_residue(record, payload):
    left, right = record["left"], record["right"]
    scale = min(left[1], right[1], left[1] - 8 if payload else left[1])
    value = ((-1 if left[0] else 1)
             * (left[2] << (left[1] - scale)))
    value += ((-1 if right[0] else 1)
              * (right[2] << (right[1] - scale)))
    if payload:
        payload_sign = left[0] ^ (payload < 0)
        value += ((-1 if payload_sign else 1)
                  * (abs(payload) << (left[1] - 8 - scale)))
    magnitude = abs(value)
    cut = magnitude.bit_length() - 67
    residue = magnitude & ((1 << cut) - 1) if cut > 0 else 0
    return (residue << 66) >> cut if cut > 0 else 0


def feature_record(record):
    row = response_score.reconstructed(record)
    left, right = record["left"], record["right"]
    payload_pre = int(record["payload"])
    payload = int(record.get("pay2", record["payload"]))
    scale = min(left[1], right[1], left[1] - 8 if payload else left[1])
    s_value = left[2] << (left[1] - scale)
    if payload:
        s_value += payload << (left[1] - 8 - scale)
    b_value = right[2] << (right[1] - scale)
    magnitude = s_value - b_value
    cut = magnitude.bit_length() - 67
    propagate = ~(s_value ^ b_value)
    pup = 0
    while pup < 64 and ((propagate >> (cut + pup)) & 1):
        pup += 1
    row.update(
        active=int(record["active"]), payload=payload,
        payload_pre=payload_pre,
        scale=scale, cut=cut, ce=scale + cut, pup=pup,
        svalue=s_value, bvalue=b_value,
        qpost=terminal_residue(record, payload),
        qpre=terminal_residue(record, payload_pre),
        qright=normalized_residue(record["f4"][2] * record["rf"][2]),
        qleft=normalized_residue(record["mul"][2] * record["lf"][2]),
        qf4=normalized_residue(record["mul"][2] * record["mul"][2]),
        qsq=normalized_residue(record["mag"][2] * record["mag"][2]),
        force_sum=(int(record["d60"], 16) >> 52) + int(record["low3"]),
        mul=record["mul"][2], lf=record["lf"][2],
        f4k=record["f4"][2], rf=record["rf"][2], mag=record["mag"][2],
    )
    return row


def collect(candidate):
    with open(runner.DATA) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    groups = defaultdict(list)
    for row in rows:
        groups[(row["insn"], row["mode"])].append(row)
    labels = defaultdict(set)
    for (insn, mode), sample in sorted(groups.items()):
        operands = [row["op"] for row in sample]
        before, _ = runner.run(runner.BASE, insn, mode, operands)
        after, _ = runner.run(candidate, insn, mode, operands)
        for datum, baseline, changed in zip(sample, before, after):
            if baseline == changed:
                continue
            hardware = runner.norm(datum["hw"])
            if changed == hardware and baseline != hardware:
                label = "FIX"
            elif baseline == hardware and changed != hardware:
                label = "BREAK"
            else:
                label = "OTHER"
            labels[(insn, datum["op"])].add(label)
    return labels


def main():
    for family, (candidate, direction) in CONFIG.items():
        labels = collect(candidate)
        print("\n", family, "label sets",
              Counter(tuple(sorted(value)) for value in labels.values()))
        featured = []
        for insn in ("cos", "sin"):
            chosen = sorted((operand, next(iter(value)))
                            for (which, operand), value in labels.items()
                            if which == insn and len(value) == 1
                            and value <= {"FIX", "BREAK"})
            if not chosen:
                continue
            operands = [operand for operand, _ in chosen]
            _, dump = runner.run(runner.BASE, insn, "rn", operands, dump=True)
            records = response_score.parse_dumps(dump)
            for (operand, label), record in zip(chosen, records):
                row = feature_record(record)
                row.update(label=label, insn=insn, op=operand)
                featured.append(row)

        print(" all", Counter(row["label"] for row in featured))
        eligible = [row for row in featured
                    if row["active"] == 1 and row["pcut"] == direction]
        print(" direction eligible", Counter(row["label"] for row in eligible))
        print(" pdown", Counter((row["label"], row["pdown"])
                                for row in eligible))
        print(" structure", Counter((row["label"], row["sum8"], row["s4"],
                                     row["side"], row["dist"])
                                    for row in eligible))

        fields = (
            "label", "insn", "op", "sum8", "low3", "dist", "s4", "side",
            "b1", "b2", "mreg", "sqlow", "pcut", "pdown", "pup",
            "pbelow",
            "active", "payload", "payload_pre", "scale", "cut", "ce",
            "force_sum",
            "svalue", "bvalue",
            "qpost", "qpre", "qright", "qleft",
            "qf4", "qsq", "mul", "lf", "f4k", "rf", "mag",
        )
        with open(f"/tmp/h1042_{family}_union.tsv", "w") as out:
            out.write("\t".join(fields) + "\n")
            for row in eligible:
                out.write("\t".join(str(row[field]) for field in fields) + "\n")


if __name__ == "__main__":
    main()
