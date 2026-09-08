#!/usr/bin/env python3
"""Audit a source-defined one's-complement final-FADD carry representation.

Sun US5808926A publishes a complete low-slice representation for a floating
adder that overlaps rounding with significand addition.  For effective
subtraction it complements the aligned smaller significand, supplies the
one's-complement end-around carry, and derives named ``Gs``, ``Ps``, ``Cs``
and round-in signals from sum bits S[4:0], result sign, normalization class,
and rounding mode.

This audit generalizes the patent's format-independent equations from its
worked binary64 example to the 64-bit x87 significand plus G/R/S.  Before any
label is scored, the representation must reproduce the current final
``1 + correction`` output on every source row.  It then tests only the ten
literal named/input signals of that low-slice circuit through one global
Boolean gate with the incumbent R59 carry.  A complete-tuple collision test
rules out arbitrary deterministic selectors over the same vocabulary.

The source is a Sun embodiment, not evidence of Intel or Skylake topology.
All labels are immutable cached data and no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import h1424_subtract_final_add_interstage_carrier as h1424
import h1425_p5_public_mux_signals as h1425
import h206_p5_fadd_complete as h206
from h1110_carry_gate_mine import GATE_NAMES


PATENT = "US5808926A"
PATENT_URL = "https://patents.google.com/patent/US5808926A/en"
WIDTH = 67
MASK = (1 << WIDTH) - 1
BELOW_J_MASK = (1 << (WIDTH - 1)) - 1
SIGNAL_NAMES = (
    "S0",
    "S1",
    "S2",
    "S3",
    "S4",
    "Gout",
    "Gs",
    "Ps",
    "Cs",
    "RV",
)


@dataclass(frozen=True)
class PreparedRow:
    row: dict[str, str]
    current: int
    required: int
    target: bool
    signals: tuple[int, ...]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def jam_right(word: int, distance: int) -> int:
    shifted = word >> distance
    if distance and word & ((1 << distance) - 1):
        shifted |= 1
    return shifted


def low_slice(row: dict[str, str]) -> tuple[dict[str, int], str, tuple[int, ...]]:
    """Return the literal Comp=1, Gout=0 final-add low-slice state."""
    one = h206.h200.normalized_bus((0, 1, 0))
    correction = h1424.incumbent_bus(row)
    if one.sign != 0 or correction.sign != 1:
        raise RuntimeError(f"unexpected final-add signs for {row['op']}")
    distance = one.exponent - correction.exponent
    if distance <= 1:
        raise RuntimeError(f"final add left the patent rounding path: {distance}")

    # The positive aligned smaller operand has J at bit 66 and G/R/S at 2:0.
    # Complementing all 67 positions also implements the patent's complemented
    # sticky convention; adding Comp=1 supplies its end-around carry.
    aligned = jam_right(correction.word, distance)
    complemented = (~aligned) & MASK
    total = one.word + complemented + 1
    sum_word = total & MASK

    # For effective subtraction, Gout is the carry into J (bit 66), not the
    # discarded carry above the complete one's-complement word.
    gout = (
        (one.word & BELOW_J_MASK)
        + (complemented & BELOW_J_MASK)
        + 1
    ) >> (WIDTH - 1)
    if gout != 0 or sum_word.bit_length() != WIDTH - 1:
        raise RuntimeError(
            f"final add left one-bit-normalization class for {row['op']}"
        )

    bits = tuple((sum_word >> bit) & 1 for bit in range(5))
    s0, s1, s2, s3, s4 = bits
    mode = row["mode"]
    if mode == "rn":
        # Appendix 1/3, Comp=1, positive result, Gout=0.
        gs = s4 & s3 & s2 & s1
        ps = s4 & s3 & s2
        round_in = s1 & (s2 | s0)
    elif mode == "ru":
        gs = s4 & s3 & s2 & (s1 | s0)
        ps = s4 & s3 & (s2 | s1 | s0)
        round_in = s1 | s0
    elif mode in {"rd", "rz"}:
        # The visible result is positive, so both modes truncate magnitude.
        gs = 0
        ps = 0
        round_in = 0
    else:
        raise RuntimeError(f"unknown rounding mode {mode}")
    carry = gs | (ps & gout)

    # One-bit left normalization makes S2 the retained LSB.  This output check
    # is the applicability gate: the source-defined representation must equal
    # the independently reconstructed exact final add before its wires are
    # allowed into the selector audit.
    retained = (sum_word >> 2) + round_in
    if retained.bit_length() != 64:
        raise RuntimeError(f"bad rounded final width for {row['op']}")
    output = f"{one.exponent - 1 + 0x3FFF:04x}:{retained:016x}"
    expected = h1424.final_output(correction, "exact", mode)
    if output != expected:
        raise RuntimeError(
            f"patent representation failed applicability for {row['op']}: "
            f"{output} != {expected}"
        )

    values = {
        "S0": s0,
        "S1": s1,
        "S2": s2,
        "S3": s3,
        "S4": s4,
        "Gout": gout,
        "Gs": gs,
        "Ps": ps,
        "Cs": carry,
        "RV": round_in,
    }
    trace = (distance, *bits, gout, gs, ps, carry, round_in)
    return values, output, trace


def prepare(args: argparse.Namespace) -> tuple[
    list[PreparedRow], list[dict[str, str]], Counter[tuple[int, ...]]
]:
    base, rows, _, _ = h1425.prepare(args)
    source_traces: Counter[tuple[int, ...]] = Counter()
    for row in rows:
        _, output, trace = low_slice(row)
        source_traces[trace] += 1
        if output != row["model"].lower():
            raise RuntimeError(
                f"patent output/current model mismatch for {row['op']}"
            )

    prepared = []
    for item in base:
        values, _, _ = low_slice(item.row)
        if set(values) != set(SIGNAL_NAMES):
            raise RuntimeError("low-slice signal schema changed")
        prepared.append(PreparedRow(
            row=item.row,
            current=item.current,
            required=item.required,
            target=item.target,
            signals=tuple(values[name] for name in SIGNAL_NAMES),
        ))
    return prepared, rows, source_traces


def gate_output(gate: int, current: int, signal: int) -> int:
    return (gate >> (2 * current + signal)) & 1


def collision_summary(prepared: list[PreparedRow]) -> tuple[list[tuple], int]:
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        key = (item.row["branch"], item.current, item.signals)
        groups[key][item.required].append(item)

    mixed = []
    targets_in_mixed = 0
    for key, members in groups.items():
        if not members[0] or not members[1]:
            continue
        targets = [item for side in members for item in side if item.target]
        targets_in_mixed += len(targets)
        mixed.append((
            key,
            len(members[0]),
            len(members[1]),
            tuple((item.row["mode"], item.row["op"]) for item in targets),
            (members[0][0].row["mode"], members[0][0].row["op"]),
            (members[1][0].row["mode"], members[1][0].row["op"]),
        ))
    return mixed, targets_in_mixed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default=h1425.EXTRA_OP)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    prepared, rows, source_traces = prepare(args)
    target_count = sum(item.target for item in prepared)
    control_count = len(prepared) - target_count
    ones = Counter()
    for item in prepared:
        for name, value in zip(SIGNAL_NAMES, item.signals):
            ones[name] += value

    ranking = []
    for signal_index, name in enumerate(SIGNAL_NAMES):
        for gate in range(16):
            counts = Counter()
            for item in prepared:
                output = gate_output(
                    gate, item.current, item.signals[signal_index]
                )
                wrong = output != item.required
                changed = output != item.current
                counts["errors"] += wrong
                counts["target_errors"] += wrong and item.target
                counts["control_errors"] += wrong and not item.target
                counts["control_changes"] += changed and not item.target
            ranking.append((
                counts["errors"],
                counts["target_errors"],
                counts["control_errors"],
                counts["control_changes"],
                GATE_NAMES[gate],
                gate,
                name,
            ))
    ranking.sort()
    exact = [item for item in ranking if item[0] == 0]
    improvements = [
        item for item in ranking
        if item[2] == 0 and item[1] < target_count
    ]
    mixed, targets_in_mixed = collision_summary(prepared)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(f"primary_source\t{PATENT}\t{PATENT_URL}\n")
        output.write(
            "source_scope\tSun_patent_exact_arithmetic_isomorphism_not_"
            "Intel_or_Skylake_provenance\n"
        )
        output.write(
            "candidate_policy\tliteral_ones_complement_low_slice_S4_0_"
            "Gout_Gs_Ps_Cs_RV_only\n"
        )
        output.write(f"source_rows\t{len(rows)}\n")
        output.write("source_output_reconstruction_errors\t0\n")
        output.write(f"source_low_slice_classes\t{len(source_traces)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"source_defined_signals\t{len(SIGNAL_NAMES)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(improvements)}\n"
        )
        output.write(f"complete_tuple_mixed_groups\t{len(mixed)}\n")
        output.write(
            f"targets_in_complete_tuple_mixed_groups\t{targets_in_mixed}\n"
        )

        output.write("\n[signal distribution]\n")
        output.write("signal\tones\tzeros\ttarget_ones\ttarget_zeros\n")
        for index, name in enumerate(SIGNAL_NAMES):
            target_ones = sum(
                item.target and item.signals[index] for item in prepared
            )
            output.write(
                f"{name}\t{ones[name]}\t{len(prepared) - ones[name]}\t"
                f"{target_ones}\t{target_count - target_ones}\n"
            )

        output.write("\n[low-slice class distribution]\n")
        output.write(
            "distance\tS0\tS1\tS2\tS3\tS4\tGout\tGs\tPs\tCs\tRV\trows\n"
        )
        for trace, count in sorted(source_traces.items()):
            output.write("\t".join(map(str, (*trace, count))) + "\n")

        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in ranking:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[complete tuple collision witnesses]\n")
        output.write(
            "branch\tcurrent\tS0\tS1\tS2\tS3\tS4\tGout\tGs\tPs\tCs\tRV\t"
            "required0\trequired1\ttargets\texample0\texample1\n"
        )
        for key, count0, count1, targets, example0, example1 in mixed:
            branch, current, signals = key
            output.write(
                f"{branch}\t{current}\t"
                + "\t".join(map(str, signals))
                + f"\t{count0}\t{count1}\t{targets}\t{example0}\t{example1}\n"
            )

        output.write("\n[result]\n")
        output.write("arithmetic_representation\texact_on_source_rows\n")
        output.write("r59_selector\timpossible_on_complete_signal_tuple\n")
        output.write("selector_candidate\tnone\n")

    print(
        f"wrote {args.report}: source={len(rows)} constrained={len(prepared)} "
        f"signals={len(SIGNAL_NAMES)} exact={len(exact)} "
        f"improvements={len(improvements)} mixed_targets={targets_in_mixed}",
        flush=True,
    )


if __name__ == "__main__":
    main()
