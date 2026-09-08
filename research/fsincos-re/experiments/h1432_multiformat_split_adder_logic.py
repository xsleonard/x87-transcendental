#!/usr/bin/env python3
"""Test whether h1431's collision-free fingerprints form a small law.

h1431 reconstructs Intel US20080133895A1's 68-bit double-extended FADD as
MS32 and LS36 slices and adds those literal controls/carries to the earlier
public signal bank.  The resulting full tuples happen to be collision-free,
so an arbitrary lookup table can label the frozen rows.  Collision freedom is
not a closed-form mechanism.

This audit tests bounded, hardware-plausible interpretations of that apparent
separation:

* every fixed one-bit state recurrence driven by one homologous signal stream;
* every fixed one-bit affine recurrence driven by two homologous streams;
* every affine and every quadratic algebraic-normal-form selector over the
  incumbent carry and all unique varying public signals; and
* every conjunction of up to four public-signal literals.

The recurrence is shared across all six arithmetic stages, and every selector
is global.  There are no operand identities, numeric thresholds, interval
boundaries, branch-local programs, or hardware execution.  The purpose is to
distinguish a compact structural rule from a high-dimensional fitted table.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np

import h1425_p5_public_mux_signals as h1425
import h1431_multiformat_split_adder_state as h1431
from h1110_carry_gate_mine import GATE_NAMES


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def homologous_sequences(
    names: tuple[str, ...], matrix: np.ndarray
) -> dict[str, tuple[np.ndarray, ...]]:
    columns: dict[str, dict[str, int]] = {}
    for index, name in enumerate(names):
        for stage in h1431.STAGES:
            prefix = stage + "."
            if name.startswith(prefix):
                columns.setdefault(name[len(prefix):], {})[stage] = index
                break
    return {
        suffix: tuple(matrix[:, stage_columns[stage]] for stage in h1431.STAGES)
        for suffix, stage_columns in columns.items()
        if set(stage_columns) == set(h1431.STAGES)
    }


def score_prediction(
    prediction: np.ndarray,
    required: np.ndarray,
    target: np.ndarray,
) -> tuple[int, int, int]:
    wrong = prediction != required
    return (
        int(wrong.sum()),
        int(wrong[target].sum()),
        int(wrong[~target].sum()),
    )


def one_input_recurrences(
    sequences: dict[str, tuple[np.ndarray, ...]],
    current: np.ndarray,
    required: np.ndarray,
    target: np.ndarray,
) -> list[tuple]:
    ranking = []
    for name, sequence in sequences.items():
        for initial in (0, 1):
            for transition in range(16):
                state = np.full(len(current), initial, dtype=np.uint8)
                for signal in sequence:
                    state = (
                        (transition >> (2 * state + signal)) & 1
                    ).astype(np.uint8)
                for output_gate in range(16):
                    prediction = (
                        (output_gate >> (2 * current + state)) & 1
                    ).astype(np.uint8)
                    score = score_prediction(
                        prediction, required, target
                    )
                    ranking.append((
                        *score, name, initial, transition,
                        GATE_NAMES[transition], output_gate,
                        GATE_NAMES[output_gate], int(state.sum()),
                        int(state[target].sum()),
                    ))
    ranking.sort()
    return ranking


def two_input_affine_recurrences(
    sequences: dict[str, tuple[np.ndarray, ...]],
    current: np.ndarray,
    required: np.ndarray,
    target: np.ndarray,
) -> list[tuple]:
    ranking = []
    for (left_name, left), (right_name, right) in combinations(
        sequences.items(), 2
    ):
        for initial in (0, 1):
            # coefficient bits are constant, old-state, left, and right.
            for coefficients in range(16):
                constant = coefficients & 1
                use_state = (coefficients >> 1) & 1
                use_left = (coefficients >> 2) & 1
                use_right = (coefficients >> 3) & 1
                state = np.full(len(current), initial, dtype=np.uint8)
                for left_signal, right_signal in zip(left, right):
                    state = (
                        constant
                        ^ (use_state & state)
                        ^ (use_left & left_signal)
                        ^ (use_right & right_signal)
                    )
                for output_gate in range(16):
                    prediction = (
                        (output_gate >> (2 * current + state)) & 1
                    ).astype(np.uint8)
                    score = score_prediction(
                        prediction, required, target
                    )
                    ranking.append((
                        *score, left_name, right_name, initial,
                        coefficients, output_gate, GATE_NAMES[output_gate],
                        int(state.sum()), int(state[target].sum()),
                    ))
    ranking.sort()
    return ranking


def unique_varying_variables(
    prepared: list[h1431.PreparedRow], combined_names: tuple[str, ...]
) -> tuple[list[str], list[list[int]], list[int]]:
    row_count = len(prepared)
    all_rows = (1 << row_count) - 1
    candidates = [
        ("incumbent_carry", [item.current for item in prepared])
    ]
    candidates.extend(
        (
            name,
            [item.combined[index] for item in prepared],
        )
        for index, name in enumerate(combined_names)
    )

    names = []
    values = []
    bitsets = []
    seen = set()
    for name, column in candidates:
        bits = sum(value << index for index, value in enumerate(column))
        if not bits or bits == all_rows or bits in seen:
            continue
        seen.add(bits)
        names.append(name)
        values.append(column)
        bitsets.append(bits)
    return names, values, bitsets


def anf_system(
    prepared: list[h1431.PreparedRow],
    variables: list[list[int]],
    degree: int,
) -> tuple[int, int | None, int]:
    """Return GF(2) rank, first contradiction witness, and monomial count."""
    variable_count = len(variables)
    if degree == 1:
        monomial_count = 1 + variable_count
    elif degree == 2:
        monomial_count = (
            1 + variable_count + variable_count * (variable_count - 1) // 2
        )
    else:
        raise ValueError(degree)

    basis: dict[int, tuple[int, int, int]] = {}
    contradiction = None
    for row_index, item in enumerate(prepared):
        active = [
            index for index, column in enumerate(variables)
            if column[row_index]
        ]
        equation = 1
        for index in active:
            equation |= 1 << (1 + index)
        if degree == 2:
            pair_base = 1 + variable_count
            for active_index, left in enumerate(active):
                for right in active[active_index + 1:]:
                    pair_index = (
                        left * (2 * variable_count - left - 1) // 2
                        + (right - left - 1)
                    )
                    equation |= 1 << (pair_base + pair_index)

        rhs = item.required
        witness = 1 << row_index
        while equation:
            pivot = equation.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = (equation, rhs, witness)
                break
            old_equation, old_rhs, old_witness = basis[pivot]
            equation ^= old_equation
            rhs ^= old_rhs
            witness ^= old_witness
        else:
            if rhs:
                contradiction = witness
                break
    return len(basis), contradiction, monomial_count


def low_order_minterms(
    prepared: list[h1431.PreparedRow],
    variable_names: list[str],
    variable_bitsets: list[int],
    maximum_order: int,
) -> list[tuple[int, int, int, tuple[str, ...] | None]]:
    row_count = len(prepared)
    all_rows = (1 << row_count) - 1
    target_rows = sum(
        1 << index for index, item in enumerate(prepared) if item.target
    )
    control_rows = all_rows ^ target_rows
    literals = []
    for name, bits in zip(variable_names, variable_bitsets):
        literals.extend(((name + "=1", bits), (name + "=0", all_rows ^ bits)))

    result = []
    for order in range(1, maximum_order + 1):
        count = 0
        best_coverage = 0
        best_clause = None
        for clause in combinations(literals, order):
            selected = all_rows
            for _, bits in clause:
                selected &= bits
            target_coverage = (selected & target_rows).bit_count()
            if not target_coverage or selected & control_rows:
                continue
            count += 1
            if target_coverage > best_coverage:
                best_coverage = target_coverage
                best_clause = tuple(name for name, _ in clause)
        result.append((order, count, best_coverage, best_clause))
    return result


def witness_rows(
    witness: int | None, prepared: list[h1431.PreparedRow]
) -> list[tuple[str, str, int, int, int]]:
    if witness is None:
        return []
    return [
        (
            item.row["mode"], item.row["op"], item.current,
            item.required, int(item.target),
        )
        for index, item in enumerate(prepared)
        if (witness >> index) & 1
    ]


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

    prepared, source_rows, names, inherited_names = h1431.prepare(args)
    target_count = sum(item.target for item in prepared)
    current = np.asarray(
        [item.current for item in prepared], dtype=np.uint8
    )
    required = np.asarray(
        [item.required for item in prepared], dtype=np.uint8
    )
    target = np.asarray(
        [item.target for item in prepared], dtype=bool
    )
    matrix = np.asarray(
        [item.signals for item in prepared], dtype=np.uint8
    )
    sequences = homologous_sequences(names, matrix)

    one_input = one_input_recurrences(
        sequences, current, required, target
    )
    two_input = two_input_affine_recurrences(
        sequences, current, required, target
    )
    one_exact = [item for item in one_input if item[0] == 0]
    two_exact = [item for item in two_input if item[0] == 0]
    one_improvements = [
        item for item in one_input
        if item[2] == 0 and item[1] < target_count
    ]
    two_improvements = [
        item for item in two_input
        if item[2] == 0 and item[1] < target_count
    ]

    combined_names = inherited_names + names
    variable_names, variables, variable_bitsets = unique_varying_variables(
        prepared, combined_names
    )
    affine_rank, affine_witness, affine_monomials = anf_system(
        prepared, variables, 1
    )
    quadratic_rank, quadratic_witness, quadratic_monomials = anf_system(
        prepared, variables, 2
    )
    clauses = low_order_minterms(
        prepared, variable_names, variable_bitsets, 4
    )
    combined_mixed, combined_collision_targets = h1431.collision_summary(
        prepared, combined=True
    )
    affine_rows = witness_rows(affine_witness, prepared)
    quadratic_rows = witness_rows(quadratic_witness, prepared)

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
            "candidate_policy\tfixed_recurrences_low_degree_ANF_and_"
            "low_order_conjunctions_only\n"
        )
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{len(prepared) - target_count}\n")
        output.write(f"homologous_signal_streams\t{len(sequences)}\n")
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
        output.write(f"unique_varying_public_variables\t{len(variables)}\n")
        output.write(f"affine_monomials\t{affine_monomials}\n")
        output.write(f"affine_rank_before_contradiction\t{affine_rank}\n")
        output.write(f"affine_exact\t{int(affine_witness is None)}\n")
        output.write(
            f"affine_contradiction_rows\t{len(affine_rows)}\n"
        )
        output.write(f"quadratic_monomials\t{quadratic_monomials}\n")
        output.write(
            f"quadratic_rank_before_contradiction\t{quadratic_rank}\n"
        )
        output.write(f"quadratic_exact\t{int(quadratic_witness is None)}\n")
        output.write(
            f"quadratic_contradiction_rows\t{len(quadratic_rows)}\n"
        )
        output.write("literal_conjunction_maximum_order\t4\n")
        output.write(
            "zero_collateral_literal_conjunctions\t"
            f"{sum(item[1] for item in clauses)}\n"
        )
        output.write(f"combined_history_mixed_groups\t{len(combined_mixed)}\n")
        output.write(
            "targets_in_combined_history_mixed_groups\t"
            f"{combined_collision_targets}\n"
        )

        output.write("\n[one-input recurrence ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tsignal\tinitial\t"
            "transition_mask\ttransition\toutput_mask\toutput\tstate_ones\t"
            "target_state_ones\n"
        )
        for item in one_input[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[two-input affine recurrence ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tleft\tright\tinitial\t"
            "affine_coefficients\toutput_mask\toutput\tstate_ones\t"
            "target_state_ones\n"
        )
        for item in two_input[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[low-order literal conjunctions]\n")
        output.write(
            "order\tzero_collateral_clauses\tbest_target_coverage\t"
            "example_clause\n"
        )
        for order, count, coverage, clause in clauses:
            output.write(
                f"{order}\t{count}\t{coverage}\t"
                f"{'' if clause is None else ','.join(clause)}\n"
            )

        output.write("\n[affine contradiction witness]\n")
        output.write("mode\top\tcurrent\trequired\ttarget\n")
        for row in affine_rows:
            output.write("\t".join(map(str, row)) + "\n")

        output.write("\n[quadratic contradiction witness summary]\n")
        output.write("mode\top\tcurrent\trequired\ttarget\n")
        for row in quadratic_rows[:24]:
            output.write("\t".join(map(str, row)) + "\n")
        if len(quadratic_rows) > 24:
            output.write(f"...\t{len(quadratic_rows) - 24}_more_rows\n")

        output.write("\n[result]\n")
        output.write(
            "collision_free_public_tuple\tlookup_only_no_closed_form_found\n"
        )
        output.write("fixed_recurrence_selector\timpossible_on_constrained_wall\n")
        output.write("affine_selector\timpossible_on_constrained_wall\n")
        output.write("quadratic_ANF_selector\timpossible_on_constrained_wall\n")
        output.write(
            "literal_conjunction_order_le_4\timpossible_at_zero_collateral\n"
        )

    print(
        f"wrote {args.report}: rows={len(prepared)} "
        f"one_recurrences={len(one_input)} two_recurrences={len(two_input)} "
        f"affine_exact={affine_witness is None} "
        f"quadratic_exact={quadratic_witness is None} "
        f"low_order_clauses={sum(item[1] for item in clauses)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
