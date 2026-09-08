#!/usr/bin/env python3
"""Localize upper FCOS residuals with named-producer response tests.

This is a software-only causal experiment over previously captured four-mode
hardware truth.  It perturbs one named materialized producer at a time and
records which operands become exact in every architectural rounding mode.
The perturbations are diagnostics, not a proposed correction rule.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import defaultdict
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")
PRODUCERS = (
    "red", "mag", "sq", "f4", "odd", "even", "left", "right",
    "payload", "umag",
)
UPSTREAM_ANCHORS = {
    "3ffc be6000000688f849",
    "3ffc fb900000030c1fc9",
    "3ffc ffffff80075216a0",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_truth(path: Path) -> tuple[dict[tuple[str, str], str], list[str]]:
    truth: dict[tuple[str, str], str] = {}
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            operand = row["op"].lower()
            key = (row["mode"], operand)
            result = row["hw"].lower()
            if key in truth and truth[key] != result:
                raise RuntimeError(f"conflicting truth for {key}")
            truth[key] = result
    operands = sorted({operand for _, operand in truth})
    for operand in operands:
        missing = [mode for mode in MODES if (mode, operand) not in truth]
        if missing:
            raise RuntimeError(f"missing modes for {operand}: {missing}")
    missing_anchors = sorted(UPSTREAM_ANCHORS - set(operands))
    if missing_anchors:
        raise RuntimeError(f"missing upstream anchors: {missing_anchors}")
    return truth, operands


def run(model: Path, mode: str, operands: list[str], producer: str,
        delta: int) -> list[str]:
    command = [
        str(model), "--batch", f"--rc={mode}", "--fcos-standalone",
        f"--perturb={producer}:{delta}",
    ]
    process = subprocess.run(
        command, input="\n".join(operands) + "\n", text=True,
        capture_output=True, check=True,
    )
    results = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            results.append(fields[1].lower() + ":" + fields[2].lower())
    if len(results) != len(operands):
        raise RuntimeError(
            f"output count {len(results)} != {len(operands)} for "
            f"{producer}:{delta}/{mode}"
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("truth", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    truth, operands = read_truth(args.truth)
    variants: dict[tuple[str, int], dict[str, int]] = {}
    matches: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for producer in PRODUCERS:
        for delta in range(-4, 5):
            legs = defaultdict(int)
            for mode in MODES:
                results = run(args.model, mode, operands, producer, delta)
                for operand, result in zip(operands, results):
                    legs[operand] += result == truth[mode, operand]
            exact = {operand for operand, count in legs.items()
                     if count == len(MODES)}
            anchors = exact & UPSTREAM_ANCHORS
            variants[producer, delta] = {
                "exact_operands": len(exact),
                "exact_legs": sum(legs.values()),
                "exact_anchors": len(anchors),
                "anchor_legs": sum(legs[operand]
                                   for operand in UPSTREAM_ANCHORS),
            }
            for operand in exact:
                matches[operand].append((producer, delta))
            print(
                f"{producer}:{delta:+d} exact={len(exact)}/{len(operands)} "
                f"anchors={len(anchors)}/{len(UPSTREAM_ANCHORS)}",
                flush=True,
            )

    ranking = sorted(
        variants.items(),
        key=lambda item: (
            -item[1]["exact_anchors"], -item[1]["anchor_legs"],
            -item[1]["exact_operands"], -item[1]["exact_legs"],
            item[0][0], abs(item[0][1]), item[0][1],
        ),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"truth_sha256\t{digest(args.truth)}\n")
        target.write(f"operands\t{len(operands)}\n")
        target.write(f"legs\t{len(operands) * len(MODES)}\n")
        target.write("\n[variant ranking]\n")
        target.write(
            "exact_anchors\tanchor_legs\texact_operands\texact_legs\t"
            "producer\tdelta\n"
        )
        for (producer, delta), score in ranking:
            target.write(
                f"{score['exact_anchors']}\t{score['anchor_legs']}\t"
                f"{score['exact_operands']}\t{score['exact_legs']}\t"
                f"{producer}\t{delta}\n"
            )
        target.write("\n[all-mode exact variants per upstream anchor]\n")
        target.write("op\tcount\tvariants\n")
        for operand in sorted(UPSTREAM_ANCHORS):
            entries = sorted(matches[operand],
                             key=lambda item: (item[0], abs(item[1]), item[1]))
            rendered = ",".join(f"{name}:{delta:+d}"
                                for name, delta in entries)
            target.write(f"{operand}\t{len(entries)}\t{rendered or '-'}\n")

    print(f"wrote {args.report} best={ranking[0]}", flush=True)


if __name__ == "__main__":
    main()
