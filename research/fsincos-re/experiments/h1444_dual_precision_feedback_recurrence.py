#!/usr/bin/env python3
"""Test fixed recurrences on h1443's collision-free p67/p68 histories.

h1443 found that no single corrected iterative-feedback signal can drive the
missing R59 carry, but the complete p67/p68 histories of ``final.round_bit``
and ``final.rne_increment`` are collision-free on the frozen wall.  This is
only lookup capacity unless the 16-bit history collapses to a small fixed
recurrence.

This audit exhausts two source-motivated recurrence families over the eight
modeled FMUL stages:

* every one-bit Boolean transition ``q' = f(q, bit67, bit68)``;
* every two-bit affine transition ``q' = a*q + b*symbol + c (mod 4)``.

The transition is fixed across stages.  Both/all initial states and every
stage tap are tested.  At each tap, both a global output decoder based on
``(incumbent carry, q)`` and the more permissive existing-branch-qualified
decoder are assessed exactly.  A branch decoder is an upper bound, not a
license to fit an operand table.

The p67/p68 bits are exact arithmetic outputs and are invariant under the two
Booth encodings and operand-port swap used by h1442; those aliases are checked
before labels are scored.  No threshold, operand identity, decision tree,
x87 execution, or paper/emulator change is involved.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np

import h1442_corrected_iterative_feedback as h1442


SUFFIXES = ("final.round_bit", "final.rne_increment")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def column_index(names: tuple[str, ...], name: str) -> int:
    try:
        return names.index(name)
    except ValueError as error:
        raise RuntimeError(f"missing h1442 signal {name}") from error


def mask_from_column(
    prepared: list[h1442.PreparedRow], index: int,
) -> int:
    packed = bytearray((len(prepared) + 7) // 8)
    for row_index, item in enumerate(prepared):
        packed[row_index >> 3] |= item.signals[index] << (row_index & 7)
    return int.from_bytes(packed, "little")


def transition1(
    law: int, state: int, low: int, high: int, all_rows: int,
) -> int:
    result = 0
    not_state = all_rows ^ state
    not_low = all_rows ^ low
    not_high = all_rows ^ high
    for state_value, state_rows in ((0, not_state), (1, state)):
        for symbol, symbol_rows in (
            (0, not_low & not_high),
            (1, low & not_high),
            (2, not_low & high),
            (3, low & high),
        ):
            if (law >> (4 * state_value + symbol)) & 1:
                result |= state_rows & symbol_rows
    return result


def assess_mask(
    state: int,
    all_rows: int,
    current: int,
    required: int,
    branch_masks: tuple[tuple[str, int], ...],
) -> tuple[int, str, int, str]:
    def assess(scopes: tuple[tuple[str, int], ...]) -> tuple[int, str]:
        errors = 0
        table = 0
        table_index = 0
        for _, scope in scopes:
            for current_value in (0, 1):
                current_rows = current if current_value else all_rows ^ current
                for state_value in (0, 1):
                    state_rows = state if state_value else all_rows ^ state
                    group = scope & current_rows & state_rows
                    zeros = (group & (all_rows ^ required)).bit_count()
                    ones = (group & required).bit_count()
                    if ones > zeros:
                        table |= 1 << table_index
                        errors += zeros
                    else:
                        errors += ones
                    table_index += 1
        return errors, f"0x{table:0{max(1, (table_index + 3) // 4)}x}"

    global_errors, global_table = assess((("global", all_rows),))
    branch_errors, branch_table = assess(branch_masks)
    return global_errors, global_table, branch_errors, branch_table


def assess_array(
    state: np.ndarray,
    current: np.ndarray,
    required: np.ndarray,
    branch: np.ndarray,
) -> tuple[int, str, int, str]:
    def assess(groups: np.ndarray, group_count: int) -> tuple[int, str]:
        counts = np.bincount(
            2 * groups.astype(np.int64) + required,
            minlength=2 * group_count,
        ).reshape(group_count, 2)
        errors = int(np.minimum(counts[:, 0], counts[:, 1]).sum())
        selected = counts[:, 1] > counts[:, 0]
        table = sum(int(value) << index
                    for index, value in enumerate(selected))
        return errors, f"0x{table:0{max(1, (group_count + 3) // 4)}x}"

    base = 4 * current + state
    global_errors, global_table = assess(base, 8)
    branch_errors, branch_table = assess(8 * branch + base, 32)
    return global_errors, global_table, branch_errors, branch_table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default=h1442.h1425.EXTRA_OP)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    prepared, source_rows, names = h1442.prepare(args)
    row_count = len(prepared)
    all_rows = (1 << row_count) - 1
    current_mask = sum(
        item.current << index for index, item in enumerate(prepared)
    )
    required_mask = sum(
        item.required << index for index, item in enumerate(prepared)
    )
    branches = tuple(sorted({item.row["branch"] for item in prepared}))
    branch_masks = tuple((
        branch_name,
        sum(int(item.row["branch"] == branch_name) << index
            for index, item in enumerate(prepared)),
    ) for branch_name in branches)

    current_array = np.asarray(
        [item.current for item in prepared], dtype=np.uint8)
    required_array = np.asarray(
        [item.required for item in prepared], dtype=np.int64)
    branch_codes = {name: index for index, name in enumerate(branches)}
    branch_array = np.asarray(
        [branch_codes[item.row["branch"]] for item in prepared],
        dtype=np.uint8,
    )

    alias_checks = []
    histories: dict[str, tuple[tuple[int, int], ...]] = {}
    arrays: dict[str, tuple[np.ndarray, ...]] = {}
    for suffix in SUFFIXES:
        stage_masks = []
        stage_symbols = []
        for stage in h1442.FMUL_STAGES:
            precision_columns = []
            for precision in h1442.PROJECTIONS:
                canonical_name = (
                    f"{stage}.full_twos.p{precision}.written.{suffix}"
                )
                canonical_index = column_index(names, canonical_name)
                canonical = bytes(
                    item.signals[canonical_index] for item in prepared
                )
                aliases = []
                for representation in h1442.REPRESENTATIONS:
                    for role in h1442.ROLES:
                        alias_name = (
                            f"{stage}.{representation}.p{precision}."
                            f"{role}.{suffix}"
                        )
                        alias_index = column_index(names, alias_name)
                        alias = bytes(
                            item.signals[alias_index] for item in prepared
                        )
                        if alias != canonical:
                            raise RuntimeError(
                                f"exact-product alias changed: {alias_name}"
                            )
                        aliases.append(alias_name)
                alias_checks.append((suffix, stage, precision, len(aliases)))
                precision_columns.append(canonical_index)

            low_mask = mask_from_column(prepared, precision_columns[0])
            high_mask = mask_from_column(prepared, precision_columns[1])
            stage_masks.append((low_mask, high_mask))
            low_array = np.fromiter(
                (item.signals[precision_columns[0]] for item in prepared),
                dtype=np.uint8,
                count=row_count,
            )
            high_array = np.fromiter(
                (item.signals[precision_columns[1]] for item in prepared),
                dtype=np.uint8,
                count=row_count,
            )
            stage_symbols.append(low_array | (high_array << 1))
        histories[suffix] = tuple(stage_masks)
        arrays[suffix] = tuple(stage_symbols)

    boolean_results = []
    affine_results = []
    for suffix in SUFFIXES:
        for initial in (0, 1):
            initial_mask = all_rows if initial else 0
            for law in range(256):
                state = initial_mask
                for tap, (low, high) in enumerate(histories[suffix], start=1):
                    state = transition1(law, state, low, high, all_rows)
                    assessment = assess_mask(
                        state, all_rows, current_mask, required_mask,
                        branch_masks,
                    )
                    boolean_results.append((
                        suffix, initial, f"0x{law:02x}", tap, *assessment
                    ))

        for encoding in ("p67_low", "p68_low"):
            symbol_arrays = arrays[suffix]
            if encoding == "p68_low":
                symbol_arrays = tuple(
                    ((symbol & 1) << 1) | ((symbol >> 1) & 1)
                    for symbol in symbol_arrays
                )
            for initial in range(4):
                for a in range(4):
                    for b in range(4):
                        for c in range(4):
                            state = np.full(row_count, initial, dtype=np.uint8)
                            for tap, symbol in enumerate(
                                    symbol_arrays, start=1):
                                state = (
                                    a * state + b * symbol + c
                                ) & 3
                                assessment = assess_array(
                                    state, current_array, required_array,
                                    branch_array,
                                )
                                affine_results.append((
                                    suffix, encoding, initial, a, b, c, tap,
                                    *assessment,
                                ))

    boolean_exact_global = [item for item in boolean_results if item[4] == 0]
    boolean_exact_branch = [item for item in boolean_results if item[6] == 0]
    affine_exact_global = [item for item in affine_results if item[7] == 0]
    affine_exact_branch = [item for item in affine_results if item[9] == 0]
    boolean_ranking = sorted(
        boolean_results, key=lambda item: (item[4], item[6], item[:4]))
    affine_ranking = sorted(
        affine_results, key=lambda item: (item[7], item[9], item[:7]))

    target_count = sum(item.target for item in prepared)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for label, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
            ("feedback_reconstruction", Path(h1442.__file__)),
        ):
            output.write(f"{label}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tfixed_dual_precision_recurrences_no_"
            "operand_features_or_learned_stage_gates\n"
        )
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{row_count}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{row_count - target_count}\n")
        output.write(f"fmul_stages\t{len(h1442.FMUL_STAGES)}\n")
        output.write(f"history_suffixes\t{','.join(SUFFIXES)}\n")
        output.write(f"exact_product_alias_checks\t{len(alias_checks)}\n")
        output.write(f"one_bit_program_taps\t{len(boolean_results)}\n")
        output.write(
            f"one_bit_exact_global_decoders\t{len(boolean_exact_global)}\n"
        )
        output.write(
            f"one_bit_exact_branch_decoders\t{len(boolean_exact_branch)}\n"
        )
        output.write(f"affine_mod4_program_taps\t{len(affine_results)}\n")
        output.write(
            f"affine_mod4_exact_global_decoders\t{len(affine_exact_global)}\n"
        )
        output.write(
            f"affine_mod4_exact_branch_decoders\t{len(affine_exact_branch)}\n"
        )

        output.write("\n[best one-bit fixed recurrences]\n")
        output.write(
            "suffix\tinitial\ttransition_table\ttap\tglobal_errors\t"
            "global_output_table\tbranch_errors\tbranch_output_table\n"
        )
        for item in boolean_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best affine-mod4 fixed recurrences]\n")
        output.write(
            "suffix\tencoding\tinitial\ta\tb\tc\ttap\tglobal_errors\t"
            "global_output_table\tbranch_errors\tbranch_output_table\n"
        )
        for item in affine_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[result]\n")
        if boolean_exact_global or affine_exact_global:
            output.write("dual_precision_recurrence\tCANDIDATE_ONLY\n")
        elif boolean_exact_branch or affine_exact_branch:
            output.write(
                "dual_precision_recurrence\tbranch_qualified_candidate_only\n"
            )
        else:
            output.write("dual_precision_recurrence\tno_exact_program\n")
        output.write(
            "history_separation_status\thigh_dimensional_lookup_capacity_"
            "only_without_fixed_recurrence\n"
        )


if __name__ == "__main__":
    main()
