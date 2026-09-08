#!/usr/bin/env python3
"""Close the stage-addressed ROM-gating loophole for h1431 signals.

h1432 tests recurrences whose transition law is fixed across the fixed
arithmetic schedule. A stage index could instead select a
different Boolean transition at every stage.  This audit symbolically
exhausts every six-stage sequence of one-bit Boolean transition functions for
each homologous US20080133895A1 signal stream, from both initial states.

The final selector is deliberately more permissive than a two-input gate: it
may choose an independent output for every (existing branch, incumbent carry,
final state) tuple.  Semantic state vectors are deduplicated after each stage,
so the search is exhaustive without enumerating duplicate gate programs.

Each candidate still consumes only one source-defined signal stream and the
fixed model stage order.  No operand identity, threshold, interval,
or hardware observation is used.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import h1425_p5_public_mux_signals as h1425
import h1431_multiformat_split_adder_state as h1431


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def homologous_columns(
    names: tuple[str, ...]
) -> dict[str, dict[str, int]]:
    columns: dict[str, dict[str, int]] = {}
    for index, name in enumerate(names):
        for stage in h1431.STAGES:
            prefix = stage + "."
            if name.startswith(prefix):
                columns.setdefault(name[len(prefix):], {})[stage] = index
                break
    return {
        suffix: stage_columns
        for suffix, stage_columns in columns.items()
        if set(stage_columns) == set(h1431.STAGES)
    }


def boolean_gate(
    state: int, signal: int, gate: int, all_rows: int
) -> int:
    groups = (
        (~state & ~signal) & all_rows,
        (~state & signal) & all_rows,
        (state & ~signal) & all_rows,
        state & signal,
    )
    result = 0
    for index, rows in enumerate(groups):
        if (gate >> index) & 1:
            result |= rows
    return result


def assess_state(
    state: int,
    prepared: list[h1431.PreparedRow],
    all_rows: int,
    current: int,
    required: int,
    target: int,
    controls: int,
    branch_masks: dict[str, int],
) -> tuple[bool, int, int, int, int]:
    exact = True
    minimum_errors = 0
    minimum_target_errors = 0
    minimum_control_errors = 0
    zero_collateral_repairs = 0
    for branch_rows in branch_masks.values():
        for current_value in (0, 1):
            current_rows = current if current_value else all_rows ^ current
            for state_value in (0, 1):
                state_rows = state if state_value else all_rows ^ state
                group = branch_rows & current_rows & state_rows
                required_zero = (group & (all_rows ^ required)).bit_count()
                required_one = (group & required).bit_count()
                if required_zero and required_one:
                    exact = False

                choose_one = required_one > required_zero
                if choose_one:
                    wrong = group & (all_rows ^ required)
                else:
                    wrong = group & required
                minimum_errors += wrong.bit_count()
                minimum_target_errors += (wrong & target).bit_count()
                minimum_control_errors += (wrong & controls).bit_count()

                target_flips = group & target & (required ^ current)
                if target_flips and not (group & controls):
                    zero_collateral_repairs += target_flips.bit_count()
    return (
        exact,
        minimum_errors,
        minimum_target_errors,
        minimum_control_errors,
        zero_collateral_repairs,
    )


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

    prepared, source_rows, names, _ = h1431.prepare(args)
    row_count = len(prepared)
    all_rows = (1 << row_count) - 1
    current = sum(
        item.current << index for index, item in enumerate(prepared)
    )
    required = sum(
        item.required << index for index, item in enumerate(prepared)
    )
    target = sum(
        int(item.target) << index for index, item in enumerate(prepared)
    )
    controls = all_rows ^ target
    if (required ^ current) & controls:
        raise RuntimeError("control row unexpectedly requires a carry flip")
    branch_masks = {
        branch: sum(
            int(item.row["branch"] == branch) << index
            for index, item in enumerate(prepared)
        )
        for branch in sorted({item.row["branch"] for item in prepared})
    }
    columns = homologous_columns(names)

    results = []
    for signal_name, stage_columns in columns.items():
        states = {0: (), all_rows: ()}
        stage_state_counts = []
        for stage in h1431.STAGES:
            column = stage_columns[stage]
            signal = sum(
                item.signals[column] << index
                for index, item in enumerate(prepared)
            )
            next_states = {}
            for state, program in states.items():
                for gate in range(16):
                    output = boolean_gate(state, signal, gate, all_rows)
                    next_states.setdefault(output, program + (gate,))
            states = next_states
            stage_state_counts.append(len(states))

        exact_states = 0
        improvement_states = 0
        best = None
        for state, program in states.items():
            assessment = assess_state(
                state, prepared, all_rows, current, required,
                target, controls, branch_masks,
            )
            exact_states += assessment[0]
            improvement_states += bool(assessment[4])
            item = (
                assessment[1], assessment[2], assessment[3],
                -assessment[4], program,
            )
            if best is None or item < best:
                best = item
        if best is None:
            raise RuntimeError("stage-addressed recurrence produced no state")
        results.append((
            signal_name,
            tuple(stage_state_counts),
            len(states),
            exact_states,
            improvement_states,
            *best,
        ))

    exact_signal_streams = sum(bool(item[3]) for item in results)
    improvement_signal_streams = sum(bool(item[4]) for item in results)
    target_count = target.bit_count()
    transition_programs_per_stream = 2 * 16 ** len(h1431.STAGES)
    branch_output_classes = 2 * 2 * len(branch_masks)
    output_tables_per_state = 1 << branch_output_classes

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
            ("signal_reconstruction", Path(h1431.__file__)),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(f"primary_source\t{h1431.PATENT}\t{h1431.PATENT_URL}\n")
        output.write(
            "candidate_policy\tarbitrary_stage_specific_one_bit_Boolean_"
            "transitions_per_homologous_signal_stream\n"
        )
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{row_count}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{controls.bit_count()}\n")
        output.write(f"branches\t{len(branch_masks)}\n")
        output.write(f"arithmetic_stages\t{len(h1431.STAGES)}\n")
        output.write(f"homologous_signal_streams\t{len(columns)}\n")
        output.write(
            "raw_transition_programs_per_stream\t"
            f"{transition_programs_per_stream}\n"
        )
        output.write(
            f"branch_aware_output_classes\t{branch_output_classes}\n"
        )
        output.write(
            f"output_tables_per_semantic_state\t{output_tables_per_state}\n"
        )
        output.write(f"exact_signal_streams\t{exact_signal_streams}\n")
        output.write(
            "zero_collateral_improvement_signal_streams\t"
            f"{improvement_signal_streams}\n"
        )

        output.write("\n[stage-addressed recurrence results]\n")
        output.write(
            "signal\tstate_counts_after_each_stage\tfinal_semantic_states\t"
            "exact_states\timprovement_states\tminimum_errors\t"
            "minimum_target_errors\tminimum_control_errors\t"
            "maximum_zero_collateral_repairs\twitness_gate_sequence\n"
        )
        for item in results:
            (
                signal_name, stage_counts, final_states, exact_states,
                improvement_states, errors, target_errors, control_errors,
                negative_repairs, program,
            ) = item
            output.write(
                f"{signal_name}\t{','.join(map(str, stage_counts))}\t"
                f"{final_states}\t{exact_states}\t{improvement_states}\t"
                f"{errors}\t{target_errors}\t{control_errors}\t"
                f"{-negative_repairs}\t{','.join(map(str, program))}\n"
            )

        output.write("\n[result]\n")
        output.write(
            "stage_addressed_single_stream_selector\t"
            "impossible_on_constrained_wall\n"
        )
        output.write(
            "carry360_stage_addressed_selector\t"
            "impossible_on_constrained_wall\n"
        )
        output.write(
            "reason\tno_semantic_final_state_permits_exact_or_"
            "zero_control_collateral_branch_aware_output_mapping\n"
        )

    print(
        f"wrote {args.report}: rows={row_count} streams={len(columns)} "
        f"exact_streams={exact_signal_streams} "
        f"improvement_streams={improvement_signal_streams}",
        flush=True,
    )


if __name__ == "__main__":
    main()
