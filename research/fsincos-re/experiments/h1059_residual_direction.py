#!/usr/bin/env python3
"""h1059: classify every residual closed-selector miss by endpoint action."""

import csv
import os
from collections import Counter, defaultdict

import h1039_top0_union_block_phase as runner
import h1042_active_union_response as active


CURRENT = os.environ.get("H1059_CURRENT", "/tmp/x87-r96-allclosed-p0")
FORCES = {number: f"/tmp/x87-r96-force{number}" for number in range(1, 9)}


def main():
    with open(runner.DATA) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    groups = defaultdict(list)
    for row in rows:
        groups[row["insn"], row["mode"]].append(row)

    residual = defaultdict(list)
    leg_counts = Counter()
    for (insn, mode), sample in sorted(groups.items()):
        operands = [row["op"] for row in sample]
        base, _ = runner.run(runner.BASE, insn, mode, operands)
        current, _ = runner.run(CURRENT, insn, mode, operands)
        forced = {number: runner.run(path, insn, mode, operands)[0]
                  for number, path in FORCES.items()}
        for index, (datum, before, after) in enumerate(
                zip(sample, base, current)):
            hardware = runner.norm(datum["hw"])
            if after == hardware:
                continue
            hits = tuple(number for number, output in forced.items()
                         if output[index] == hardware
                         and output[index] != before)
            if len(hits) != 1:
                raise AssertionError((insn, mode, datum["op"], hits))
            force = hits[0]
            residual[insn, datum["op"]].append((mode, force))
            leg_counts[insn, mode, force] += 1

    fields = (
        "insn", "op", "force", "modes", "legs", "force_sum", "sum8",
        "low3", "dist", "s4", "side", "b1", "b2", "mreg", "sqlow",
        "pcut", "pdown", "pup", "pbelow", "active", "payload",
        "payload_pre", "scale", "cut", "ce", "svalue", "bvalue",
        "qpost", "qpre", "qright", "qleft", "qf4", "qsq", "mul",
        "lf", "f4k", "rf", "mag",
    )
    output = []
    for insn in ("cos", "sin"):
        chosen = sorted((op, legs) for (which, op), legs in residual.items()
                        if which == insn)
        if not chosen:
            continue
        _, dump = runner.run(runner.BASE, insn, "rn",
                             [op for op, _ in chosen], dump=True)
        records = active.response_score.parse_dumps(dump)
        for (op, legs), record in zip(chosen, records):
            forces = {force for _, force in legs}
            if len(forces) != 1:
                raise AssertionError((insn, op, legs))
            row = active.feature_record(record)
            row.update(insn=insn, op=op, force=next(iter(forces)),
                       modes=",".join(sorted(mode for mode, _ in legs)),
                       legs=len(legs))
            output.append(row)

    with open("/tmp/h1059_remaining.tsv", "w") as target:
        target.write("\t".join(fields) + "\n")
        for row in output:
            target.write("\t".join(str(row[field]) for field in fields)
                         + "\n")
    print("legs", dict(leg_counts))
    print("operands", Counter(row["force"] for row in output))


if __name__ == "__main__":
    main()
