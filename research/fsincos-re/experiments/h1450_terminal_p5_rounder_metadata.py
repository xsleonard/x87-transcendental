#!/usr/bin/env python3
"""Audit the P5 rounder's named metadata at the terminal ``_FSUB``.

Intel US5258943A exposes a small, source-defined Boolean vocabulary around
the 68-bit FADD rounder: overflow/J pre-normalization class, the displaced
low bit on a 1x right shift, normalized L/G/R/S, inexact, the RN increment
decision, retained-fraction all-ones, incrementer carry, round overflow,
overflow-plus-J, and result zero.  h1427 reconstructed this vocabulary only
at the four RN64 Horner additions.  The cosine model has a terminal
subtraction before the final addition. This pass tests whether the
reconstructed terminal carrier supplies the missing input-dependent
coordinate.

The known terminal operation materializes by chopping to 67 bits, so the
validated post-``_FSUB`` carrier is used directly.  No unvalidated raw P5
projection is allowed into the selector search.  As an explicit applicability
check, the four published sticky interpretations with normalization on/off
are replayed from the terminal operands and compared against that carrier;
none is treated as Skylake state unless it reconstructs every source row.

Every tested selector is one global two-input Boolean gate over the incumbent
R59 carry and one named metadata signal.  A separate collision test groups by
branch, incumbent carry, and the complete named terminal tuple.  There are no
operand identities, thresholds, bit-position searches, intervals, trees, or
new hardware observations.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import h1415_terminal_famubus_subtractor as h1415
import h1424_subtract_final_add_interstage_carrier as h1424
import h1425_p5_public_mux_signals as h1425
import h206_p5_fadd_complete as h206
from h1110_carry_gate_mine import GATE_NAMES
from h1191_grs_history_isomorphism import compare_values


PATENT = "US5258943A"
PATENT_URL = "https://patents.google.com/patent/US5258943A/en"
MASK63 = (1 << 63) - 1
MASK64 = (1 << 64) - 1
SIGNAL_NAMES = (
    "pre.case00_left",
    "pre.case01_asis",
    "pre.case1x_right",
    "pre.fr1xlsb",
    "normalized.L",
    "normalized.G",
    "normalized.R",
    "normalized.S",
    "inexact",
    "frrbit",
    "frlmones",
    "frhcout",
    "round_overflow",
    "frojones",
    "frreszero",
)
NEW_METADATA = (
    "pre.case00_left",
    "pre.case01_asis",
    "pre.case1x_right",
    "pre.fr1xlsb",
    "frlmones",
    "frhcout",
    "round_overflow",
    "frojones",
    "frreszero",
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


def carrier_metadata(bus: h206.Bus) -> dict[str, int]:
    """Return the named US5258943A signals for a normalized FAMUBUS."""
    if not bus.word or bus.word.bit_length() != 67:
        raise RuntimeError("terminal carrier is not a normalized FAMUBUS")
    raw_case = (bus.word >> 66) & 3
    if raw_case != 1:
        raise RuntimeError(f"unexpected terminal carrier class {raw_case:02b}")

    l_bit = (bus.word >> 3) & 1
    guard = (bus.word >> 2) & 1
    round_bit = (bus.word >> 1) & 1
    sticky = bus.word & 1
    inexact = int(bool(guard or round_bit or sticky))
    frrbit = guard & int(bool(round_bit or sticky or l_bit))
    retained = (bus.word >> 3) & MASK64
    fraction = retained & MASK63
    frlmones = int(fraction == MASK63)
    frhcout = int(retained == MASK64)
    if frhcout != frlmones:
        raise RuntimeError("normalized J=1 did not equate frhcout/frlmones")

    return {
        "pre.case00_left": 0,
        "pre.case01_asis": 1,
        "pre.case1x_right": 0,
        "pre.fr1xlsb": 0,
        "normalized.L": l_bit,
        "normalized.G": guard,
        "normalized.R": round_bit,
        "normalized.S": sticky,
        "inexact": inexact,
        "frrbit": frrbit,
        "frlmones": frlmones,
        "frhcout": frhcout,
        "round_overflow": frrbit & frhcout,
        "frojones": 0,
        "frreszero": 0,
    }


def raw_projection_counts(rows: list[dict[str, str]]) -> Counter:
    """Check whether any public P5 subtract interpretation is validated."""
    counts = Counter()
    for row in rows:
        left = h1415.to_bus(h1415.row_value(row, "left"))
        right = h1415.to_bus(h1415.row_value(row, "right"))
        expected = h1424.incumbent_bus(row)
        for mode in h206.MODES:
            for normalize in (False, True):
                candidate, trace = h206.fadd(
                    left, right, mode, normalize=normalize
                )
                if trace.operation != "far-sub":
                    raise RuntimeError(
                        f"terminal path ceased to be far subtraction: {row['op']}"
                    )
                key = (mode, normalize)
                counts[key, "rows"] += 1
                counts[key, "matches"] += (
                    compare_values(
                        h1415.from_bus(candidate), h1415.from_bus(expected)
                    ) == 0
                )
    return counts


def prepare(args: argparse.Namespace) -> tuple[
    list[PreparedRow], list[dict[str, str]], Counter
]:
    base, rows, _, _ = h1425.prepare(args)
    prepared = []
    for item in base:
        values = carrier_metadata(h1424.incumbent_bus(item.row))
        if set(values) != set(SIGNAL_NAMES):
            raise RuntimeError("terminal metadata schema changed")
        prepared.append(PreparedRow(
            row=item.row,
            current=item.current,
            required=item.required,
            target=item.target,
            signals=tuple(values[name] for name in SIGNAL_NAMES),
        ))
    return prepared, rows, raw_projection_counts(rows)


def gate_output(gate: int, current: int, signal: int) -> int:
    return (gate >> (2 * current + signal)) & 1


def collision_summary(
    prepared: list[PreparedRow], indices: tuple[int, ...] | None = None
) -> tuple[list[tuple], int]:
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        signals = (
            item.signals
            if indices is None
            else tuple(item.signals[index] for index in indices)
        )
        key = (item.row["branch"], item.current, signals)
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

    prepared, rows, projections = prepare(args)
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
    metadata_indices = tuple(
        SIGNAL_NAMES.index(name) for name in NEW_METADATA
    )
    metadata_mixed, metadata_targets_in_mixed = collision_summary(
        prepared, metadata_indices
    )
    exact_projections = [
        key for key in (
            (mode, normalize)
            for mode in h206.MODES
            for normalize in (False, True)
        )
        if projections[key, "matches"] == projections[key, "rows"]
    ]

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
            "candidate_policy\tvalidated_post_FSUB_carrier_named_rounder_"
            "metadata_only\n"
        )
        output.write(
            "raw_projection_policy\tapplicability_check_only_no_unvalidated_"
            "projection_scored\n"
        )
        output.write(f"source_rows\t{len(rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"named_terminal_signals\t{len(SIGNAL_NAMES)}\n")
        output.write(f"new_metadata_signals\t{len(NEW_METADATA)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(improvements)}\n"
        )
        output.write(f"complete_tuple_mixed_groups\t{len(mixed)}\n")
        output.write(
            f"targets_in_complete_tuple_mixed_groups\t{targets_in_mixed}\n"
        )
        output.write(
            f"metadata_tuple_mixed_groups\t{len(metadata_mixed)}\n"
        )
        output.write(
            "targets_in_metadata_tuple_mixed_groups\t"
            f"{metadata_targets_in_mixed}\n"
        )
        output.write(f"exact_raw_P5_projections\t{len(exact_projections)}\n")

        output.write("\n[raw P5 projection applicability]\n")
        output.write("sticky_mode\tnormalize\tmatches\trows\n")
        for mode in h206.MODES:
            for normalize in (False, True):
                key = (mode, normalize)
                output.write(
                    f"{mode}\t{int(normalize)}\t"
                    f"{projections[key, 'matches']}\t"
                    f"{projections[key, 'rows']}\n"
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

        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in ranking:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[complete tuple collision witnesses]\n")
        output.write(
            "branch\tcurrent_carry\tcarry0_rows\tcarry1_rows\t"
            "target_rows\tcarry0_example\tcarry1_example\n"
        )
        for key, zeros, ones_count, targets, zero_example, one_example in mixed:
            branch, current, _ = key
            target_text = ",".join(
                f"{mode}:{operand}" for mode, operand in targets
            )
            output.write(
                f"{branch}\t{current}\t{zeros}\t{ones_count}\t"
                f"{target_text}\t{zero_example[0]}:{zero_example[1]}\t"
                f"{one_example[0]}:{one_example[1]}\n"
            )

        output.write("\n[result]\n")
        output.write("terminal_rounder_metadata_selector\timpossible_on_wall\n")
        output.write(
            "reason\tevery_target_has_opposite_required_carry_collision_on_"
            "branch_incumbent_and_complete_named_terminal_tuple\n"
        )
        output.write(
            "raw_pre_rounder_extension\trejected_before_mining_no_public_P5_"
            "projection_reconstructs_the_validated_terminal_carrier\n"
        )

    print(
        f"wrote {args.report}: rows={len(rows)} constrained={len(prepared)} "
        f"signals={len(SIGNAL_NAMES)} exact={len(exact)} "
        f"improvements={len(improvements)} mixed_targets={targets_in_mixed} "
        f"raw_exact={len(exact_projections)} best={ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
