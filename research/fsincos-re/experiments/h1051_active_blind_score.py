#!/usr/bin/env python3
"""h1051: reconstruct h1050 and score the exact monotone cell laws."""

import csv
from collections import Counter, defaultdict

import h1042_active_union_response as active
import h1039_top0_union_block_phase as runner


ONE = 1 << 66


def decorate(row):
    row = dict(row)
    row["mul65"] = (row["mul"] >> 65) & 1
    row["qpost55"] = (row["qpost"] >> 55) & 1
    row["qpost56"] = (row["qpost"] >> 56) & 1
    row["qpost57"] = (row["qpost"] >> 57) & 1
    row["qf441"] = (row["qf4"] >> 41) & 1
    return row


def load_training(family):
    with open(f"/tmp/h1042_{family}_union.tsv") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    for row in rows:
        for key in row.keys() - {"label", "insn", "op"}:
            row[key] = int(row[key])
    return [decorate(row) for row in rows]


def blind_rows(family, path="/tmp/h1050_active_force_blind.tsv"):
    with open(path) as source:
        raw = [row for row in csv.DictReader(source, delimiter="\t")
               if row["family"] == family]
    labels = defaultdict(set)
    for row in raw:
        labels[row["insn"], row["op"]].add(row["outcome"])
    result = []
    for insn in ("cos", "sin"):
        chosen = sorted((op, next(iter(value)))
                        for (which, op), value in labels.items()
                        if which == insn and len(value) == 1)
        if not chosen:
            continue
        _, dump = runner.run(
            runner.BASE, insn, "rn", [op for op, _ in chosen], dump=True)
        records = active.response_score.parse_dumps(dump)
        for (op, label), record in zip(chosen, records):
            row = decorate(active.feature_record(record))
            row.update(op=op, insn=insn, label=label)
            result.append(row)
    return result


def fields(family):
    common = ("sum8", "s4", "side", "dist", "low3", "b1", "b2",
              "pdown")
    if family == "top1":
        return common + ("mul65", "qpost56", "qpost55")
    return common + ("qf441", "qpost57", "qpost56")


def learn(family, rows):
    groups = defaultdict(list)
    key_fields = fields(family)
    for row in rows:
        groups[tuple(row[field] for field in key_fields)].append(row)
    rule = {}
    for key, cell in groups.items():
        fixes = [row["mreg"] for row in cell if row["label"] == "FIX"]
        breaks = [row["mreg"] for row in cell if row["label"] == "BREAK"]
        if not fixes:
            continue
        if not breaks:
            rule[key] = "always", None
            continue
        if family == "top1":
            lower, upper = max(breaks), min(fixes)
        else:
            lower, upper = max(fixes), min(breaks)
        thresholds = [value for value in range(lower // ONE - 1,
                                                upper // ONE + 2)
                      if lower < value * ONE <= upper]
        if not thresholds:
            raise AssertionError((family, key, lower, upper))
        # Prefer the phase nearest zero; ties prefer the lower magnitude.
        threshold = min(thresholds, key=lambda value: (abs(value), value))
        rule[key] = "threshold", threshold
    return rule


def fires(family, rule, row):
    qpost9 = row["qpost"] * 512 // ONE
    if family == "top1" and qpost9 < 506:
        return False
    if family == "low1" and qpost9 > 6:
        return False
    key = tuple(row[field] for field in fields(family))
    kind, threshold = rule.get(key, ("never", None))
    if kind == "always":
        return True
    if kind == "never":
        return False
    return (row["mreg"] >= threshold * ONE if family == "top1"
            else row["mreg"] < threshold * ONE)


def main():
    for family in ("top1", "low1"):
        training = load_training(family)
        rule = learn(family, training)
        print("\n", family, "rule cells", len(rule),
              "training", Counter((row["label"], fires(family, rule, row))
                                  for row in training))
        for bank, path in (
                ("wide", "/tmp/h1050_active_force_blind.tsv"),
                ("annulus", "/tmp/h1050_active_force_annulus.tsv"),
                ("micro", "/tmp/h1050_active_force_micro.tsv")):
            blind = blind_rows(family, path)
            print(bank, Counter((row["label"], fires(family, rule, row))
                                for row in blind),
                  "eligible", Counter(
                      (row["label"], fires(family, rule, row))
                      for row in blind
                      if row["pcut"]
                      == (1 if family == "top1" else 0)))
            fired = [row for row in blind if fires(family, rule, row)]
            for row in fired[:30]:
                print(" FIRE", bank, row["insn"], row["op"],
                      tuple(row[field] for field in fields(family)),
                      row["mreg"] / ONE,
                      "qpost512", row["qpost"] * 512 // ONE)


if __name__ == "__main__":
    main()
