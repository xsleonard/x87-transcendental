#!/usr/bin/env python3
"""h1061: retain rounding-mode labels for mixed endpoint responses."""

import csv
from collections import Counter, defaultdict

import h1039_top0_union_block_phase as runner
import h1042_active_union_response as active


CONFIG = {
    "low_down": "/tmp/x87-r96-force3",
    "low_up": "/tmp/x87-r96-force6",
    "top0_up": "/tmp/x87-r96-force1",
    "top0_down": "/tmp/x87-r96-force4",
}
MODE_CODE = {"rn": 0, "rd": 1, "ru": 2, "rz": 3}


def main():
    with open(runner.DATA) as source:
        union = list(csv.DictReader(source, delimiter="\t"))
    groups = defaultdict(list)
    for row in union:
        groups[row["insn"], row["mode"]].append(row)

    fields = (
        "label", "insn", "op", "mode", "rc", "force_sum", "sum8",
        "low3", "dist", "s4", "side", "b1", "b2", "mreg", "sqlow",
        "pcut", "pdown", "pup", "pbelow", "active", "payload",
        "payload_pre", "scale", "cut", "ce", "svalue", "bvalue",
        "qpost", "qpre", "qright", "qleft", "qf4", "qsq", "mul",
        "lf", "f4k", "rf", "mag",
    )
    for family, candidate in CONFIG.items():
        legs = []
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
                legs.append((insn, mode, datum["op"], label))

        feature_by_op = {}
        by_insn = defaultdict(set)
        for insn, _, op, _ in legs:
            by_insn[insn].add(op)
        for insn, operands in by_insn.items():
            ordered = sorted(operands)
            _, dump = runner.run(runner.BASE, insn, "rn", ordered, dump=True)
            records = active.response_score.parse_dumps(dump)
            for op, record in zip(ordered, records):
                feature_by_op[insn, op] = active.feature_record(record)

        rows = []
        for insn, mode, op, label in legs:
            row = dict(feature_by_op[insn, op])
            row.update(label=label, insn=insn, op=op,
                       mode=mode, rc=MODE_CODE[mode])
            rows.append(row)
        with open(f"/tmp/h1061_{family}.tsv", "w") as target:
            target.write("\t".join(fields) + "\n")
            for row in rows:
                target.write("\t".join(str(row[field]) for field in fields)
                             + "\n")
        print(family, len(rows), dict(Counter(row["label"] for row in rows)))


if __name__ == "__main__":
    main()
