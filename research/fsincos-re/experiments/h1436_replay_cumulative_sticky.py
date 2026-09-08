#!/usr/bin/env python3
"""Audit a replay-style cumulative sticky stream at the R59 selector.

VIA US20090259708A1 describes an x87 replay path that preserves a cumulative
sticky bit formed from aligned operand bits below the 64-bit intermediate
format.  This audit reconstructs that literal per-operation input at the four
causal Horner FADDs, terminal ``_FSUB``, and final ``FINAL_ADD``.  It scores
all fixed two-input gates with the incumbent R59 carry and every fixed
one-bit state recurrence driven by the six-stage sticky stream.

The source establishes that this state is physically plausible in one x87
implementation.  It is VIA, not Intel, and is not evidence that Skylake uses
the mechanism.  All labels are cached; no x87 instruction is executed, and
there are no operand identities, thresholds, tables, or branch-local rules.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np

import h1431_multiformat_split_adder_state as h1431
import h1432_multiformat_split_adder_logic as h1432
import h206_p5_fadd_complete as h206
from h1110_carry_gate_mine import GATE_NAMES


PATENT = "US20090259708A1"
PATENT_URL = "https://patents.google.com/patent/US20090259708A1/en"
LOW64_DISCARDED_MASK = (1 << 3) - 1


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def operation_sticky(left, right) -> int:
    exponent = max(left.exponent, right.exponent)
    left_aligned, left_tail = h206.h200.shift_right(
        left.word, exponent - left.exponent
    )
    right_aligned, right_tail = h206.h200.shift_right(
        right.word, exponent - right.exponent
    )
    return int(bool(
        (left_aligned & LOW64_DISCARDED_MASK)
        or (right_aligned & LOW64_DISCARDED_MASK)
        or left_tail
        or right_tail
    ))


def sticky_trace(row: dict[str, str]) -> tuple[int, ...]:
    inputs = h1431.stage_inputs(row)
    if tuple(inputs) != h1431.STAGES:
        raise RuntimeError("arithmetic stage order changed")
    return tuple(operation_sticky(*inputs[stage]) for stage in h1431.STAGES)


def gate_output(gate: int, current: int, signal: int) -> int:
    return (gate >> (2 * current + signal)) & 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default=h1431.h1425.EXTRA_OP)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    prepared, source_rows, _, _ = h1431.prepare(args)
    traces = [sticky_trace(item.row) for item in prepared]
    target_count = sum(item.target for item in prepared)
    control_count = len(prepared) - target_count
    current = np.asarray(
        [item.current for item in prepared], dtype=np.uint8
    )
    required = np.asarray(
        [item.required for item in prepared], dtype=np.uint8
    )
    target = np.asarray([item.target for item in prepared], dtype=bool)

    sequence = tuple(
        np.asarray([trace[index] for trace in traces], dtype=np.uint8)
        for index in range(len(h1431.STAGES))
    )
    recurrences = h1432.one_input_recurrences(
        {"cumulative_sticky64": sequence},
        current,
        required,
        target,
    )
    recurrence_exact = [item for item in recurrences if item[0] == 0]
    recurrence_improvements = [
        item for item in recurrences
        if item[2] == 0 and item[1] < target_count
    ]

    signal_names = tuple(h1431.STAGES) + ("or_all_stages",)
    gate_ranking = []
    distributions = []
    for signal_index, name in enumerate(signal_names):
        if signal_index < len(h1431.STAGES):
            signal = [trace[signal_index] for trace in traces]
        else:
            signal = [int(any(trace)) for trace in traces]
        ones = sum(signal)
        target_ones = sum(
            value for value, item in zip(signal, prepared) if item.target
        )
        distributions.append((name, ones, len(signal) - ones,
                              target_ones, target_count - target_ones))
        for gate in range(16):
            counts = Counter()
            for value, item in zip(signal, prepared):
                output = gate_output(gate, item.current, value)
                wrong = output != item.required
                changed = output != item.current
                counts["errors"] += wrong
                counts["target_errors"] += wrong and item.target
                counts["control_errors"] += wrong and not item.target
                counts["control_changes"] += changed and not item.target
            gate_ranking.append((
                counts["errors"],
                counts["target_errors"],
                counts["control_errors"],
                counts["control_changes"],
                GATE_NAMES[gate],
                gate,
                name,
            ))
    gate_ranking.sort()
    gate_exact = [item for item in gate_ranking if item[0] == 0]
    gate_improvements = [
        item for item in gate_ranking
        if item[2] == 0 and item[1] < target_count
    ]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("software_model", args.model),
            ("misses", args.misses),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write(f"source_patent\t{PATENT}\n")
        output.write(f"source_url\t{PATENT_URL}\n")
        output.write("source_vendor\tVIA_Technologies\n")
        output.write(
            "source_boundary\tx87_physical_plausibility_not_Intel_or_"
            "Skylake_provenance\n"
        )
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write(
            "signal_policy\tOR_of_aligned_bits_below_64bit_intermediate_"
            "plus_shifted_tail\n"
        )
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"arithmetic_stages\t{len(h1431.STAGES)}\n")
        output.write(f"global_gate_programs\t{len(gate_ranking)}\n")
        output.write(f"global_gate_exact\t{len(gate_exact)}\n")
        output.write(
            f"global_gate_zero_control_improvements\t{len(gate_improvements)}\n"
        )
        output.write(f"fixed_recurrence_programs\t{len(recurrences)}\n")
        output.write(f"fixed_recurrence_exact\t{len(recurrence_exact)}\n")
        output.write(
            "fixed_recurrence_zero_control_improvements\t"
            f"{len(recurrence_improvements)}\n"
        )

        output.write("\n[signal distribution]\n")
        output.write("signal\tones\tzeros\ttarget_ones\ttarget_zeros\n")
        for item in distributions:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best global gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in gate_ranking[:64]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best fixed recurrences]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tsignal\tinitial\t"
            "transition_mask\ttransition\toutput_mask\toutput\tstate_ones\t"
            "target_state_ones\n"
        )
        for item in recurrences[:64]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-error programs]\n")
        if gate_exact or recurrence_exact:
            for item in gate_exact:
                output.write("gate\t" + "\t".join(map(str, item)) + "\n")
            for item in recurrence_exact:
                output.write(
                    "recurrence\t" + "\t".join(map(str, item)) + "\n"
                )
        else:
            output.write("none\n")

        output.write("\n[target sticky traces]\n")
        output.write("mode\top\tcurrent\trequired\ttrace\n")
        for item, trace in zip(prepared, traces):
            if item.target:
                output.write(
                    f"{item.row['mode']}\t{item.row['op']}\t{item.current}\t"
                    f"{item.required}\t{''.join(map(str, trace))}\n"
                )

        output.write("\n[result]\n")
        output.write("replay_cumulative_sticky_selector\trejected\n")
        output.write(
            "reason\tno_global_gate_or_fixed_recurrence_is_exact_and_none_"
            "repairs_a_target_at_zero_control_collateral\n"
        )

    print(
        f"wrote {args.report}: rows={len(prepared)} "
        f"gate_exact={len(gate_exact)} recurrence_exact={len(recurrence_exact)} "
        f"improvements={len(gate_improvements) + len(recurrence_improvements)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
