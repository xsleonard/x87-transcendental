#!/usr/bin/env python3
"""Causally localize the apparent high-q final-Horner FADD responses.

The R1281-style factor perturbation and a different terminal subtractor carry
can produce the same architectural result.  This audit compares each frozen
hardware-labelled leg with both factor recurrences at both exact terminal
carry endpoints.  Fresh labels are used only in the modes actually captured;
the cached positive control may additionally supply its complete all-mode
truth from an immutable score file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1210_stagea_residual_reframe import run


MODES = ("rn", "rd", "ru", "rz")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def normalize_operand(value: str) -> str:
    fields = value.lower().split()
    if len(fields) != 2:
        raise RuntimeError(f"bad operand {value!r}")
    return " ".join(fields)


def load_fresh_labels(paths: list[Path]) -> dict[tuple[str, str], dict[str, str]]:
    labels: dict[tuple[str, str], dict[str, str]] = {}
    for path in paths:
        with path.open(newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                mode = row["mode"].lower()
                operand = normalize_operand(row["op"])
                key = mode, operand
                hardware = row["hardware"].lower()
                record = {
                    "mode": mode,
                    "op": operand,
                    "hardware": hardware,
                    "source": path.name,
                    "capture_scope": "fresh_captured_leg",
                }
                previous = labels.setdefault(key, record)
                if previous["hardware"] != hardware:
                    raise RuntimeError(f"hardware conflict for {key}")
    return labels


def add_cached_operand(
        labels: dict[tuple[str, str], dict[str, str]], path: Path,
        operand: str) -> None:
    found = set()
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if normalize_operand(row["op"]) != operand:
                continue
            mode = row["mode"].lower()
            key = mode, operand
            hardware = row["hw"].lower()
            record = {
                "mode": mode,
                "op": operand,
                "hardware": hardware,
                "source": path.name,
                "capture_scope": "cached_all_mode",
            }
            previous = labels.setdefault(key, record)
            if previous["hardware"] != hardware:
                raise RuntimeError(f"hardware conflict for {key}")
            found.add(mode)
    if found != set(MODES):
        raise RuntimeError(
            f"cached truth for {operand} has modes {sorted(found)}, "
            f"expected {list(MODES)}"
        )


def model_outputs(
        model: Path, operands_by_mode: dict[str, list[str]]
        ) -> dict[tuple[str, str], str]:
    outputs = {}
    for mode in MODES:
        operands = operands_by_mode[mode]
        if not operands:
            continue
        values, _ = run(model, mode, operands)
        outputs.update({
            (mode, operand): value
            for operand, value in zip(operands, values)
        })
    return outputs


def rendered_carries(values: set[int]) -> str:
    return ",".join(map(str, sorted(values))) or "-"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh-label", action="append", type=Path,
                        default=[])
    parser.add_argument("--cached-score", type=Path, required=True)
    parser.add_argument("--cached-operand", required=True)
    parser.add_argument("--predecessor", type=Path, required=True)
    parser.add_argument("--predecessor-carry0", type=Path, required=True)
    parser.add_argument("--predecessor-carry1", type=Path, required=True)
    parser.add_argument("--wide", type=Path, required=True)
    parser.add_argument("--wide-carry0", type=Path, required=True)
    parser.add_argument("--wide-carry1", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--legs", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.report, args.legs):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    labels = load_fresh_labels(args.fresh_label)
    cached_operand = normalize_operand(args.cached_operand)
    add_cached_operand(labels, args.cached_score, cached_operand)
    operands_by_mode = {
        mode: sorted(op for row_mode, op in labels if row_mode == mode)
        for mode in MODES
    }
    model_paths = {
        "predecessor": args.predecessor,
        "predecessor_carry0": args.predecessor_carry0,
        "predecessor_carry1": args.predecessor_carry1,
        "wide": args.wide,
        "wide_carry0": args.wide_carry0,
        "wide_carry1": args.wide_carry1,
    }
    models = {
        name: model_outputs(path, operands_by_mode)
        for name, path in model_paths.items()
    }

    counts = Counter()
    operand_legs: dict[str, list[dict[str, object]]] = defaultdict(list)
    diagnostics = []
    for key in sorted(labels, key=lambda item: (item[1], MODES.index(item[0]))):
        label = labels[key]
        truth = label["hardware"]
        predecessor_carries = {
            carry for carry in (0, 1)
            if models[f"predecessor_carry{carry}"][key] == truth
        }
        wide_carries = {
            carry for carry in (0, 1)
            if models[f"wide_carry{carry}"][key] == truth
        }
        predecessor_match = models["predecessor"][key] == truth
        wide_match = models["wide"][key] == truth
        if predecessor_carries:
            causal_class = "predecessor_factor_compatible"
        elif wide_carries:
            causal_class = "wide_factor_required"
        else:
            causal_class = "unrepresented_by_factor_or_terminal_carry"
        counts[f"leg.{causal_class}"] += 1
        counts[f"leg.predecessor_natural.{int(predecessor_match)}"] += 1
        counts[f"leg.wide_natural.{int(wide_match)}"] += 1
        diagnostic = {
            **label,
            "predecessor": models["predecessor"][key],
            "predecessor_carry0": models["predecessor_carry0"][key],
            "predecessor_carry1": models["predecessor_carry1"][key],
            "predecessor_allowed_carries": rendered_carries(predecessor_carries),
            "wide": models["wide"][key],
            "wide_carry0": models["wide_carry0"][key],
            "wide_carry1": models["wide_carry1"][key],
            "wide_allowed_carries": rendered_carries(wide_carries),
            "causal_class": causal_class,
        }
        diagnostics.append(diagnostic)
        operand_legs[key[1]].append({
            "mode": key[0],
            "predecessor_carries": predecessor_carries,
            "wide_carries": wide_carries,
        })

    operand_diagnostics = []
    for operand, rows in sorted(operand_legs.items()):
        predecessor_intersection = set.intersection(*(
            row["predecessor_carries"] for row in rows
        ))
        wide_intersection = set.intersection(*(
            row["wide_carries"] for row in rows
        ))
        captured_modes = [str(row["mode"]) for row in rows]
        if predecessor_intersection:
            causal_class = "predecessor_factor_compatible"
        elif wide_intersection:
            causal_class = "wide_factor_required"
        else:
            causal_class = "no_fixed_carry_explains_captured_modes"
        counts[f"operand.{causal_class}"] += 1
        operand_diagnostics.append({
            "op": operand,
            "modes": ",".join(captured_modes),
            "predecessor_allowed_fixed_carries": rendered_carries(
                predecessor_intersection),
            "wide_allowed_fixed_carries": rendered_carries(wide_intersection),
            "causal_class": causal_class,
        })

    args.legs.parent.mkdir(parents=True, exist_ok=True)
    leg_columns = tuple(diagnostics[0])
    with args.legs.open("x", newline="") as target:
        writer = csv.DictWriter(target, leg_columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(diagnostics)
    with args.report.open("x") as target:
        for path in args.fresh_label:
            target.write(f"fresh_labels_sha256.{path.name}\t{digest(path)}\n")
        target.write(
            f"cached_score_sha256.{args.cached_score.name}\t"
            f"{digest(args.cached_score)}\n"
        )
        for name, path in model_paths.items():
            target.write(f"model_sha256.{name}\t{digest(path)}\n")
        target.write("hardware_policy\tfrozen_labels_only_no_x87_execution\n")
        target.write(f"labelled_legs\t{len(diagnostics)}\n")
        target.write(f"unique_operands\t{len(operand_diagnostics)}\n")
        target.write(f"legs_sha256\t{digest(args.legs)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[operand fixed-carry compatibility]\n")
        target.write(
            "op\tmodes\tpredecessor_allowed_fixed_carries\t"
            "wide_allowed_fixed_carries\tcausal_class\n"
        )
        for row in operand_diagnostics:
            target.write("\t".join(str(row[name]) for name in (
                "op", "modes", "predecessor_allowed_fixed_carries",
                "wide_allowed_fixed_carries", "causal_class",
            )) + "\n")

    print(
        f"wrote {args.report}: legs={len(diagnostics)} "
        f"operands={len(operand_diagnostics)} "
        f"wide_required={counts['operand.wide_factor_required']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
