#!/usr/bin/env python3
"""Audit the omitted full-block boundary carry at the R59 cut.

Intel US5257218A describes a hierarchical carry network in terms of group
generate and propagate functions.  h1128 tested output-aligned carry suffixes
only through 24 bits.  h1416 then tested every absolute phase of 8/16/32/64
bit groups, but represented an exact group boundary by a zero-length interval:
the resulting feature was merely its fixed seed.  That convention omits the
generate/propagate result of the complete group immediately below the cut.

This audit closes that representational seam.  For each literal terminal
representation inherited from h1128 it tests:

* output-aligned complete groups of width 4/8/16/32/64; and
* every absolute phase of those widths, using the preceding complete group
  when the R59 cut is exactly on a boundary and the usual partial group
  otherwise.

Seed zero is the group-generate result and seed one is the conditional
carry/group-propagate result.  Every candidate remains one global
``(representation, layout, width, phase, seed, Boolean gate)`` program.  No
operand predicate, branch-specific choice, threshold, identity key, or tree
is fitted.

All labels are immutable cached data.  The two d0d0 mode legs are reconstructed
from the current executable and assigned their already-proved carry-one
requirement.  No x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

import numpy as np

import h1425_p5_public_mux_signals as h1425
from h1110_carry_gate_mine import (
    GATE_NAMES,
    gate_changes,
    gate_errors,
    state_bad_counts,
)
from h1128_fused_terminal_csa_mine import (
    WIDTH,
    bit,
    reduce_balanced,
    terminal_rows,
)


PATENT = "US5257218A"
PATENT_URL = "https://patents.google.com/patent/US5257218A/en"
BLOCK_WIDTHS = (4, 8, 16, 32, 64)
ALIGNED_NOVEL_WIDTHS = (32, 64)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def conditional_suffixes(
    sum_vector: int, carry_vector: int, cut: int, maximum: int
) -> tuple[list[int], list[int]]:
    """Return carry outputs for every suffix length and both input carries."""
    if not 0 <= cut < WIDTH:
        raise RuntimeError(f"invalid cut {cut}")
    generate = 0
    propagate = 1
    seed_zero = [0]
    seed_one = [1]
    for length in range(1, maximum + 1):
        position = cut - length
        left = bit(sum_vector, position)
        right = bit(carry_vector, position)
        bit_generate = left & right
        bit_propagate = left ^ right
        # Prepend the newly exposed low bit to the already summarized suffix.
        generate = generate | (propagate & bit_generate)
        propagate = propagate & bit_propagate
        seed_zero.append(generate)
        seed_one.append(generate | propagate)
    return seed_zero, seed_one


def feature_schema(representations: tuple[str, ...]) -> tuple[str, ...]:
    names = []
    for representation in representations:
        for width in BLOCK_WIDTHS:
            for seed in (0, 1):
                names.append(
                    f"{representation}.output_aligned.w{width:02d}.seed{seed}"
                )
            for phase in range(width):
                for seed in (0, 1):
                    names.append(
                        f"{representation}.absolute_full_seam.w{width:02d}."
                        f"p{phase:02d}.seed{seed}"
                    )
    return tuple(names)


def row_columns(
    row: dict[str, str], names: tuple[str, ...] | None
) -> tuple[tuple[str, ...], list[int], list[int]]:
    representations = terminal_rows(row)
    if names is None:
        names = feature_schema(tuple(sorted(representations)))
    values: dict[str, int] = {}
    seam_changed: dict[str, int] = {}
    for representation in sorted(representations):
        rows, scale, cut = representations[representation]
        sum_vector, carry_vector, _ = reduce_balanced(rows)
        suffixes = conditional_suffixes(
            sum_vector, carry_vector, cut, max(BLOCK_WIDTHS)
        )
        for width in BLOCK_WIDTHS:
            for seed in (0, 1):
                name = (
                    f"{representation}.output_aligned.w{width:02d}.seed{seed}"
                )
                values[name] = suffixes[seed][width]
                seam_changed[name] = int(values[name] != seed)
            for phase in range(width):
                distance = (scale + cut - phase) % width
                length = width if distance == 0 else distance
                for seed in (0, 1):
                    name = (
                        f"{representation}.absolute_full_seam.w{width:02d}."
                        f"p{phase:02d}.seed{seed}"
                    )
                    values[name] = suffixes[seed][length]
                    seam_changed[name] = int(
                        distance == 0 and values[name] != seed
                    )
    if set(values) != set(names):
        raise RuntimeError("feature schema changed")
    return (
        names,
        [values[name] for name in names],
        [seam_changed[name] for name in names],
    )


def representation_collisions(
    matrix: np.ndarray,
    names: tuple[str, ...],
    prepared: list[h1425.PreparedRow],
) -> list[tuple[str, int, tuple[tuple[str, str], ...]]]:
    columns: dict[str, list[int]] = defaultdict(list)
    for index, name in enumerate(names):
        if ".output_aligned." in name:
            representation = name.partition(".output_aligned.")[0]
        else:
            representation = name.partition(".absolute_full_seam.")[0]
        columns[representation].append(index)

    summaries = []
    for representation, indices in sorted(columns.items()):
        packed = np.packbits(matrix[:, indices], axis=1, bitorder="little")
        groups = defaultdict(lambda: [[], []])
        for index, item in enumerate(prepared):
            key = (
                item.row["branch"],
                item.current,
                packed[index].tobytes(),
            )
            groups[key][item.required].append(item)
        targets = []
        mixed_groups = 0
        for members in groups.values():
            if not members[0] or not members[1]:
                continue
            mixed_groups += 1
            targets.extend(
                (item.row["mode"], item.row["op"])
                for side in members for item in side if item.target
            )
        summaries.append((representation, mixed_groups, tuple(sorted(targets))))
    return summaries


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

    prepared, rows, _, _ = h1425.prepare(args)
    names: tuple[str, ...] | None = None
    matrix: np.ndarray | None = None
    seam_matrix: np.ndarray | None = None
    for index, item in enumerate(prepared):
        names, values, seam_changed = row_columns(item.row, names)
        if matrix is None:
            matrix = np.empty((len(prepared), len(names)), dtype=np.uint8)
            seam_matrix = np.empty_like(matrix)
        matrix[index] = values
        seam_matrix[index] = seam_changed
        if (index + 1) % 1000 == 0:
            print(f"features {index + 1}/{len(prepared)}", flush=True)

    if names is None or matrix is None or seam_matrix is None:
        raise RuntimeError("no constraining rows")
    current = np.asarray([item.current for item in prepared], dtype=np.uint8)
    required = np.asarray([item.required for item in prepared], dtype=np.uint8)
    target = np.asarray([item.target for item in prepared], dtype=bool)
    control = ~target
    allowed = np.zeros((len(prepared), 2), dtype=bool)
    allowed[np.arange(len(prepared)), required] = True
    subsets = {"all": np.ones(len(prepared), dtype=bool),
               "target": target, "control": control}
    counts = {
        name: state_bad_counts(matrix, current, allowed, subset)
        for name, subset in subsets.items()
    }

    ranking = []
    for gate in range(16):
        errors = {
            name: gate_errors(group, gate) for name, group in counts.items()
        }
        changes = gate_changes(matrix, current, control, gate)
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
    improvements = [
        item for item in nonidentity
        if item[2] == 0 and item[1] < int(target.sum())
    ]
    aligned_novel = [
        item for item in ranking
        if ".output_aligned." in item[6]
        and any(f".w{width:02d}." in item[6]
                for width in ALIGNED_NOVEL_WIDTHS)
    ]
    absolute = [
        item for item in ranking if ".absolute_full_seam." in item[6]
    ]
    seam_rows = seam_matrix.sum(axis=0, dtype=np.int64)
    seam_columns = int(np.count_nonzero(seam_rows))
    collisions = representation_collisions(matrix, names, prepared)

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
            "candidate_policy\tliteral_terminal_rows_full_group_boundary_"
            "generate_propagate\n"
        )
        output.write(f"source_rows\t{len(rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{int(target.sum())}\n")
        output.write(f"control_mode_rows\t{int(control.sum())}\n")
        output.write(f"representations\t{len(collisions)}\n")
        output.write(f"features\t{len(names)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(improvements)}\n"
        )
        output.write(f"absolute_phase_programs\t{len(absolute)}\n")
        output.write(
            f"output_aligned_32_64_programs\t{len(aligned_novel)}\n"
        )
        output.write(f"columns_with_nontrivial_boundary_seam\t{seam_columns}\n")

        output.write("\n[boundary seam activity]\n")
        output.write("feature\trows_changed_from_zero_length_seed\n")
        for name, changed in zip(names, seam_rows):
            if changed:
                output.write(f"{name}\t{int(changed)}\n")

        output.write("\n[best nonidentity]\n")
        output.write(
            "all_bad\ttarget_bad\tcontrol_bad\tcontrol_changes\tgate\t"
            "gate_mask\tfeature\n"
        )
        for item in nonidentity[:2000]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best absolute full-seam programs]\n")
        for item in absolute[:1000]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best novel aligned 32/64 programs]\n")
        for item in aligned_novel[:1000]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-collateral improvements]\n")
        for item in improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-error programs]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[per-representation complete-bank collisions]\n")
        output.write(
            "representation\tmixed_groups\ttargets_in_mixed_groups\t"
            "target_rows\n"
        )
        for representation, mixed_groups, targets in collisions:
            target_text = ",".join(
                f"{mode}:{operand}" for mode, operand in targets
            )
            output.write(
                f"{representation}\t{mixed_groups}\t{len(targets)}\t"
                f"{target_text}\n"
            )

        output.write("\n[result]\n")
        if exact:
            output.write("full_block_boundary_selector\texact_candidate_found\n")
        else:
            output.write(
                "full_block_boundary_selector\tno_exact_candidate_found\n"
            )
        output.write(
            "promotion_policy\trequires_exact_result_and_independent_"
            "adversarial_validation\n"
        )

    print(
        f"wrote {args.report}: rows={len(rows)} constrained={len(prepared)} "
        f"features={len(names)} programs={len(ranking)} exact={len(exact)} "
        f"improvements={len(improvements)} seam_columns={seam_columns} "
        f"best={nonidentity[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
