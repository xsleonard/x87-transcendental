#!/usr/bin/env python3
"""h1056: exact response populations for the three remaining R96 arms."""

import csv
from collections import Counter, defaultdict

import h1035_top0_response_score as response_score
import h1039_top0_union_block_phase as runner
import h1042_active_union_response as active


CONFIG = {
    "top0_p0": ("/tmp/x87-r96-force1", 0, 1, 0),
    "top0_p1": ("/tmp/x87-r96-force1", 0, 1, 1),
    "top1_p0": ("/tmp/x87-r96-force2", 1, 1, 0),
    "low1_p1": ("/tmp/x87-r96-force3", 1, 0, 1),
    "top0_down_p0": ("/tmp/x87-r96-force4", 0, 1, 0),
    "top0_down_p1": ("/tmp/x87-r96-force4", 0, 1, 1),
    "top1_down_p0": ("/tmp/x87-r96-force5", 1, 1, 0),
    "top1_down_p1": ("/tmp/x87-r96-force5", 1, 1, 1),
    "low1_up_p0": ("/tmp/x87-r96-force6", 1, 0, 0),
    "low1_up_p1": ("/tmp/x87-r96-force6", 1, 0, 1),
}


def labels(candidate):
    with open(runner.DATA) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    groups = defaultdict(list)
    for row in rows:
        groups[row["insn"], row["mode"]].append(row)
    result = defaultdict(set)
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
            result[insn, datum["op"]].add(label)
    return result


def main():
    fields = (
        "label", "insn", "op", "force_sum", "sum8", "low3", "dist",
        "s4", "side", "b1", "b2", "mreg", "sqlow", "pcut", "pdown",
        "pup", "pbelow", "active", "payload", "payload_pre", "scale",
        "cut", "ce", "svalue", "bvalue", "qpost", "qpre", "qright",
        "qleft", "qf4", "qsq", "mul", "lf", "f4k", "rf", "mag",
    )
    for family, (candidate, want_active, want_top, want_pcut) in CONFIG.items():
        response = labels(candidate)
        featured = []
        for insn in ("cos", "sin"):
            chosen = sorted((operand, next(iter(value)))
                            for (which, operand), value in response.items()
                            if which == insn and len(value) == 1
                            and value <= {"FIX", "BREAK"})
            if not chosen:
                continue
            _, dump = runner.run(runner.BASE, insn, "rn",
                                 [operand for operand, _ in chosen],
                                 dump=True)
            records = response_score.parse_dumps(dump)
            for (operand, label), record in zip(chosen, records):
                row = active.feature_record(record)
                row.update(label=label, insn=insn, op=operand)
                if (row["active"] == want_active
                        and (row["force_sum"] >= 128) == bool(want_top)
                        and row["pcut"] == want_pcut):
                    featured.append(row)
        with open("/tmp/h1056_%s.tsv" % family, "w") as out:
            out.write("\t".join(fields) + "\n")
            for row in featured:
                out.write("\t".join(str(row[field]) for field in fields)
                          + "\n")
        print(family, len(featured),
              dict(Counter(row["label"] for row in featured)),
              "qpost11", dict(Counter(
                  (row["label"], row["qpost"] >> 55)
                  for row in featured)))


if __name__ == "__main__":
    main()
