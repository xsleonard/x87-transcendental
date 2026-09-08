#!/usr/bin/env python3
"""Audit the source-defined post-add normalizer after Intel's 32+36 adder.

Intel US20080133895A1 does not end its double-extended FADD at the LS36 to
MS32 carry chain tested by h1431.  Paragraphs 21--23 also describe result
selection after the two adders, separate leading-zero detectors, normalization
shift codes and masks, guard/round selection, sticky merging, a rounder, and an
exponent fix on round-up.  This audit reconstructs the non-aliased Boolean
outputs of that named pipeline at the same six arithmetic stages as h1431.

The double-extended projection is fixed: the selected 68-bit magnitude is
left-normalized, its high 64 bits are the retained significand, and the next
two bits are guard and round; all remaining and alignment-discarded bits form
sticky.  Four Horner FADDs use their validated RN64 writeback mode, the
internal terminal subtraction is evaluated under RN as a source hypothesis,
and the final FINAL_ADD uses the cached architectural rounding mode.  No bit
position, threshold, truth table, operand identity, or branch rule is fitted.

Every source signal is composed with the incumbent R59 carry by one global
Boolean gate.  The script also exhausts fixed one-bit and two-input affine
state recurrences shared across all six stages.  Opposite-label collisions on
the complete new history rule out every deterministic selector driven only by
that history, independently of these bounded recurrence families.  All labels
are immutable cached data and no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import h1425_p5_public_mux_signals as h1425
import h1431_multiformat_split_adder_state as h1431
import h1432_multiformat_split_adder_logic as h1432
from h1110_carry_gate_mine import GATE_NAMES


PATENT = "US20080133895A1"
PATENT_URL = "https://patents.google.com/patent/US20080133895A1/en"
WIDTH = 68
LOW_WIDTH = 36
HIGH_WIDTH = 32
MASK68 = (1 << WIDTH) - 1
MASK36 = (1 << LOW_WIDTH) - 1
MASK32 = (1 << HIGH_WIDTH) - 1
STAGES = h1431.STAGES


@dataclass(frozen=True)
class PreparedRow:
    row: dict[str, str]
    current: int
    required: int
    target: bool
    signals: tuple[int, ...]
    trace: tuple[tuple[object, ...], ...]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def code_bits(values: dict[str, int], prefix: str, value: int, width: int) -> None:
    for bit in range(width):
        values[f"{prefix}.bit{bit}"] = (value >> bit) & 1


def postadd_signals(left, right, active_mode: str) -> tuple[dict[str, int], tuple]:
    """Project paragraphs 21--23 onto one double-extended operation."""
    if not left.word or not right.word:
        raise RuntimeError("post-add audit requires two nonzero operands")
    if left.word.bit_length() > 67 or right.word.bit_length() > 67:
        raise RuntimeError("input exceeds normalized 68-bit extended format")

    exponent = max(left.exponent, right.exponent)
    left_aligned, left_tail = h1431.h206.h200.shift_right(
        left.word, exponent - left.exponent
    )
    right_aligned, right_tail = h1431.h206.h200.shift_right(
        right.word, exponent - right.exponent
    )
    subtract = left.sign != right.sign
    if subtract:
        if left_aligned >= right_aligned:
            magnitude = left_aligned - right_aligned
            result_sign = left.sign
        else:
            magnitude = right_aligned - left_aligned
            result_sign = right.sign
        result_inverted = int(bool(magnitude))
    else:
        magnitude = left_aligned + right_aligned
        result_sign = left.sign
        result_inverted = 0

    if not magnitude or magnitude > MASK68:
        raise RuntimeError("selected post-add magnitude is outside 68 bits")

    high = magnitude >> LOW_WIDTH
    low = magnitude & MASK36
    high_lzc = HIGH_WIDTH - high.bit_length() if high else HIGH_WIDTH
    low_lzc = LOW_WIDTH - low.bit_length() if low else LOW_WIDTH
    shift = WIDTH - magnitude.bit_length()
    normalized = magnitude << shift
    if normalized.bit_length() != WIDTH or normalized > MASK68:
        raise RuntimeError("68-bit normalization failed")

    retained = normalized >> 4
    guard = (normalized >> 3) & 1
    round_bit = (normalized >> 2) & 1
    sticky = int(bool((normalized & 3) or left_tail or right_tail))
    lsb = retained & 1
    inexact = int(bool(guard or round_bit or sticky))
    above_half = int(bool(guard and (round_bit or sticky)))
    tie = int(bool(guard and not round_bit and not sticky))
    rn_increment = int(bool(guard and (round_bit or sticky or lsb)))
    ru_increment = int(bool(not result_sign and inexact))
    rd_increment = int(bool(result_sign and inexact))
    increments = {
        "rn": rn_increment,
        "ru": ru_increment,
        "rd": rd_increment,
        "rz": 0,
    }
    if active_mode not in increments:
        raise ValueError(active_mode)
    active_increment = increments[active_mode]
    round_carry = int(bool(active_increment and retained == (1 << 64) - 1))

    values = {
        "select.result_inverted": result_inverted,
        "select.result_sign": result_sign,
        "lzd.ms32.empty": int(not high),
        "lzd.ls36.empty": int(not low),
        "normalize.cross32": int(shift >= 32),
        "normalize.cross64": int(shift >= 64),
        "normalized.L": lsb,
        "normalized.G": guard,
        "normalized.R": round_bit,
        "normalized.S": sticky,
        "round.inexact": inexact,
        "round.above_half": above_half,
        "round.tie": tie,
        "round.rn_increment": rn_increment,
        "round.ru_increment": ru_increment,
        "round.rd_increment": rd_increment,
        "round.active_increment": active_increment,
        "round.carryout": round_carry,
        "exponent.fix_roundup": round_carry,
    }
    code_bits(values, "lzd.ms32.code", high_lzc, 6)
    code_bits(values, "lzd.ls36.code", low_lzc, 6)
    code_bits(values, "normalize.shift_code", shift, 7)
    trace = (
        subtract, result_inverted, result_sign, high_lzc, low_lzc, shift,
        lsb, guard, round_bit, sticky, rn_increment, active_increment,
        round_carry,
    )
    return values, trace


def source_signals(
    row: dict[str, str]
) -> tuple[dict[str, int], tuple[tuple[object, ...], ...]]:
    values: dict[str, int] = {}
    traces = []
    for stage, (left, right) in h1431.stage_inputs(row).items():
        active_mode = row["mode"] if stage == "final_add" else "rn"
        local, trace = postadd_signals(left, right, active_mode)
        values.update({f"{stage}.{name}": value for name, value in local.items()})
        traces.append((stage, active_mode, *trace))
    return values, tuple(traces)


def prepare(args: argparse.Namespace) -> tuple[
    list[PreparedRow], list[dict[str, str]], tuple[str, ...]
]:
    base, source_rows, _, _ = h1431.prepare(args)
    prepared = []
    names: tuple[str, ...] | None = None
    for item in base:
        values, trace = source_signals(item.row)
        if names is None:
            names = tuple(sorted(values))
        elif set(values) != set(names):
            raise RuntimeError("post-add signal schema changed")
        prepared.append(PreparedRow(
            row=item.row,
            current=item.current,
            required=item.required,
            target=item.target,
            signals=tuple(values[name] for name in names),
            trace=trace,
        ))
    if names is None:
        raise RuntimeError("no constraining rows")
    return prepared, source_rows, names


def gate_output(gate: int, current: int, signal: int) -> int:
    return (gate >> (2 * current + signal)) & 1


def collision_summary(prepared: list[PreparedRow]) -> tuple[list[tuple], int]:
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        key = (item.row["branch"], item.current, item.signals)
        groups[key][item.required].append(item)
    mixed = []
    target_count = 0
    for key, members in groups.items():
        if not members[0] or not members[1]:
            continue
        targets = [item for side in members for item in side if item.target]
        target_count += len(targets)
        mixed.append((
            key, len(members[0]), len(members[1]),
            tuple((item.row["mode"], item.row["op"]) for item in targets),
            (members[0][0].row["mode"], members[0][0].row["op"]),
            (members[1][0].row["mode"], members[1][0].row["op"]),
        ))
    return mixed, target_count


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

    prepared, source_rows, names = prepare(args)
    target_count = sum(item.target for item in prepared)
    control_count = len(prepared) - target_count
    ones = Counter()
    target_ones = Counter()
    ranking = []
    for signal_index, name in enumerate(names):
        ones[name] = sum(item.signals[signal_index] for item in prepared)
        target_ones[name] = sum(
            item.signals[signal_index] for item in prepared if item.target
        )
        for gate in range(16):
            counts = Counter()
            for item in prepared:
                output = gate_output(gate, item.current, item.signals[signal_index])
                wrong = output != item.required
                changed = output != item.current
                counts["errors"] += wrong
                counts["target_errors"] += wrong and item.target
                counts["control_errors"] += wrong and not item.target
                counts["control_changes"] += changed and not item.target
            ranking.append((
                counts["errors"], counts["target_errors"],
                counts["control_errors"], counts["control_changes"],
                GATE_NAMES[gate], gate, name,
            ))
    ranking.sort()
    exact = [item for item in ranking if item[0] == 0]
    improvements = [
        item for item in ranking if item[2] == 0 and item[1] < target_count
    ]
    mixed, collision_targets = collision_summary(prepared)

    matrix = np.asarray([item.signals for item in prepared], dtype=np.uint8)
    sequences = h1432.homologous_sequences(names, matrix)
    current = np.asarray([item.current for item in prepared], dtype=np.uint8)
    required = np.asarray([item.required for item in prepared], dtype=np.uint8)
    target = np.asarray([item.target for item in prepared], dtype=bool)
    one_input = h1432.one_input_recurrences(
        sequences, current, required, target
    )
    two_input = h1432.two_input_affine_recurrences(
        sequences, current, required, target
    )
    one_exact = [item for item in one_input if item[0] == 0]
    two_exact = [item for item in two_input if item[0] == 0]
    one_improvements = [
        item for item in one_input if item[2] == 0 and item[1] < target_count
    ]
    two_improvements = [
        item for item in two_input if item[2] == 0 and item[1] < target_count
    ]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
            ("h1431_reconstruction", Path(h1431.__file__)),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(f"primary_source\t{PATENT}\t{PATENT_URL}\n")
        output.write(
            "source_scope\tIntel_double_extended_embodiment_not_proved_"
            "Skylake_topology\n"
        )
        output.write(
            "candidate_policy\tliteral_postadd_result_select_LZD_normalizer_"
            "GRS_rounder_exponent_fix\n"
        )
        output.write("double_extended_projection\t68_to_64_G_R_S_fixed\n")
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"causal_arithmetic_stages\t{len(STAGES)}\n")
        output.write(f"postadd_signals\t{len(names)}\n")
        output.write(f"homologous_signal_streams\t{len(sequences)}\n")
        output.write(f"global_gate_programs\t{len(ranking)}\n")
        output.write(f"global_gate_exact\t{len(exact)}\n")
        output.write(
            "global_gate_zero_collateral_improvements\t"
            f"{len(improvements)}\n"
        )
        output.write(f"complete_history_mixed_groups\t{len(mixed)}\n")
        output.write(
            f"targets_in_complete_history_mixed_groups\t{collision_targets}\n"
        )
        output.write(f"one_input_recurrence_programs\t{len(one_input)}\n")
        output.write(f"one_input_recurrence_exact\t{len(one_exact)}\n")
        output.write(
            "one_input_recurrence_zero_collateral_improvements\t"
            f"{len(one_improvements)}\n"
        )
        output.write(f"two_input_affine_recurrence_programs\t{len(two_input)}\n")
        output.write(f"two_input_affine_recurrence_exact\t{len(two_exact)}\n")
        output.write(
            "two_input_affine_recurrence_zero_collateral_improvements\t"
            f"{len(two_improvements)}\n"
        )

        output.write("\n[signal distribution]\n")
        output.write("signal\tones\tzeros\ttarget_ones\ttarget_zeros\n")
        for name in names:
            output.write(
                f"{name}\t{ones[name]}\t{len(prepared) - ones[name]}\t"
                f"{target_ones[name]}\t{target_count - target_ones[name]}\n"
            )

        output.write("\n[global gate ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in ranking[:512]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[one-input recurrence ranking]\n")
        for item in one_input[:256]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[two-input affine recurrence ranking]\n")
        for item in two_input[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[complete-history mixed groups]\n")
        output.write(
            "branch\tcurrent\trequired0\trequired1\ttargets\texample0\t"
            "example1\n"
        )
        for key, count0, count1, targets, example0, example1 in mixed:
            branch, incumbent, _ = key
            target_text = ",".join(
                f"{mode}:{operand}" for mode, operand in targets
            )
            output.write(
                f"{branch}\t{incumbent}\t{count0}\t{count1}\t{target_text}\t"
                f"{example0[0]}:{example0[1]}\t{example1[0]}:{example1[1]}\n"
            )

        output.write("\n[target structural traces]\n")
        output.write("mode\top\tcurrent\trequired\tstage_traces\n")
        for item in prepared:
            if item.target:
                output.write(
                    f"{item.row['mode']}\t{item.row['op']}\t{item.current}\t"
                    f"{item.required}\t{item.trace!r}\n"
                )

        output.write("\n[result]\n")
        output.write(
            "complete_postadd_history\tcollision_free_lookup_fingerprint_only\n"
        )
        output.write("global_single_signal_selector\tno_exact_program\n")
        output.write("fixed_one_input_recurrence\tno_exact_program\n")
        output.write("fixed_two_input_affine_recurrence\tno_exact_program\n")

    print(
        f"wrote {args.report}: rows={len(prepared)} signals={len(names)} "
        f"gate_exact={len(exact)} one_exact={len(one_exact)} "
        f"two_exact={len(two_exact)} collision_targets={collision_targets}",
        flush=True,
    )


if __name__ == "__main__":
    main()
