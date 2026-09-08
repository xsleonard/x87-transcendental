#!/usr/bin/env python3
"""Search a compact integer threshold law for the h1135 carry surface."""

from __future__ import annotations

import argparse
import csv
import itertools
from collections import defaultdict
from pathlib import Path


def state(row: dict[str, str]) -> int | None:
    theta = int(row["theta"])
    allowed = {int(value) for value in row["target_allowed"].split(",")}
    physical = allowed & ({-1, 0} if theta >= 0 else {0, 1})
    if len(physical) == 2:
        return None
    if not physical:
        raise RuntimeError(f"no physical endpoint for {row['op']}")
    return int(next(iter(physical)) != 0)


def best_intercept(rows, low_fires: bool):
    values = defaultdict(lambda: [0, 0])
    for z, label in rows:
        values[z][label] += 1
    ordered = sorted(values.items())
    total = [sum(count[label] for _, count in ordered) for label in (0, 1)]
    below = [0, 0]
    candidates = []
    for index in range(len(ordered) + 1):
        # z < F at split index.  For positive/tie theta that side fires;
        # for negative theta the upper side fires.
        errors = (
            below[0] + total[1] - below[1]
            if low_fires
            else below[1] + total[0] - below[0]
        )
        left = ordered[index - 1][0] if index else None
        right = ordered[index][0] if index < len(ordered) else None
        candidates.append((errors, index, left, right))
        if index < len(ordered):
            below[0] += ordered[index][1][0]
            below[1] += ordered[index][1][1]
    return min(candidates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--radius", type=int, default=4)
    parser.add_argument("--group-theta", action="store_true")
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    groups = defaultdict(list)
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            label = state(row)
            if label is None:
                continue
            theta = int(row["theta"])
            outer = (row["ce"], row["s4"], row["side"], row["dist"], row["rsh"])
            if args.group_theta:
                outer += (row["theta"],)
            sign_class = "nonnegative" if theta >= 0 else "negative"
            groups[(sign_class, outer)].append({
                "q": int(row["mreg_signed"]) // (1 << 66),
                "payload": int(row["payload"]),
                "theta": theta,
                "b1": int(row["b1"]),
                "b2": int(row["b2"]),
                "label": label,
            })

    coefficients = range(-args.radius, args.radius + 1)
    scores = []
    local_best = {}
    for a, b, c, d in itertools.product(coefficients, repeat=4):
        total = 0
        intercepts = {}
        for (sign_class, outer), rows in groups.items():
            transformed = [
                (
                    row["q"] - a * row["payload"] - b * row["theta"]
                    - c * row["b1"] - d * row["b2"],
                    row["label"],
                )
                for row in rows
            ]
            result = best_intercept(transformed, sign_class == "nonnegative")
            total += result[0]
            intercepts[(sign_class, outer)] = result
            local = (result[0], abs(a) + abs(b) + abs(c) + abs(d),
                     (a, b, c, d), result)
            if (sign_class, outer) not in local_best \
                    or local[:3] < local_best[(sign_class, outer)][:3]:
                local_best[(sign_class, outer)] = local
        scores.append((total, abs(a) + abs(b) + abs(c) + abs(d),
                       (a, b, c, d), intercepts))
    scores.sort(key=lambda item: item[:3])

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"groups\t{len(groups)}\n")
        target.write("errors\tcomplexity\ta_payload\tb_theta\tc_b1\td_b2\n")
        for errors, complexity, coeff, _ in scores[:64]:
            target.write(
                f"{errors}\t{complexity}\t{coeff[0]}\t{coeff[1]}\t"
                f"{coeff[2]}\t{coeff[3]}\n"
            )
        best = scores[0]
        target.write("\n[best-intercepts]\n")
        target.write("sign\touter\terrors\tleft_z\tright_z\n")
        for key, result in sorted(best[3].items()):
            target.write(
                f"{key[0]}\t{'/'.join(key[1])}\t{result[0]}\t"
                f"{'' if result[2] is None else result[2]}\t"
                f"{'' if result[3] is None else result[3]}\n"
            )
        target.write("\n[per-group-best]\n")
        target.write("sign\touter\terrors\tcomplexity\ta\tb\tc\td\t"
                     "left_z\tright_z\n")
        for key, result in sorted(local_best.items()):
            coeff = result[2]
            boundary = result[3]
            target.write(
                f"{key[0]}\t{'/'.join(key[1])}\t{result[0]}\t{result[1]}\t"
                f"{coeff[0]}\t{coeff[1]}\t{coeff[2]}\t{coeff[3]}\t"
                f"{'' if boundary[2] is None else boundary[2]}\t"
                f"{'' if boundary[3] is None else boundary[3]}\n"
            )
    print(
        f"groups={len(groups)} best_errors={scores[0][0]} "
        f"coefficients={scores[0][2]}"
    )


if __name__ == "__main__":
    main()
