#!/usr/bin/env python3
"""Audit Intel's published 32+36-bit extended-FADD split at R59.

Intel US20080133895A1 describes a multi-format floating-point adder whose
double-extended mantissa path combines an MS 32-bit slice with an LS 36-bit
slice.  The low adder's carry-out (signal 360) is the high adder's carry-in.
The same embodiment exposes five-bit alignment shift codes, separate high and
low complement controls, shifted-tail sticky, a high-adder result selection,
and a rounder add-one used to finish two's complementation of a negative
subtraction result.

This is a source-defined structural family, not an operand-boundary fit.  The
signals are reconstructed at the four causal Horner FADDs, the terminal
``_FSUB``, and the final ``FINAL_ADD`` addition.  Every global two-input
Boolean composition with the incumbent R59 carry is scored.  More strongly,
rows are grouped by branch, incumbent carry, and the complete joint history
of h1425's public mux signals, h1427's P5 rounder signals, h1430's P6 rounder
slice carries, and the signals introduced here.  Opposite-label collisions
in that tuple rule out every deterministic selector driven only by this
combined public family, not merely the enumerated gates.

The patent is an Intel embodiment that includes double-extended precision;
it is not proof that Skylake's transcendental microcode uses this exact
physical adder.  Only controls and slice outputs stated by the source are
modeled.  Finer unnamed internal gates are outside the claim.  All labels are
immutable cached data, and no x87 instruction is executed.
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
import h1427_p5_fadd_rounder_signals as h1427
import h206_p5_fadd_complete as h206
from h1110_carry_gate_mine import GATE_NAMES


PATENT = "US20080133895A1"
PATENT_URL = "https://patents.google.com/patent/US20080133895A1/en"
STAGES = (*h1427.FADD_STAGES, "terminal_fsub", "final_add")
WIDTH = 68
LOW_WIDTH = 36
HIGH_WIDTH = 32
MASK68 = (1 << WIDTH) - 1
MASK36 = (1 << LOW_WIDTH) - 1
MASK32 = (1 << HIGH_WIDTH) - 1
LOW11_MASK = (1 << 11) - 1
LOW40_MASK = (1 << 40) - 1


@dataclass(frozen=True)
class PreparedRow:
    row: dict[str, str]
    current: int
    required: int
    target: bool
    signals: tuple[int, ...]
    combined: tuple[int, ...]
    trace: tuple[tuple[object, ...], ...]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def to_bus(value) -> h206.Bus:
    return h1415.to_bus(value)


def split_signals(
    left: h206.Bus, right: h206.Bus
) -> tuple[dict[str, int], tuple[object, ...]]:
    """Reconstruct the literal extended-format split-adder controls."""
    if not left.word or not right.word:
        raise RuntimeError("split-adder audit requires two nonzero operands")
    if left.word.bit_length() > 67 or right.word.bit_length() > 67:
        raise RuntimeError("input exceeds normalized 68-bit extended format")

    exponent = max(left.exponent, right.exponent)
    left_aligned, left_tail = h206.h200.shift_right(
        left.word, exponent - left.exponent
    )
    right_aligned, right_tail = h206.h200.shift_right(
        right.word, exponent - right.exponent
    )
    big = max(left_aligned, right_aligned)
    small = min(left_aligned, right_aligned)
    subtract = int(left.sign != right.sign)

    # Paragraph 21 complements the larger/equal-exponent mantissa for true
    # subtraction and supplies Compl_Lo as the low adder's carry-in.  For
    # double/double-extended operation signal 360 then chains LS36 into MS32.
    first = ((~big) & MASK68) if subtract else big
    second = small
    low_total = (first & MASK36) + (second & MASK36) + subtract
    carry360 = low_total >> LOW_WIDTH
    high_total = (first >> LOW_WIDTH) + (second >> LOW_WIDTH) + carry360
    high_carry = high_total >> HIGH_WIDTH
    raw = ((high_total & MASK32) << LOW_WIDTH) | (low_total & MASK36)

    if subtract:
        difference = big - small
        expected_raw = (-difference) & MASK68
        if raw != expected_raw:
            raise RuntimeError("split subtraction does not reconstruct")
        negative_select = int(bool(difference))
        restored = ((~raw) + 1) & MASK68 if negative_select else raw
        if restored != difference:
            raise RuntimeError("rounder-assisted two's complement mismatch")
    else:
        expected = big + small
        if expected >= 1 << WIDTH or raw != expected:
            raise RuntimeError("split addition does not reconstruct")
        negative_select = 0

    distance = abs(left.exponent - right.exponent)
    values = {
        "align.lt32": int(distance < 32),
        "align.ge32_lt64": int(32 <= distance < 64),
        "align.ge64": int(distance >= 64),
        "align.shifted_tail_sticky": int(left_tail or right_tail),
        "compl_hi": subtract,
        "compl_lo": subtract,
        "low36.carry360": int(carry360),
        "high32.carryout": int(high_carry),
        "high32.result_msb": (raw >> 67) & 1,
        "high32.negative_select": negative_select,
        "rounder.twos_complement_addone": negative_select,
    }
    for bit in range(5):
        values[f"align.shift_code_bit{bit}"] = (distance >> bit) & 1

    trace = (
        distance,
        int(left_tail or right_tail),
        subtract,
        int(carry360),
        int(high_carry),
        (raw >> 67) & 1,
        negative_select,
    )
    return values, trace


def stage_inputs(row: dict[str, str]) -> dict[str, tuple[h206.Bus, h206.Bus]]:
    result = {
        stage: (to_bus(pair[0]), to_bus(pair[1]))
        for stage, pair in h1427.fadd_inputs(row).items()
    }
    result["terminal_fsub"] = (
        to_bus(h1415.row_value(row, "left")),
        to_bus(h1415.row_value(row, "right")),
    )
    result["final_add"] = (
        h206.h200.normalized_bus((0, 1, 0)),
        h1424.incumbent_bus(row),
    )
    if tuple(result) != STAGES:
        raise RuntimeError("split-adder stage order changed")
    return result


def source_signals(
    row: dict[str, str]
) -> tuple[dict[str, int], tuple[tuple[object, ...], ...]]:
    values: dict[str, int] = {}
    traces = []
    for stage, pair in stage_inputs(row).items():
        local, trace = split_signals(*pair)
        values.update({f"{stage}.{name}": value for name, value in local.items()})
        traces.append((stage, *trace))
    return values, tuple(traces)


def h1430_slice_history(
    traces: tuple[tuple[int, ...], ...]
) -> tuple[int, ...]:
    values = []
    for trace in traces:
        retained = trace[3]
        round_increment = trace[4]
        carry11 = int(
            bool(round_increment) and (retained & LOW11_MASK) == LOW11_MASK
        )
        carry40 = int(
            bool(round_increment) and (retained & LOW40_MASK) == LOW40_MASK
        )
        values.extend((carry11, carry40))
    return tuple(values)


def prepare(args: argparse.Namespace) -> tuple[
    list[PreparedRow], list[dict[str, str]], tuple[str, ...], tuple[str, ...]
]:
    base, rows, base_names, _ = h1425.prepare(args)
    prepared = []
    names: tuple[str, ...] | None = None
    rounder_names: tuple[str, ...] | None = None
    for item in base:
        values, trace = source_signals(item.row)
        rounder, rounder_trace = h1427.rounder_signals(item.row)
        if names is None:
            names = tuple(sorted(values))
            rounder_names = tuple(sorted(rounder))
        elif set(values) != set(names) or set(rounder) != set(rounder_names or ()):
            raise RuntimeError("public signal schema changed")
        local = tuple(values[name] for name in names)
        inherited = (
            item.signals
            + tuple(rounder[name] for name in rounder_names or ())
            + h1430_slice_history(rounder_trace)
        )
        prepared.append(PreparedRow(
            row=item.row,
            current=item.current,
            required=item.required,
            target=item.target,
            signals=local,
            combined=inherited + local,
            trace=trace,
        ))
    if names is None or rounder_names is None:
        raise RuntimeError("no constraining split-adder rows")
    inherited_names = (
        base_names
        + rounder_names
        + tuple(
            f"{stage}.{signal}"
            for stage in h1427.FADD_STAGES
            for signal in ("carry11", "carry40")
        )
    )
    return prepared, rows, names, inherited_names


def gate_output(gate: int, current: int, signal: int) -> int:
    return (gate >> (2 * current + signal)) & 1


def collision_summary(
    prepared: list[PreparedRow], combined: bool
) -> tuple[list[tuple], int]:
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        history = item.combined if combined else item.signals
        key = (item.row["branch"], item.current, history)
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

    prepared, source_rows, names, inherited_names = prepare(args)
    target_count = sum(item.target for item in prepared)
    control_count = len(prepared) - target_count
    ranking = []
    ones = Counter()
    target_ones = Counter()
    for signal_index, name in enumerate(names):
        ones[name] = sum(item.signals[signal_index] for item in prepared)
        target_ones[name] = sum(
            item.signals[signal_index] for item in prepared if item.target
        )
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
                counts["errors"], counts["target_errors"],
                counts["control_errors"], counts["control_changes"],
                GATE_NAMES[gate], gate, name,
            ))
    ranking.sort()
    exact = [item for item in ranking if item[0] == 0]
    improvements = [
        item for item in ranking
        if item[2] == 0 and item[1] < target_count
    ]
    local_mixed, local_targets = collision_summary(prepared, combined=False)
    combined_mixed, combined_targets = collision_summary(prepared, combined=True)

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
            "source_scope\tIntel_double_extended_embodiment_not_proved_"
            "Skylake_topology\n"
        )
        output.write(
            "candidate_policy\tliteral_68bit_MS32_LS36_split_adder_"
            "controls_and_carry360\n"
        )
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"causal_arithmetic_stages\t{len(STAGES)}\n")
        output.write(f"split_adder_signals\t{len(names)}\n")
        output.write(f"inherited_public_signals\t{len(inherited_names)}\n")
        output.write(f"combined_public_signals\t{len(inherited_names) + len(names)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(improvements)}\n"
        )
        output.write(f"local_history_mixed_groups\t{len(local_mixed)}\n")
        output.write(f"targets_in_local_history_mixed_groups\t{local_targets}\n")
        output.write(f"combined_history_mixed_groups\t{len(combined_mixed)}\n")
        output.write(
            f"targets_in_combined_history_mixed_groups\t{combined_targets}\n"
        )

        output.write("\n[split-adder signal distribution]\n")
        output.write("signal\tones\tzeros\ttarget_ones\ttarget_zeros\n")
        for name in names:
            output.write(
                f"{name}\t{ones[name]}\t{len(prepared) - ones[name]}\t"
                f"{target_ones[name]}\t{target_count - target_ones[name]}\n"
            )

        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in ranking:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-control-collateral improvements]\n")
        for item in improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-error programs]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[combined-history mixed groups]\n")
        output.write(
            "branch\tcurrent\trequired0\trequired1\ttargets\t"
            "example0\texample1\n"
        )
        for key, count0, count1, targets, example0, example1 in combined_mixed:
            branch, current, _ = key
            target_text = ",".join(
                f"{mode}:{operand}" for mode, operand in targets
            )
            output.write(
                f"{branch}\t{current}\t{count0}\t{count1}\t{target_text}\t"
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
        output.write("multiformat_split_adder_selector\timpossible_on_constrained_wall\n")
        output.write(
            "reason\topposite_required_carries_share_branch_current_carry_"
            "and_complete_combined_public_signal_history\n"
        )

    print(
        f"wrote {args.report}: rows={len(prepared)} signals={len(names)} "
        f"exact={len(exact)} improvements={len(improvements)} "
        f"combined_collision_targets={combined_targets}",
        flush=True,
    )


if __name__ == "__main__":
    main()
