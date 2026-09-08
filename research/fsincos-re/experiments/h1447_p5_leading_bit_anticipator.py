#!/usr/bin/env python3
"""Audit Intel's carry-OR-sum leading-bit anticipator at R59.

Intel WO1999060475A1 defines a floating-point multiplier normalizer control
that predicts the leading nonzero product bit from ``carry OR sum`` before
the final carry-propagate addition.  The prediction can be one position low;
the resolved product then supplies a final one-bit shift correction.

This audit applies that literal circuit to the exact 67-by-64-bit P5
radix-8/4:2 CSA tree reconstructed from Intel US5195051A.  The P5 tree and
the later anticipator are two Intel source disclosures, but their composition
is only a physically plausible isomorphism: it is not evidence that Skylake
uses the same redundant representation.

At each of the eight recovered FMUL sites and in both operand-port
orientations, the script asserts that the P5 sum/carry words reconstruct the
exact product and that the anticipator is correct or one bit low.  It scores
only the patent's priority-encoder position bits and the final correction.
There are no operand identities, thresholds, interval searches, learned
trees, new hardware observations, or emulator changes.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import h1100_p5_multiplier_tree as h1100
import h1425_p5_public_mux_signals as h1425
import h1432_multiformat_split_adder_logic as h1432
import h1441_iterative_multiplier_feedback as h1441
from h1110_carry_gate_mine import GATE_NAMES


LBA_PATENT = "WO1999060475A1"
LBA_URL = "https://patents.google.com/patent/WO1999060475A1/en"
TREE_PATENT = "US5195051A"
TREE_URL = "https://patents.google.com/patent/US5195051A/en"
FMUL_STAGES = h1441.FMUL_STAGES
ROLES = ("written", "swapped")
POSITION_BITS = 8


@dataclass(frozen=True)
class PreparedRow:
    row: dict[str, str]
    current: int
    required: int
    target: bool
    signals: bytes
    trace: tuple[tuple[object, ...], ...]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def code_bits(values: dict[str, int], prefix: str, value: int) -> None:
    if not 0 <= value < (1 << POSITION_BITS):
        raise ValueError("leading-bit position does not fit encoder output")
    for bit in range(POSITION_BITS):
        values[f"{prefix}.bit{bit}"] = (value >> bit) & 1


def leading_bit_state(
    left: h1441.Value,
    right: h1441.Value,
    role: str,
) -> tuple[dict[str, int], tuple[object, ...]]:
    if role == "swapped":
        left, right = right, left
    elif role != "written":
        raise ValueError(role)

    multiplicand = h1441.normalized_significand(left, 67)
    multiplier = h1441.normalized_significand(right, 64)
    state = h1100.assert_product(multiplicand, multiplier)
    sum_word = state["sum"] & h1100.PRODUCT_MASK
    carry_word = state["carry"] & h1100.PRODUCT_MASK
    product = (sum_word + carry_word) & h1100.PRODUCT_MASK
    exact_product = multiplicand * multiplier
    if product != exact_product:
        raise RuntimeError("P5 carry/sum words changed the exact product")

    predicted_word = sum_word | carry_word
    if not predicted_word or not product:
        raise RuntimeError("normalized multiplier produced a zero word")
    predicted_position = predicted_word.bit_length() - 1
    actual_position = product.bit_length() - 1
    correction = actual_position - predicted_position
    if correction not in (0, 1):
        raise RuntimeError(
            "carry-OR-sum anticipator was not exact or one position low"
        )

    values = {"resolved.correction": correction}
    code_bits(values, "lba.predicted_position", predicted_position)
    code_bits(values, "resolved.actual_position", actual_position)
    trace = (
        role,
        multiplicand,
        multiplier,
        predicted_position,
        actual_position,
        correction,
    )
    return values, trace


def source_signals(
    row: dict[str, str],
) -> tuple[dict[str, int], tuple[tuple[object, ...], ...]]:
    values: dict[str, int] = {}
    traces = []
    for stage, operands in h1441.fmul_inputs(row).items():
        for role in ROLES:
            local, trace = leading_bit_state(*operands, role)
            stem = f"{stage}.{role}"
            values.update({f"{stem}.{name}": value
                           for name, value in local.items()})
            traces.append((stage, trace))
    return values, tuple(traces)


def prepare(args: argparse.Namespace) -> tuple[
    list[PreparedRow], list[dict[str, str]], tuple[str, ...]
]:
    base, source_rows, _, _ = h1425.prepare(args)
    prepared = []
    names: tuple[str, ...] | None = None
    for row_index, item in enumerate(base):
        values, trace = source_signals(item.row)
        if names is None:
            names = tuple(sorted(values))
        elif set(values) != set(names):
            raise RuntimeError("leading-bit signal schema changed")
        prepared.append(PreparedRow(
            row=item.row,
            current=item.current,
            required=item.required,
            target=item.target,
            signals=bytes(values[name] for name in names),
            trace=trace if item.target else (),
        ))
        if row_index and row_index % 8000 == 0:
            print(f"  reconstructed {row_index}/{len(base)} rows", flush=True)
    if names is None:
        raise RuntimeError("no constraining rows")
    return prepared, source_rows, names


def structural_pairs(names: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    available = set(names)
    pairs = []
    for stage in FMUL_STAGES:
        prefix = f"{stage}.written."
        for name in names:
            if not name.startswith(prefix):
                continue
            suffix = name[len(prefix):]
            pair = (name, f"{stage}.swapped.{suffix}")
            if pair[1] in available:
                pairs.append(pair)
    return tuple(pairs)


def assess_history(
    prepared: list[PreparedRow], columns: tuple[int, ...],
) -> tuple[int, int, int, tuple[tuple[object, ...], ...]]:
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        history = bytes(item.signals[index] for index in columns)
        groups[(item.row["branch"], item.current, history)][
            item.required
        ].append(item)

    mixed = 0
    targets_in_mixed = 0
    rows_in_mixed = 0
    witnesses = []
    for members in groups.values():
        if not members[0] or not members[1]:
            continue
        mixed += 1
        rows_in_mixed += len(members[0]) + len(members[1])
        targets = [item for side in members for item in side if item.target]
        targets_in_mixed += len(targets)
        if targets and len(witnesses) < 4:
            witnesses.append((
                tuple((item.row["mode"], item.row["op"])
                      for item in targets),
                (members[0][0].row["mode"], members[0][0].row["op"]),
                (members[1][0].row["mode"], members[1][0].row["op"]),
            ))
    return mixed, targets_in_mixed, rows_in_mixed, tuple(witnesses)


def history_results(
    prepared: list[PreparedRow], names: tuple[str, ...],
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    indices = {name: index for index, name in enumerate(names)}
    first = FMUL_STAGES[0]
    suffixes = tuple(sorted({
        name.split(".", 2)[2]
        for name in names
        if name.startswith(first + ".")
    }))

    streams = []
    for suffix in suffixes:
        for role_set_name, roles in (
            ("written", ("written",)),
            ("swapped", ("swapped",)),
            ("both", ROLES),
        ):
            columns = tuple(
                indices[f"{stage}.{role}.{suffix}"]
                for stage in FMUL_STAGES
                for role in roles
            )
            streams.append((
                suffix,
                role_set_name,
                *assess_history(prepared, columns),
            ))

    joint = []
    for role_set_name, roles in (
        ("written", ("written",)),
        ("swapped", ("swapped",)),
        ("both", ROLES),
    ):
        columns = tuple(
            indices[f"{stage}.{role}.{suffix}"]
            for stage in FMUL_STAGES
            for role in roles
            for suffix in suffixes
        )
        joint.append((
            role_set_name,
            len(columns),
            *assess_history(prepared, columns),
        ))
    return streams, joint


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
    matrix = np.frombuffer(
        b"".join(item.signals for item in prepared), dtype=np.uint8
    ).reshape(len(prepared), len(names))
    current = np.asarray([item.current for item in prepared], dtype=np.uint8)
    required = np.asarray([item.required for item in prepared], dtype=np.uint8)
    target = np.asarray([item.target for item in prepared], dtype=bool)
    target_count = int(target.sum())

    gate_ranking = []
    for signal_index, name in enumerate(names):
        selector = 2 * current + matrix[:, signal_index]
        for gate in range(16):
            prediction = ((gate >> selector) & 1).astype(np.uint8)
            changed = prediction != current
            gate_ranking.append((
                *h1432.score_prediction(prediction, required, target),
                int(changed[~target].sum()),
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
    nonidentity_gates = [item for item in gate_ranking if item[5] != 12]

    indices = {name: index for index, name in enumerate(names)}
    pairs = structural_pairs(names)
    pair_ranking = []
    for left_name, right_name in pairs:
        selector = (
            4 * current
            + 2 * matrix[:, indices[left_name]]
            + matrix[:, indices[right_name]]
        )
        for gate in range(256):
            prediction = ((gate >> selector) & 1).astype(np.uint8)
            wrong = prediction != required
            changed = prediction != current
            pair_ranking.append((
                int(wrong.sum()),
                int(wrong[target].sum()),
                int(wrong[~target].sum()),
                int(changed[~target].sum()),
                f"0x{gate:02x}",
                left_name,
                right_name,
            ))
    pair_ranking.sort()
    pair_exact = [item for item in pair_ranking if item[0] == 0]
    pair_improvements = [
        item for item in pair_ranking
        if item[2] == 0 and item[1] < target_count
    ]
    nonidentity_pairs = [item for item in pair_ranking if item[4] != "0xf0"]

    streams, joint = history_results(prepared, names)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for label, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
            ("p5_tree", Path(h1100.__file__)),
        ):
            output.write(f"{label}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(
            f"lba_primary_source\t{LBA_PATENT}\t{LBA_URL}\t"
            "source_vendor=Intel\n"
        )
        output.write(
            f"tree_primary_source\t{TREE_PATENT}\t{TREE_URL}\t"
            "source_vendor=Intel\n"
        )
        output.write(
            "source_scope\tcomposition_of_two_exact_Intel_disclosures_"
            "possible_isomorphism_not_Skylake_provenance\n"
        )
        output.write(
            "candidate_policy\tpriority_encoder_position_bits_and_"
            "one_bit_resolved_correction_only_no_operand_fitting\n"
        )
        output.write(
            "arithmetic_identity\tP5_sum_plus_carry_mod_2^131="
            "exact_67x64_product\n"
        )
        output.write(
            "anticipator_identity\tactual_leading_position_minus_"
            "leading_position(carry_OR_sum)_in_{0,1}\n"
        )
        output.write("operand_ports\t67x64\n")
        output.write("operand_roles\twritten,swapped\n")
        output.write("fmul_stages\t" + ",".join(FMUL_STAGES) + "\n")
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{len(prepared) - target_count}\n")
        output.write(f"candidate_signals\t{len(names)}\n")
        output.write(f"global_gate_programs\t{len(gate_ranking)}\n")
        output.write(f"global_gate_exact\t{len(gate_exact)}\n")
        output.write(
            "global_gate_zero_control_improvements\t"
            f"{len(gate_improvements)}\n"
        )
        output.write(
            "best_nonidentity_global_gate\t"
            + "\t".join(map(str, nonidentity_gates[0])) + "\n"
        )
        output.write(f"structural_pairs\t{len(pairs)}\n")
        output.write(f"structural_pair_gate_programs\t{len(pair_ranking)}\n")
        output.write(f"structural_pair_gate_exact\t{len(pair_exact)}\n")
        output.write(
            "structural_pair_gate_zero_control_improvements\t"
            f"{len(pair_improvements)}\n"
        )
        output.write(
            "best_nonidentity_structural_pair_gate\t"
            + "\t".join(map(str, nonidentity_pairs[0])) + "\n"
        )
        output.write(f"individual_history_streams\t{len(streams)}\n")
        output.write(
            "collision_free_individual_histories\t"
            f"{sum(item[2] == 0 for item in streams)}\n"
        )

        output.write("\n[best global gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in gate_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-control global improvements]\n")
        for item in gate_improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best written/swapped pair gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate_mask\twritten_signal\tswapped_signal\n"
        )
        for item in pair_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-control written/swapped improvements]\n")
        for item in pair_improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[individual complete-history collisions]\n")
        output.write(
            "suffix\troles\tmixed_groups\ttargets_in_mixed\t"
            "rows_in_mixed\twitnesses\n"
        )
        for item in streams:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[joint priority-encoder-history collisions]\n")
        output.write(
            "roles\tbits\tmixed_groups\ttargets_in_mixed\t"
            "rows_in_mixed\twitnesses\n"
        )
        for item in joint:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[target leading-bit traces]\n")
        output.write("mode\top\tcurrent\trequired\ttraces\n")
        for item in prepared:
            if item.target:
                output.write("\t".join((
                    item.row["mode"],
                    item.row["op"],
                    str(item.current),
                    str(item.required),
                    repr(item.trace),
                )) + "\n")

        output.write("\n[result]\n")
        if gate_exact or pair_exact:
            output.write("p5_leading_bit_anticipator_selector\tCANDIDATE_ONLY\n")
        else:
            output.write("p5_leading_bit_anticipator_selector\tno_exact_program\n")


if __name__ == "__main__":
    main()
