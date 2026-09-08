#!/usr/bin/env python3
"""Test Intel's literal redundant-format LZA vector at the R59 terminal.

US7024439B2 gives a closed combinational leading-zero/one anticipator for a
two-word, possibly redundant, adder input.  For every overlapping three-bit
window, each input-bit pair is classified Z/P/G and the predictive vector L
is asserted for the eighteen patterns listed in the patent.  The leading L
bit predicts the transition in the eventual two's-complement sum; a following
shifter corrects the prediction by zero, one, or two places.

This audit applies that literal equation to the materialized terminal R59
rows before their final carry-propagate addition.  Candidate wires are only
the patented L vector, its binary count/select bits, its leading pattern, the
result sign, and the measured 0/1/2 correction class.  Each wire is composed
with the incumbent carry by one global two-input Boolean gate.  There are no
operand identities, branches, thresholds, or learned truth tables.

The separately tracked d0d0 row is reconstructed from the current executable
and appended with its all-mode-required carry=1 label.  Hardware is never
executed; all other labels come from cached all-mode response banks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np

from h1110_carry_gate_mine import (
    GATE_NAMES,
    allmode_allowed,
    extract_carry_state,
    gate_changes,
    gate_errors,
    state_bad_counts,
)
from h1128_fused_terminal_csa_mine import (
    MASK,
    WIDTH,
    negate_rows,
    reduce_balanced,
)
from h1386_current_r59_feature_bank import dump


PATTERNS = (
    "PGP", "PGG", "PZP", "PZZ", "ZZP", "ZZG",
    "ZPZ", "ZPP", "ZPG", "GZP", "GZG", "GPZ",
    "GPP", "GPG", "GGZ", "GGP", "ZGZ", "ZGP",
)
PATTERN_SET = frozenset(PATTERNS)
UNCERTAIN_PATTERNS = frozenset(("PGP", "PZP", "ZZP", "GZP", "GGP", "ZGP"))
RELATIVE_L_BITS = range(-16, 17)


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
        raise RuntimeError(f"empty feature bank: {path}")
    return rows


def materialized_pair(row: dict[str, str]) -> tuple[int, int, int]:
    left = int(row["tc_left_sig"], 16) << int(row["dl"])
    right = int(row["tc_right_sig"], 16) << int(row["dr"])
    rows = [left]
    payload = int(row["payload"])
    if payload:
        rows.append(payload << int(row["dp"]))
    rows.extend(negate_rows([right]))
    sum_vector, carry_vector, _ = reduce_balanced(rows)
    return sum_vector, carry_vector, int(row["k"])


def zpg(left: int, right: int, position: int) -> str:
    pair = ((left >> position) & 1) + ((right >> position) & 1)
    return "ZPG"[pair]


def lza_vector(left: int, right: int) -> tuple[int, int, str]:
    classes = [zpg(left, right, position) for position in range(WIDTH)]
    vector = 1  # Patent's mandatory least-significant catch-all bit.
    leading_pattern = "LSB"
    for high in range(2, WIDTH):
        pattern = "".join((classes[high], classes[high - 1], classes[high - 2]))
        if pattern in PATTERN_SET:
            vector |= 1 << high
            leading_pattern = pattern
    leading = vector.bit_length() - 1
    if leading >= 2:
        leading_pattern = "".join(
            (classes[leading], classes[leading - 1], classes[leading - 2])
        )
    return vector, leading, leading_pattern


def row_columns(row: dict[str, str]) -> tuple[dict[str, int], tuple[int, int, str, int]]:
    sum_vector, carry_vector, cut = materialized_pair(row)
    vector, predicted_position, pattern = lza_vector(sum_vector, carry_vector)
    raw = (sum_vector + carry_vector) & MASK
    negative = (raw >> (WIDTH - 1)) & 1
    magnitude = (-raw) & MASK if negative else raw
    actual_position = magnitude.bit_length() - 1
    if actual_position < 0:
        raise RuntimeError(f"zero terminal result for {row['op']}")

    count = (WIDTH - 1) - predicted_position
    correction = predicted_position - actual_position
    values: dict[str, int] = {
        "sign.negative": negative,
        "leading_pattern.uncertain": int(pattern in UNCERTAIN_PATTERNS),
        "correction.zero": int(correction == 0),
        "correction.one": int(correction == 1),
        "correction.two": int(correction == 2),
        "correction.nonzero": int(correction != 0),
        "correction.lowbit": correction & 1,
        "correction.highbit": (correction >> 1) & 1,
    }
    for name in PATTERNS:
        values[f"leading_pattern.{name}"] = int(pattern == name)
    values["leading_pattern.LSB"] = int(pattern == "LSB")
    for bit_index in range(8):
        values[f"count.bit{bit_index}"] = (count >> bit_index) & 1
        values[f"predicted_position.bit{bit_index}"] = (
            predicted_position >> bit_index
        ) & 1
        values[f"actual_position.bit{bit_index}"] = (
            actual_position >> bit_index
        ) & 1
    for residue in range(4):
        values[f"count.low2.eq{residue}"] = int((count & 3) == residue)
    for bit_index in range(6):
        values[f"count.coarse.bit{bit_index}"] = (count >> (bit_index + 2)) & 1
    for offset in RELATIVE_L_BITS:
        position = cut + offset
        values[f"L.cut{offset:+d}"] = (
            (vector >> position) & 1 if 0 <= position < WIDTH else 0
        )
    return values, (predicted_position, actual_position, pattern, correction)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--positive-allmode", type=Path, required=True)
    parser.add_argument("--control-allmode", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--extra-op", default="3ffc d0d000000cc0b3f8")
    parser.add_argument("--extra-mode", default="rd")
    parser.add_argument("--extra-carry", type=int, choices=(0, 1), default=1)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    positive = allmode_allowed(args.positive_allmode)
    controls = allmode_allowed(args.control_allmode)
    rows = read_rows(args.features)
    if any(row["op"] == args.extra_op for row in rows):
        raise RuntimeError("extra operand is already in the feature bank")
    extra = dump(str(args.model), args.extra_mode, [args.extra_op])[0]
    extra.update({
        "label": "POS",
        "desired": f"carry{args.extra_carry}",
        "mode": args.extra_mode,
        "op": args.extra_op,
    })
    rows.append(extra)

    states = []
    traces = []
    names: list[str] | None = None
    matrix: np.ndarray | None = None
    for index, row in enumerate(rows):
        if row["op"] == args.extra_op:
            s_value = int(row["S"], 16)
            b_value = int(row["B"], 16)
            mask = (1 << int(row["k"])) - 1
            borrow = int((s_value & mask) < (b_value & mask))
            allowed_delta = {borrow - 1 + args.extra_carry}
        else:
            labels = positive if row["label"] == "POS" else controls
            allowed_delta = labels[row["op"]]
        states.append(extract_carry_state(row, allowed_delta))
        columns, trace = row_columns(row)
        traces.append(trace)
        if names is None:
            names = sorted(columns)
            matrix = np.empty((len(rows), len(names)), dtype=np.uint8)
        elif set(columns) != set(names):
            raise RuntimeError("feature schema changed")
        assert matrix is not None and names is not None
        matrix[index] = [columns[name] for name in names]

    assert matrix is not None and names is not None
    current = np.asarray([state[2] for state in states], dtype=np.uint8)
    allowed = np.asarray(
        [[carry in state[3] for carry in (0, 1)] for state in states],
        dtype=bool,
    )
    capable = allowed.any(axis=1)
    targets = np.asarray([row["label"] == "POS" for row in rows]) & capable
    controls_mask = (~targets) & capable
    groups = {"all": capable, "target": targets, "control": controls_mask}
    counts = {
        name: state_bad_counts(matrix, current, allowed, subset)
        for name, subset in groups.items()
    }

    ranking = []
    for gate in range(16):
        errors = {name: gate_errors(group, gate) for name, group in counts.items()}
        changes = gate_changes(matrix, current, controls_mask, gate)
        for column, feature in enumerate(names):
            ranking.append((
                int(errors["all"][column]),
                int(errors["target"][column]),
                int(errors["control"][column]),
                int(changes[column]),
                GATE_NAMES[gate],
                gate,
                feature,
            ))
    ranking.sort()
    exact = [item for item in ranking if item[0] == 0]
    nonidentity = [item for item in ranking if item[5] != 0xC]
    active = [item for item in nonidentity if item[3] != 0]
    improvements = [
        item for item in nonidentity
        if item[2] == 0 and item[1] < int(targets.sum())
    ]
    repairers = [item for item in nonidentity if item[1] < int(targets.sum())]
    correction_counts = Counter(trace[3] for trace in traces)
    pattern_counts = Counter(trace[2] for trace in traces)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write("candidate_policy\tUS7024439_literal_redundant_LZA_vector\n")
        output.write(f"source_rows\t{len(rows)}\n")
        output.write(f"carry_capable\t{int(capable.sum())}\n")
        output.write(f"target_rows\t{int(targets.sum())}\n")
        output.write(f"extra_operand\t{args.extra_op}\n")
        output.write(f"extra_required_carry\t{args.extra_carry}\n")
        output.write(f"features\t{len(names)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(f"zero_collateral_improvements\t{len(improvements)}\n")
        output.write("\n[correction distribution]\n")
        output.write("predicted_minus_actual_position\trows\n")
        for correction, count in sorted(correction_counts.items()):
            output.write(f"{correction}\t{count}\n")
        output.write("\n[leading pattern distribution]\n")
        output.write("pattern\trows\n")
        for pattern, count in sorted(pattern_counts.items()):
            output.write(f"{pattern}\t{count}\n")
        header = (
            "all_bad\ttarget_bad\tcontrol_bad\tcontrol_changes\tgate\t"
            "gate_mask\tfeature\n"
        )
        for title, items in (
            ("best nonidentity", nonidentity),
            ("best active", active),
            ("best target repairers", repairers),
            ("zero-collateral improvements", improvements),
            ("zero-error programs", exact),
        ):
            output.write(f"\n[{title}]\n")
            output.write(header)
            for item in items[:1000]:
                output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[target traces]\n")
        output.write(
            "operand\tpredicted_position\tactual_position\tleading_pattern\t"
            "correction\n"
        )
        for row, trace in zip(rows, traces):
            if row["label"] == "POS":
                output.write(row["op"] + "\t" + "\t".join(map(str, trace)) + "\n")

    print(
        f"wrote {args.report}: rows={len(rows)} features={len(names)} "
        f"programs={len(ranking)} exact={len(exact)} "
        f"improvements={len(improvements)} best={nonidentity[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
