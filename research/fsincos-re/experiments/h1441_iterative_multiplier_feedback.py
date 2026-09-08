#!/usr/bin/env python3
"""Audit source-anchored 27-bit iterative-multiplier feedback at R59.

Tan, Lemonds, and Schulte describe an AMD 76x27-bit rectangular multiplier
whose IP68/EP operations take three low-first passes.  The first two passes
feed product bits 102:27 back in redundant carry-save form while their
27-bit low regions contribute carry and cumulative sticky information to the
combined DP/EP rounder.  Figure 3 fixes fourteen radix-4 Booth rows, two
feedback rows, and a contiguous three-level 4:2 compression tree.  Figure 11
shows four carry wires and one sticky wire from prior iterations, but does not
publish the optimized carry-wire recurrence.

This audit reconstructs the fixed Figure-3 tree at all eight FMULs in the
modeled cosine schedule.  It tests two non-fitted input projections: the
project's recovered 67-bit carrier and the paper's named IP68 precision.  Both
operand port orientations are included because the numeric operation is
symmetric but iterative state is not.  At each pass it exposes the two
carry-select endpoints of the 27-bit low region, resolved and redundant
sticky, boundary bits, and the next feedback bits.  A bounded interpretation
of Figure 11's four prior-iteration carry wires is the carry-zero/carry-one
endpoint pair from each of passes one and two; this interpretation is stated,
not attributed to unpublished RTL.

Every signal is composed with the incumbent R59 carry by one global Boolean
gate.  Fixed one-bit recurrences are exhausted across the eight FMUL sites,
and paired affine recurrences cover only source-coupled endpoint/sticky pairs.
Complete-history collisions test whether even an arbitrary deterministic
function of this reconstructed state could label the wall.  There are no
operand identities, thresholds, interval boundaries, learned trees, or x87
execution.  AMD physical plausibility is not Intel/Skylake provenance.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np

import h1425_p5_public_mux_signals as h1425
import h1432_multiformat_split_adder_logic as h1432
from h1110_carry_gate_mine import GATE_NAMES
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    Value,
    multiply,
    quantize,
    row_value,
    schedule,
)


PAPER = "Tan_Lemonds_Schulte_IEEE_TC_2009"
PAPER_DOI = "10.1109/TC.2008.203"
PAPER_PATH = Path(
    "supplemental/Low-Power Multiple-Precision Iterative Floating-Point -- "
    "Dimitri Tan;Carl E_ Lemonds;Michael J_ Schulte(Advanced -- IEEE "
    "Transactions on Computers, -- doi 10_1109-tc_2008_203 -- "
    "0044589fc58ebf85504d4a59beb66021 -- Anna’s Archive.pdf"
)
VERIFICATION_PAPER = Path("supplemental/1110.4675v1.pdf")
FMUL_STAGES = (
    "square",
    "fourth",
    "negative.mul1",
    "positive.mul1",
    "negative.mul2",
    "positive.mul2",
    "left",
    "right",
)
PROJECTIONS = (67, 68)
ROLES = ("written", "swapped")
PRODUCT_WIDTH = 103
FEEDBACK_WIDTH = 76
CHUNK_WIDTH = 27
PRODUCT_MASK = (1 << PRODUCT_WIDTH) - 1
FEEDBACK_MASK = (1 << FEEDBACK_WIDTH) - 1
CHUNK_MASK = (1 << CHUNK_WIDTH) - 1
DIGIT = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}


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


def csa(left: int, right: int, addend: int) -> tuple[int, int]:
    total = (left ^ right ^ addend) & PRODUCT_MASK
    carry = (
        ((left & right) | (left & addend) | (right & addend)) << 1
    ) & PRODUCT_MASK
    return total, carry


def compressor42(a: int, b: int, c: int, d: int) -> tuple[int, int]:
    first_sum, first_carry = csa(a, b, c)
    return csa(first_sum, first_carry, d)


def booth_rows(multiplicand: int, multiplier: int) -> list[int]:
    """Fourteen radix-4 rows with hot-ones on the following row."""
    encoded = (multiplier & CHUNK_MASK) << 1
    rows = []
    pending_hot_one = 0
    for column in range(0, 28, 2):
        digit = DIGIT[(encoded >> column) & 7]
        if digit > 0:
            row = (digit * multiplicand << column) & PRODUCT_MASK
        elif digit < 0:
            row = (
                ((~((-digit) * multiplicand)) & PRODUCT_MASK) << column
            ) & PRODUCT_MASK
        else:
            row = 0
        row |= pending_hot_one
        pending_hot_one = (1 << column) if digit < 0 else 0
        rows.append(row)
    return rows


def source_tree(
    rows: list[int], feedback_sum: int, feedback_carry: int
) -> tuple[int, int]:
    """The contiguous 16-input, three-level 4:2 tree in Figure 3."""
    if len(rows) != 14:
        raise RuntimeError("Figure-3 tree requires fourteen Booth rows")
    inputs = rows + [feedback_sum, feedback_carry]
    level1 = [
        compressor42(*inputs[index:index + 4])
        for index in range(0, 16, 4)
    ]
    level2_left = compressor42(*level1[0], *level1[1])
    level2_right = compressor42(*level1[2], *level1[3])
    return compressor42(*level2_left, *level2_right)


def normalized_significand(value: Value, precision: int) -> int:
    """Project a normalized value to a fixed significand width by chopping."""
    width = value.significand.bit_length()
    if width > precision:
        result = value.significand >> (width - precision)
    else:
        result = value.significand << (precision - width)
    if result.bit_length() != precision:
        raise RuntimeError("failed to normalize multiplier input")
    return result


def fmul_inputs(row: dict[str, str]) -> dict[str, tuple[Value, Value]]:
    operations = schedule(row)
    magnitude = row_value(row, "mag")
    square = quantize(operations["square"], 67, False)
    fourth = quantize(operations["fourth"], 67, False)
    negative1 = quantize(operations["negative.add1"], 64, True)
    positive1 = quantize(operations["positive.add1"], 64, True)
    negative2 = quantize(operations["negative.add2"], 64, True)
    positive2 = quantize(operations["positive.add2"], 64, True)
    inputs = {
        "square": (magnitude, magnitude),
        "fourth": (square, square),
        "negative.mul1": (fourth, Value(*CONSTANTS[5])),
        "positive.mul1": (fourth, Value(*CONSTANTS[6])),
        "negative.mul2": (fourth, negative1),
        "positive.mul2": (fourth, positive1),
        "left": (square, negative2),
        "right": (fourth, positive2),
    }
    if tuple(inputs) != FMUL_STAGES:
        raise RuntimeError("FMUL stage order changed")
    for stage, operands in inputs.items():
        if multiply(*operands) != operations[stage]:
            raise RuntimeError(f"FMUL input reconstruction failed at {stage}")
    return inputs


def iteration_state(
    left: Value, right: Value, precision: int, role: str
) -> tuple[dict[str, int], tuple[object, ...]]:
    a = normalized_significand(left, precision)
    b = normalized_significand(right, precision)
    if role == "swapped":
        a, b = b, a
    elif role != "written":
        raise ValueError(role)

    # Figure 6 left-aligns the significand in the 76-bit multiplicand port.
    multiplicand = a << (FEEDBACK_WIDTH - precision)
    low_width = precision - 2 * CHUNK_WIDTH
    if not 1 <= low_width <= CHUNK_WIDTH:
        raise RuntimeError("unsupported three-pass precision")
    chunks = (
        (b & ((1 << low_width) - 1)) << (CHUNK_WIDTH - low_width),
        (b >> low_width) & CHUNK_MASK,
        (b >> (low_width + CHUNK_WIDTH)) & CHUNK_MASK,
    )

    values: dict[str, int] = {}
    traces = []
    feedback_sum = 0
    feedback_carry = 0
    cumulative_sticky = 0
    early_endpoints = []
    for pass_index, chunk in enumerate(chunks, start=1):
        product_sum, product_carry = source_tree(
            booth_rows(multiplicand, chunk), feedback_sum, feedback_carry
        )
        expected = multiplicand * chunk + feedback_sum + feedback_carry
        if ((product_sum + product_carry) & PRODUCT_MASK) != expected:
            raise RuntimeError("Figure-3 tree failed exact arithmetic")

        low_sum = product_sum & CHUNK_MASK
        low_carry = product_carry & CHUNK_MASK
        low_total = low_sum + low_carry
        carry0 = (low_total >> CHUNK_WIDTH) & 1
        carry1 = ((low_total + 1) >> CHUNK_WIDTH) & 1
        resolved_low = low_total & CHUNK_MASK
        resolved_sticky = int(bool(resolved_low))
        redundant_sticky = int(bool(low_sum | low_carry))
        cumulative_sticky |= resolved_sticky
        prefix = f"pass{pass_index}"
        local = {
            "carry0": carry0,
            "carry1": carry1,
            "carry_xor": carry0 ^ carry1,
            "resolved_sticky": resolved_sticky,
            "redundant_sticky": redundant_sticky,
            "cumulative_sticky": cumulative_sticky,
            "sum_boundary": (low_sum >> 26) & 1,
            "carry_boundary": (low_carry >> 26) & 1,
            "resolved_boundary": (resolved_low >> 26) & 1,
            "sum_lsb": low_sum & 1,
            "carry_lsb": low_carry & 1,
            "resolved_lsb": resolved_low & 1,
            "feedback_sum_lsb": (product_sum >> 27) & 1,
            "feedback_carry_lsb": (product_carry >> 27) & 1,
        }
        values.update({f"{prefix}.{name}": value for name, value in local.items()})
        traces.append((
            pass_index,
            chunk,
            carry0,
            carry1,
            resolved_sticky,
            redundant_sticky,
            cumulative_sticky,
            low_sum,
            low_carry,
        ))
        if pass_index < 3:
            early_endpoints.extend((carry0, carry1))
            feedback_sum = (product_sum >> CHUNK_WIDTH) & FEEDBACK_MASK
            feedback_carry = (product_carry >> CHUNK_WIDTH) & FEEDBACK_MASK

    if len(early_endpoints) != 4:
        raise RuntimeError("missing prior-iteration carry endpoints")
    carry4 = sum(bit << index for index, bit in enumerate(early_endpoints))
    aggregate = {
        **{f"prior_carry4.bit{index}": bit
           for index, bit in enumerate(early_endpoints)},
        "prior_carry4.any": int(bool(carry4)),
        "prior_carry4.all": int(carry4 == 15),
        "prior_carry4.parity": carry4.bit_count() & 1,
        "prior_carry4.pass_equal": int(
            early_endpoints[:2] == early_endpoints[2:]
        ),
        "prior_sticky": int(bool(traces[0][4] or traces[1][4])),
        "prior_redundant_sticky": int(bool(traces[0][5] or traces[1][5])),
    }
    values.update(aggregate)
    return values, (precision, role, a, b, tuple(traces), carry4)


def source_signals(
    row: dict[str, str]
) -> tuple[dict[str, int], tuple[tuple[object, ...], ...]]:
    values: dict[str, int] = {}
    traces = []
    for stage, operands in fmul_inputs(row).items():
        for precision in PROJECTIONS:
            for role in ROLES:
                local, trace = iteration_state(*operands, precision, role)
                stem = f"{stage}.p{precision}.{role}"
                values.update({f"{stem}.{name}": value for name, value in local.items()})
                traces.append((stage, *trace))
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
            raise RuntimeError("iterative multiplier signal schema changed")
        prepared.append(PreparedRow(
            row=item.row,
            current=item.current,
            required=item.required,
            target=item.target,
            signals=bytes(values[name] for name in names),
            trace=trace if item.target else (),
        ))
        if row_index and row_index % 4000 == 0:
            print(f"  reconstructed {row_index}/{len(base)} rows", flush=True)
    if names is None:
        raise RuntimeError("no constraining rows")
    return prepared, source_rows, names


def gate_output(gate: int, current: np.ndarray, signal: np.ndarray) -> np.ndarray:
    return ((gate >> (2 * current + signal)) & 1).astype(np.uint8)


def signal_sequences(
    names: tuple[str, ...], matrix: np.ndarray
) -> dict[str, tuple[np.ndarray, ...]]:
    columns: dict[str, dict[str, int]] = {}
    for index, name in enumerate(names):
        for stage in FMUL_STAGES:
            prefix = stage + "."
            if name.startswith(prefix):
                columns.setdefault(name[len(prefix):], {})[stage] = index
                break
    return {
        suffix: tuple(matrix[:, stage_columns[stage]] for stage in FMUL_STAGES)
        for suffix, stage_columns in columns.items()
        if set(stage_columns) == set(FMUL_STAGES)
    }


def paired_sequence_names(sequence_names: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    available = set(sequence_names)
    pairs = set()
    for precision in PROJECTIONS:
        for role in ROLES:
            stem = f"p{precision}.{role}."
            for pass_index in (1, 2, 3):
                prefix = stem + f"pass{pass_index}."
                for left, right in (
                    ("carry0", "carry1"),
                    ("resolved_sticky", "redundant_sticky"),
                    ("sum_boundary", "carry_boundary"),
                    ("feedback_sum_lsb", "feedback_carry_lsb"),
                ):
                    pair = (prefix + left, prefix + right)
                    if set(pair) <= available:
                        pairs.add(pair)
            for left, right in combinations(
                ("prior_carry4.bit0", "prior_carry4.bit1",
                 "prior_carry4.bit2", "prior_carry4.bit3",
                 "prior_sticky"),
                2,
            ):
                pair = (stem + left, stem + right)
                if set(pair) <= available:
                    pairs.add(pair)
    return tuple(sorted(pairs))


def paired_affine_recurrences(
    sequences: dict[str, tuple[np.ndarray, ...]],
    pairs: tuple[tuple[str, str], ...],
    current: np.ndarray,
    required: np.ndarray,
    target: np.ndarray,
) -> list[tuple]:
    ranking = []
    for left_name, right_name in pairs:
        left = sequences[left_name]
        right = sequences[right_name]
        for initial in (0, 1):
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
                    prediction = gate_output(output_gate, current, state)
                    score = h1432.score_prediction(prediction, required, target)
                    ranking.append((
                        *score, left_name, right_name, initial, coefficients,
                        output_gate, GATE_NAMES[output_gate], int(state.sum()),
                        int(state[target].sum()),
                    ))
    ranking.sort()
    return ranking


def paired_global_gates(
    names: tuple[str, ...],
    matrix: np.ndarray,
    suffix_pairs: tuple[tuple[str, str], ...],
    current: np.ndarray,
    required: np.ndarray,
    target: np.ndarray,
) -> list[tuple]:
    """Exhaust all three-input gates on each source-coupled wire pair."""
    indices = {name: index for index, name in enumerate(names)}
    ranking = []
    for stage in FMUL_STAGES:
        for left_suffix, right_suffix in suffix_pairs:
            left_name = f"{stage}.{left_suffix}"
            right_name = f"{stage}.{right_suffix}"
            if left_name not in indices or right_name not in indices:
                continue
            left = matrix[:, indices[left_name]]
            right = matrix[:, indices[right_name]]
            selector = 4 * current + 2 * left + right
            for gate in range(256):
                prediction = ((gate >> selector) & 1).astype(np.uint8)
                wrong = prediction != required
                changed = prediction != current
                ranking.append((
                    int(wrong.sum()),
                    int(wrong[target].sum()),
                    int(wrong[~target].sum()),
                    int(changed[~target].sum()),
                    f"0x{gate:02x}", left_name, right_name,
                ))
    ranking.sort()
    return ranking


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

    prepared, source_rows, names = prepare(args)
    row_count = len(prepared)
    signal_count = len(names)
    matrix = np.frombuffer(
        b"".join(item.signals for item in prepared), dtype=np.uint8
    ).reshape(row_count, signal_count)
    current = np.asarray([item.current for item in prepared], dtype=np.uint8)
    required = np.asarray([item.required for item in prepared], dtype=np.uint8)
    target = np.asarray([item.target for item in prepared], dtype=bool)
    target_count = int(target.sum())

    gate_ranking = []
    for signal_index, name in enumerate(names):
        signal = matrix[:, signal_index]
        for gate in range(16):
            prediction = gate_output(gate, current, signal)
            wrong = prediction != required
            changed = prediction != current
            gate_ranking.append((
                int(wrong.sum()),
                int(wrong[target].sum()),
                int(wrong[~target].sum()),
                int(changed[~target].sum()),
                GATE_NAMES[gate], gate, name,
            ))
    gate_ranking.sort()
    gate_exact = [item for item in gate_ranking if item[0] == 0]
    gate_improvements = [
        item for item in gate_ranking
        if item[2] == 0 and item[1] < target_count
    ]

    sequences = signal_sequences(names, matrix)
    one_input = h1432.one_input_recurrences(
        sequences, current, required, target
    )
    pair_names = paired_sequence_names(tuple(sequences))
    pair_gates = paired_global_gates(
        names, matrix, pair_names, current, required, target
    )
    paired_affine = paired_affine_recurrences(
        sequences, pair_names, current, required, target
    )
    pair_gate_exact = [item for item in pair_gates if item[0] == 0]
    pair_gate_improvements = [
        item for item in pair_gates
        if item[2] == 0 and item[1] < target_count
    ]
    one_exact = [item for item in one_input if item[0] == 0]
    pair_exact = [item for item in paired_affine if item[0] == 0]
    one_improvements = [
        item for item in one_input
        if item[2] == 0 and item[1] < target_count
    ]
    pair_improvements = [
        item for item in paired_affine
        if item[2] == 0 and item[1] < target_count
    ]
    mixed, collision_targets = collision_summary(prepared)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
            ("primary_paper", PAPER_PATH),
            ("verification_paper", VERIFICATION_PAPER),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(f"primary_source\t{PAPER}\tdoi:{PAPER_DOI}\n")
        output.write("source_vendor\tAMD\n")
        output.write(
            "source_scope\tphysical_plausibility_not_Intel_or_Skylake_provenance\n"
        )
        output.write(
            "candidate_policy\tFigure3_contiguous_14PP_plus_2feedback_"
            "three_level_4to2_tree\n"
        )
        output.write(
            "carry4_interpretation\tcarry0_and_carry1_low27_endpoints_"
            "from_each_of_first_two_passes_bounded_not_published_RTL\n"
        )
        output.write("projection_precisions\t67,68\n")
        output.write("operand_roles\twritten,swapped\n")
        output.write("chunk_order\tlow_first_variable,27,27\n")
        output.write("fmul_stages\t" + ",".join(FMUL_STAGES) + "\n")
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{row_count}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{row_count - target_count}\n")
        output.write(f"candidate_signals\t{signal_count}\n")
        output.write(f"homologous_signal_streams\t{len(sequences)}\n")
        output.write(f"global_gate_programs\t{len(gate_ranking)}\n")
        output.write(f"global_gate_exact\t{len(gate_exact)}\n")
        output.write(
            "global_gate_zero_control_improvements\t"
            f"{len(gate_improvements)}\n"
        )
        output.write(f"one_input_recurrence_programs\t{len(one_input)}\n")
        output.write(f"one_input_recurrence_exact\t{len(one_exact)}\n")
        output.write(
            "one_input_recurrence_zero_control_improvements\t"
            f"{len(one_improvements)}\n"
        )
        output.write(f"source_coupled_stream_pairs\t{len(pair_names)}\n")
        output.write(f"source_coupled_global_gate_programs\t{len(pair_gates)}\n")
        output.write(f"source_coupled_global_gate_exact\t{len(pair_gate_exact)}\n")
        output.write(
            "source_coupled_global_gate_zero_control_improvements\t"
            f"{len(pair_gate_improvements)}\n"
        )
        output.write(f"paired_affine_recurrence_programs\t{len(paired_affine)}\n")
        output.write(f"paired_affine_recurrence_exact\t{len(pair_exact)}\n")
        output.write(
            "paired_affine_recurrence_zero_control_improvements\t"
            f"{len(pair_improvements)}\n"
        )
        output.write(f"complete_history_mixed_groups\t{len(mixed)}\n")
        output.write(f"targets_in_complete_history_mixed_groups\t{collision_targets}\n")
        output.write(
            "complete_history_interpretation\t"
            "collision_free_lookup_fingerprint_not_closed_form\n"
        )

        output.write("\n[best global gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in gate_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best one-input recurrences]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tsignal\tinitial\t"
            "transition_mask\ttransition\toutput_mask\toutput\tstate_ones\t"
            "target_state_ones\n"
        )
        for item in one_input[:128]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best source-coupled global gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate_mask\tleft_signal\tright_signal\n"
        )
        for item in pair_gates[:128]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best paired affine recurrences]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tleft_signal\tright_signal\t"
            "initial\tcoefficients\toutput_mask\toutput\tstate_ones\t"
            "target_state_ones\n"
        )
        for item in paired_affine[:128]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[complete-history mixed groups]\n")
        output.write(
            "branch\tcurrent\trequired0\trequired1\ttargets\texample0\t"
            "example1\n"
        )
        for key, count0, count1, targets, example0, example1 in mixed[:256]:
            branch, incumbent, _ = key
            target_text = ",".join(
                f"{mode}:{operand}" for mode, operand in targets
            )
            output.write(
                f"{branch}\t{incumbent}\t{count0}\t{count1}\t{target_text}\t"
                f"{example0[0]}:{example0[1]}\t{example1[0]}:{example1[1]}\n"
            )

        output.write("\n[target structural traces]\n")
        output.write("mode\top\tcurrent\trequired\titeration_traces\n")
        for item in prepared:
            if item.target:
                output.write(
                    f"{item.row['mode']}\t{item.row['op']}\t{item.current}\t"
                    f"{item.required}\t{item.trace!r}\n"
                )

        output.write("\n[result]\n")
        output.write(
            "canonical_iterative_feedback_selector\t"
            + ("exact_program_found\n"
               if gate_exact or pair_gate_exact or one_exact or pair_exact
               else "no_exact_program\n")
        )
        output.write(
            "scope\toptimized_four_wire_carry_recurrence_unpublished_"
            "and_not_excluded\n"
        )

    print(
        f"wrote {args.report}: rows={row_count} signals={signal_count} "
        f"gate_exact={len(gate_exact)} pair_gate_exact={len(pair_gate_exact)} "
        f"one_exact={len(one_exact)} "
        f"pair_exact={len(pair_exact)} collision_targets={collision_targets}",
        flush=True,
    )


if __name__ == "__main__":
    main()
