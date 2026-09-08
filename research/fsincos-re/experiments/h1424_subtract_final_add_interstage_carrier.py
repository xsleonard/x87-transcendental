#!/usr/bin/env python3
"""Audit the subtract-to-final-add interstage carrier.

The cosine model ends with two distinct arithmetic operations:

    correction = _FSUB(terminal_left, terminal_right)
    result = FINAL_ADD(+1, correction)

h1415 tested documented FAMUBUS encodings at the first operation, but scored
only the resulting correction endpoint.  This pass retains each resulting bus
through a separately modeled final FADD and architectural rounding.  It also
tests the incumbent 67-bit correction, literal chop/GRS encodings of the exact
``S-B`` tail, and the diagnostic unmaterialized ``S-B`` tail itself.

Every program is a fixed datapath choice shared by all rows.  There are no
operand predicates, identity keys, learned thresholds, branch-local choices,
or hardware execution.  The nine ordinary frontier legs and all controls come
from the immutable h1386 feature bank.  The two d0d0 legs are reconstructed
from the current executable and paired with their already-cached miss rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h1321_famubus_grs_carrier_audit as h1321
import h1386_current_r59_feature_bank as h1386
import h1415_terminal_famubus_subtractor as h1415
import h206_p5_fadd_complete as h206
from h1184_upstream_halfway_audit import ExactOperation, Value


MODES = ("rn", "rd", "ru", "rz")
FINAL_POLICIES = (
    "exact",
    *(f"{mode}.{'norm' if normalize else 'raw'}"
      for mode in h206.MODES for normalize in (False, True)),
)


@dataclass(frozen=True)
class CorrectionPolicy:
    name: str
    program: h1415.Program | None = None


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError(f"empty input: {path}")
    return rows


def read_extra_misses(path: Path, operand: str) -> dict[str, dict[str, str]]:
    rows = {}
    for line in path.read_text().splitlines():
        fields = line.lower().split()
        if not fields:
            continue
        if len(fields) != 12 or fields[1] != "cos" \
                or fields[6] != "ok" or fields[9] != "ok":
            raise RuntimeError(f"unexpected miss row: {line}")
        row_operand = f"{fields[4]} {fields[5]}"
        if row_operand != operand:
            continue
        mode = fields[2]
        rows[mode] = {
            "label": "POS",
            "mode": mode,
            "op": operand,
            "model": f"{fields[7]}:{fields[8]}",
            "hw": f"{fields[10]}:{fields[11]}",
        }
    if set(rows) != {"rd", "rz"}:
        raise RuntimeError(
            f"expected rd/rz misses for {operand}, got {sorted(rows)}")
    return rows


def append_extra_rows(
    rows: list[dict[str, str]], model: Path, misses: Path, operand: str
) -> None:
    if any(row["op"] == operand for row in rows):
        raise RuntimeError("extra operand already present in feature bank")
    miss_rows = read_extra_misses(misses, operand)
    for mode in ("rd", "rz"):
        record = h1386.dump(str(model), mode, [operand])[0]
        record.update(miss_rows[mode])
        rows.append(record)


def exact_subtract(row: dict[str, str]) -> ExactOperation:
    magnitude = int(row["S"], 16) - int(row["B"], 16)
    if magnitude <= 0:
        raise RuntimeError(f"nonpositive S-B correction for {row['op']}")
    if magnitude != int(row["umag"], 16):
        raise RuntimeError(f"S-B/umag mismatch for {row['op']}")
    return ExactOperation(1, int(row["rscale"]), magnitude)


def incumbent_bus(row: dict[str, str]) -> h206.Bus:
    retained = int(row["br_r"], 16)
    if retained.bit_length() != 67:
        raise RuntimeError(f"incumbent correction is not 67 bits: {row['op']}")
    value = Value(1, int(row["rscale"]) + int(row["k"]), retained)
    return h1415.to_bus(value)


def exact_subtract_bus(row: dict[str, str], encoding: str) -> h206.Bus:
    operation = exact_subtract(row)
    if encoding == "chop67":
        value = h1415.quantize(operation, 67, False)
    elif encoding == "grs67":
        value = h1321.famubus_grs(operation)
    else:
        raise ValueError(encoding)
    return h1415.to_bus(value)


def h1415_bus(row: dict[str, str], program: h1415.Program) -> h206.Bus:
    left_operation = h1415.multiply(
        h1415.row_value(row, "mul"), h1415.row_value(row, "lf"))
    right_operation = h1415.multiply(
        h1415.row_value(row, "f4"), h1415.row_value(row, "rf"))
    left = h1415.encode_product(left_operation, program.left_encoding)
    right = h1415.encode_product(right_operation, program.right_encoding)
    bus, _ = h206.fadd(
        left, right, program.add_mode, normalize=program.normalize)
    return h206.materialize(bus, program.output_action)


def correction_bus(
    row: dict[str, str], policy: CorrectionPolicy
) -> h206.Bus:
    if policy.name == "incumbent67":
        return incumbent_bus(row)
    if policy.name == "exact_sub.chop67":
        return exact_subtract_bus(row, "chop67")
    if policy.name == "exact_sub.grs67":
        return exact_subtract_bus(row, "grs67")
    if policy.program is None:
        raise ValueError(policy)
    return h1415_bus(row, policy.program)


def correction_policies() -> tuple[CorrectionPolicy, ...]:
    fixed = (
        CorrectionPolicy("incumbent67"),
        CorrectionPolicy("exact_sub.chop67"),
        CorrectionPolicy("exact_sub.grs67"),
    )
    derived = tuple(
        CorrectionPolicy("h1415:" + program.name(), program)
        for program in h1415.programs()
    )
    return fixed + derived


def rounded_output(hidden: h58.FP, mode: str) -> str:
    effective_mode = "rd" if mode == "rz" else mode
    exponent, significand = h58.x87_round(hidden, effective_mode)
    return f"{exponent:04x}:{significand:016x}"


def final_output(
    correction: h206.Bus, final_policy: str, mode: str
) -> str:
    one = h206.h200.normalized_bus((0, 1, 0))
    if final_policy == "exact":
        hidden = h58.add_exact(one.value(), correction.value())
    else:
        add_mode, normalization = final_policy.split(".")
        hidden_bus, _ = h206.fadd(
            one,
            correction,
            add_mode,
            normalize=normalization == "norm",
        )
        hidden = hidden_bus.value()
    return rounded_output(hidden, mode)


def exact_tail_output(row: dict[str, str]) -> str:
    operation = exact_subtract(row)
    correction = (operation.sign, operation.magnitude, operation.exponent)
    hidden = h58.add_exact((0, 1, 0), correction)
    return rounded_output(hidden, row["mode"])


def score_outputs(
    rows: list[dict[str, str]], outputs: list[str]
) -> tuple[int, int, int, int, int]:
    counts = Counter()
    for row, output in zip(rows, outputs):
        target = row["label"] == "POS"
        wrong = output != row["hw"].lower()
        changed = output != row["model"].lower()
        counts["errors"] += wrong
        counts["target_errors"] += wrong and target
        counts["control_errors"] += wrong and not target
        counts["target_repairs"] += target and not wrong
        counts["control_changes"] += changed and not target
    return (
        counts["errors"],
        counts["target_errors"],
        counts["control_errors"],
        counts["target_repairs"],
        counts["control_changes"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default="3ffc d0d000000cc0b3f8")
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = read_rows(args.features)
    append_extra_rows(rows, args.model, args.misses, args.extra_op)
    targets = sum(row["label"] == "POS" for row in rows)
    controls = len(rows) - targets
    if targets != 11:
        raise RuntimeError(f"expected eleven frontier legs, got {targets}")

    # The reconstructed incumbent correction followed by an exact final add
    # must reproduce the executable.  This is the coordinate-system check for
    # the entire experiment, including the appended d0d0 rows.
    baseline_outputs = [
        final_output(incumbent_bus(row), "exact", row["mode"])
        for row in rows
    ]
    baseline_disagreements = [
        (row["mode"], row["op"], expected, row["model"].lower())
        for row, expected in zip(rows, baseline_outputs)
        if expected != row["model"].lower()
    ]
    if baseline_disagreements:
        raise RuntimeError(
            "incumbent interstage reconstruction differs from model: "
            + repr(baseline_disagreements[:5]))

    ranking = []
    best_by_source = {}
    for source_index, policy in enumerate(correction_policies(), 1):
        buses = [correction_bus(row, policy) for row in rows]
        for final_policy in FINAL_POLICIES:
            outputs = [
                final_output(bus, final_policy, row["mode"])
                for row, bus in zip(rows, buses)
            ]
            score = score_outputs(rows, outputs)
            item = (*score, policy.name, final_policy)
            ranking.append(item)
            previous = best_by_source.get(policy.name)
            if previous is None or item < previous:
                best_by_source[policy.name] = item
        if source_index % 8 == 0:
            print(
                f"correction sources {source_index}/"
                f"{len(correction_policies())}",
                flush=True,
            )

    exact_tail_outputs = [exact_tail_output(row) for row in rows]
    exact_tail_score = score_outputs(rows, exact_tail_outputs)
    ranking.append((*exact_tail_score, "exact_sub.full_tail", "exact"))
    ranking.sort()
    exact = [item for item in ranking if item[0] == 0]
    zero_collateral = [
        item for item in ranking
        if item[2] == 0 and item[1] < targets
    ]
    baseline_score = score_outputs(rows, baseline_outputs)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("model", args.model),
            ("misses", args.misses),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tfixed_FSUB_carrier_through_separate_"
            "FINAL_ADD_final_add\n")
        output.write(f"rows\t{len(rows)}\n")
        output.write(f"targets\t{targets}\n")
        output.write(f"controls\t{controls}\n")
        output.write(f"correction_sources\t{len(correction_policies()) + 1}\n")
        output.write(f"final_policies\t{len(FINAL_POLICIES)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"baseline_errors\t{baseline_score[0]}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(zero_collateral)}\n")
        output.write("incumbent_interstage_reconstruction\tPASS\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\ttarget_repairs\t"
            "control_changes\tcorrection_source\tfinal_policy\n")
        for item in ranking:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best final policy per correction source]\n")
        for name in sorted(best_by_source):
            output.write("\t".join(map(str, best_by_source[name])) + "\n")
        output.write("\n[zero-control-collateral improvements]\n")
        for item in zero_collateral:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[zero-error programs]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: rows={len(rows)} programs={len(ranking)} "
        f"exact={len(exact)} improvements={len(zero_collateral)} "
        f"best={ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
