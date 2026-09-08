#!/usr/bin/env python3
"""Audit stagewise Intel redundant-LZA control histories at R59.

h1400 exhausted fixed microcontrol recurrences driven by numerical rounding
and carry summaries.  h1421 later recovered a structurally different input:
the literal redundant-format leading-zero anticipator from Intel US7024439.
This audit applies that published equation at all twelve arithmetic sites in
the recovered six-term cosine schedule, not merely at the terminal subtract.

FMUL sites use the documented P5 67x64 radix-8 tree, with the low radix-8
digit reinserted through one 3:2 compressor when both inputs are 67 bits.
FADD sites present their two aligned magnitude rows directly to the same LZA.
Every redundant pair is checked against the exact scheduled magnitude before
any label is consulted.

The audit first reports branch-local mixed-label collisions on complete
input streams.  Such a collision disproves every deterministic FSM driven
only by that stream, regardless of its state count.  It then exhausts the
same bounded fixed one-bit Boolean and two-bit affine recurrence families as
h1400, with arbitrary branch-local output decoders at every tap.  There are
no operand identities, thresholds, decision trees, or hardware executions.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1100_p5_multiplier_tree import PRODUCT_MASK, multiplier_tree
from h1128_fused_terminal_csa_mine import MASK, csa3
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    Value,
    add_same_sign,
    multiply,
    quantize,
    row_value,
    schedule,
)
from h1386_current_r59_feature_bank import dump
from h1400_microcontrol_state_recurrence import (
    BRANCHES,
    KINDS,
    LANES,
    STAGES,
    biases_for_scheme,
    bytes_to_mask,
    laws_for_scheme,
    masks4,
    projection_scores,
    read_rows,
    retain_best,
    transition2,
    transition4,
)
from h1421_intel_redundant_lza import (
    PATTERNS,
    UNCERTAIN_PATTERNS,
    WIDTH,
    lza_vector,
)


BOOLEAN_FIELDS = (
    "correction.one",
    "correction.two",
    "correction.nonzero",
    "correction.lowbit",
    "correction.highbit",
    "leading_pattern.uncertain",
    *(f"leading_pattern.{pattern}" for pattern in PATTERNS),
    *(f"predicted_position.bit{bit}" for bit in range(8)),
    *(f"actual_position.bit{bit}" for bit in range(8)),
    *(f"count.bit{bit}" for bit in range(8)),
)
SYMBOL_FIELDS = (
    "correction",
    "predicted_position.low2",
    "actual_position.low2",
    "count.low2",
    "leading_pattern.class4",
)
def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def product_pair(left: Value, right: Value) -> tuple[int, int, int]:
    """Return an exact P5-like redundant pair for a <=67 by <=67 product."""
    if left.significand.bit_length() > 67 or right.significand.bit_length() > 67:
        raise RuntimeError("product operand exceeds recovered P5 width")
    # The recovered P5 multiplier's X port is a normalized 67-bit bus.  A
    # 64-bit materialized value occupies its high 64 positions, so normalize
    # the integer here and remember the common product scale.  This scale can
    # move the predicted position but cannot change the LZA correction.
    scale = 67 - left.significand.bit_length()
    if scale < 0:
        raise RuntimeError("product X operand exceeds recovered P5 width")
    physical_left = left.significand << scale
    state = multiplier_tree(physical_left, right.significand >> 3)
    sum_vector, carry_vector = csa3(
        (state["sum"] & PRODUCT_MASK) << 3,
        (state["carry"] & PRODUCT_MASK) << 3,
        physical_left * (right.significand & 7),
    )
    product_mask = (1 << 134) - 1
    sum_vector &= product_mask
    carry_vector &= product_mask
    exact = (left.significand * right.significand) << scale
    if sum_vector + carry_vector == exact + (1 << 134):
        # The patented redundant LZA explicitly accepts a negative carry
        # word.  Sign-extend that 134-bit word into the common audit width.
        carry_vector |= MASK ^ product_mask
    if (sum_vector + carry_vector) & MASK != exact:
        raise AssertionError("P5 redundant product changed exact magnitude")
    return sum_vector, carry_vector, scale


def add_pair(left: Value, right: Value) -> tuple[int, int, int]:
    if left.sign != right.sign:
        raise AssertionError("expected same-sign Horner add")
    exponent = min(left.exponent, right.exponent)
    pair = (
        left.significand << (left.exponent - exponent),
        right.significand << (right.exponent - exponent),
    )
    if sum(pair) != add_same_sign(left, right).magnitude:
        raise AssertionError("aligned FADD pair changed exact magnitude")
    return pair[0], pair[1], 0


def stage_pairs(row: dict[str, str]) -> dict[str, tuple[int, int, int]]:
    mag = row_value(row, "mag")
    pairs: dict[str, tuple[int, int, int]] = {}

    pairs["square"] = product_pair(mag, mag)
    square_op = multiply(mag, mag)
    square = quantize(square_op, 67, False)
    pairs["fourth"] = product_pair(square, square)
    fourth_op = multiply(square, square)
    fourth = quantize(fourth_op, 67, False)

    negative_mul1_op = multiply(fourth, Value(*CONSTANTS[5]))
    positive_mul1_op = multiply(fourth, Value(*CONSTANTS[6]))
    pairs["negative.mul1"] = product_pair(fourth, Value(*CONSTANTS[5]))
    pairs["positive.mul1"] = product_pair(fourth, Value(*CONSTANTS[6]))
    negative_mul1 = quantize(negative_mul1_op, 67, False)
    positive_mul1 = quantize(positive_mul1_op, 67, False)

    pairs["negative.add1"] = add_pair(Value(*CONSTANTS[3]), negative_mul1)
    pairs["positive.add1"] = add_pair(Value(*CONSTANTS[4]), positive_mul1)
    negative_add1_op = add_same_sign(Value(*CONSTANTS[3]), negative_mul1)
    positive_add1_op = add_same_sign(Value(*CONSTANTS[4]), positive_mul1)
    negative_add1 = quantize(negative_add1_op, 64, True)
    positive_add1 = quantize(positive_add1_op, 64, True)

    pairs["negative.mul2"] = product_pair(fourth, negative_add1)
    pairs["positive.mul2"] = product_pair(fourth, positive_add1)
    negative_mul2_op = multiply(fourth, negative_add1)
    positive_mul2_op = multiply(fourth, positive_add1)
    negative_mul2 = quantize(negative_mul2_op, 67, False)
    positive_mul2 = quantize(positive_mul2_op, 67, False)

    pairs["negative.add2"] = add_pair(Value(*CONSTANTS[1]), negative_mul2)
    pairs["positive.add2"] = add_pair(Value(*CONSTANTS[2]), positive_mul2)
    negative_add2_op = add_same_sign(Value(*CONSTANTS[1]), negative_mul2)
    positive_add2_op = add_same_sign(Value(*CONSTANTS[2]), positive_mul2)
    negative = quantize(negative_add2_op, 64, True)
    positive = quantize(positive_add2_op, 64, True)

    pairs["left"] = product_pair(square, negative)
    pairs["right"] = product_pair(fourth, positive)

    operations = schedule(row)
    for stage in STAGES:
        sum_vector, carry_vector, scale = pairs[stage]
        if ((sum_vector + carry_vector) & MASK
                != operations[stage].magnitude << scale):
            raise AssertionError(f"{stage} pair mismatch for {row['op']}")
    return pairs


def lza_fields(pair: tuple[int, int, int]) -> tuple[dict[str, int], dict[str, int]]:
    sum_vector, carry_vector, _ = pair
    vector, predicted, pattern = lza_vector(sum_vector, carry_vector)
    exact = (sum_vector + carry_vector) & MASK
    actual = exact.bit_length() - 1
    if actual < 0 or exact > MASK:
        raise RuntimeError("invalid scheduled exact magnitude")
    correction = predicted - actual
    if correction not in (0, 1, 2):
        raise AssertionError(
            f"published LZA correction envelope violated: {correction}"
        )
    count = (WIDTH - 1) - predicted
    pattern_code = PATTERNS.index(pattern) if pattern in PATTERNS else len(PATTERNS)
    boolean = {
        "correction.one": int(correction == 1),
        "correction.two": int(correction == 2),
        "correction.nonzero": int(correction != 0),
        "correction.lowbit": correction & 1,
        "correction.highbit": (correction >> 1) & 1,
        "leading_pattern.uncertain": int(pattern in UNCERTAIN_PATTERNS),
    }
    for candidate in PATTERNS:
        boolean[f"leading_pattern.{candidate}"] = int(pattern == candidate)
    for bit in range(8):
        boolean[f"predicted_position.bit{bit}"] = (predicted >> bit) & 1
        boolean[f"actual_position.bit{bit}"] = (actual >> bit) & 1
        boolean[f"count.bit{bit}"] = (count >> bit) & 1
    symbols = {
        "correction": correction,
        "predicted_position.low2": predicted & 3,
        "actual_position.low2": actual & 3,
        "count.low2": count & 3,
        "leading_pattern.class4": pattern_code & 3,
    }
    return boolean, symbols


def reconstruct(rows: list[dict[str, str]]):
    boolean_values = {
        name: [bytearray(len(rows)) for _ in STAGES]
        for name in BOOLEAN_FIELDS
    }
    symbol_values = {
        name: [bytearray(len(rows)) for _ in STAGES]
        for name in SYMBOL_FIELDS
    }
    sequences: dict[str, list[tuple[int, ...]]] = {
        name: [] for name in (*BOOLEAN_FIELDS, *SYMBOL_FIELDS)
    }
    sequences["correction_joint"] = []
    sequences["control_joint"] = []
    target_traces = []
    correction_distribution = Counter()
    for row_index, row in enumerate(rows):
        pairs = stage_pairs(row)
        stage_boolean = []
        stage_symbols = []
        stage_trace = []
        for stage_index, stage in enumerate(STAGES):
            boolean, symbols = lza_fields(pairs[stage])
            stage_boolean.append(boolean)
            stage_symbols.append(symbols)
            correction_distribution[stage, symbols["correction"]] += 1
            stage_trace.append((
                symbols["correction"],
                symbols["predicted_position.low2"],
                symbols["actual_position.low2"],
                symbols["leading_pattern.class4"],
            ))
            for name in BOOLEAN_FIELDS:
                boolean_values[name][stage_index][row_index] = boolean[name]
            for name in SYMBOL_FIELDS:
                symbol_values[name][stage_index][row_index] = symbols[name]
        for name in BOOLEAN_FIELDS:
            sequences[name].append(tuple(item[name] for item in stage_boolean))
        for name in SYMBOL_FIELDS:
            sequences[name].append(tuple(item[name] for item in stage_symbols))
        sequences["correction_joint"].append(tuple(
            (item["correction"],) for item in stage_symbols
        ))
        sequences["control_joint"].append(tuple(stage_trace))
        if row["label"] == "POS":
            target_traces.append((row["op"], tuple(stage_trace)))

    boolean_masks = {
        name: tuple(bytes_to_mask(column) for column in columns)
        for name, columns in boolean_values.items()
    }
    symbol_masks = {
        name: tuple(
            (
                bytes_to_mask(bytearray(value & 1 for value in column)),
                bytes_to_mask(bytearray((value >> 1) & 1 for value in column)),
            )
            for column in columns
        )
        for name, columns in symbol_values.items()
    }
    return (
        boolean_masks,
        symbol_masks,
        sequences,
        correction_distribution,
        target_traces,
    )


def sequence_collisions(rows, sequences):
    reports = {}
    for name, values in sequences.items():
        groups = defaultdict(Counter)
        members = defaultdict(lambda: defaultdict(list))
        for row, sequence in zip(rows, values):
            key = (row["branch"], sequence)
            groups[key][row["label"]] += 1
            members[key][row["label"]].append(row["op"])
        mixed = [key for key, counts in groups.items()
                 if counts["POS"] and counts["NEG"]]
        reports[name] = {
            "groups": len(groups),
            "mixed": len(mixed),
            "positive_in_mixed": sum(groups[key]["POS"] for key in mixed),
            "negative_in_mixed": sum(groups[key]["NEG"] for key in mixed),
            "witnesses": [
                (
                    key[0], groups[key]["POS"], groups[key]["NEG"],
                    members[key]["POS"][0], members[key]["NEG"][0],
                )
                for key in mixed
            ],
        }
    return reports


def audit_two_state(boolean_masks, branch_masks, positive_mask, all_mask):
    reports = {}
    for scheme in ("shared", "opcode", "lane"):
        best = []
        active_best = []
        zero_collateral_best = []
        exact = candidates = 0
        for field in BOOLEAN_FIELDS:
            for laws, stage_laws in laws_for_scheme(scheme):
                for seed in (0, 1):
                    state = all_mask if seed else 0
                    for tap, (law, symbol) in enumerate(
                            zip(stage_laws, boolean_masks[field]), start=1):
                        state = transition2(law, state, symbol, all_mask)
                        score, active = projection_scores(
                            (all_mask ^ state, state), branch_masks,
                            positive_mask, all_mask,
                        )
                        item = (*score[:4], field, seed, laws, tap,
                                STAGES[tap - 1], score[4])
                        retain_best(best, item)
                        if active is not None:
                            active_item = (*active[:4], field, seed, laws, tap,
                                           STAGES[tap - 1], active[4])
                            retain_best(active_best, active_item)
                            if active[2] == 0:
                                retain_best(zero_collateral_best, active_item)
                        exact += int(score[0] == 0)
                        candidates += 1
        reports[scheme] = (
            candidates, exact, sorted(best), sorted(active_best),
            sorted(zero_collateral_best),
        )
    return reports


def audit_four_state(symbol_masks, branch_masks, positive_mask, all_mask):
    reports = {}
    for scheme in ("shared", "opcode", "lane", "phase"):
        best = []
        active_best = []
        zero_collateral_best = []
        exact = candidates = 0
        for field in SYMBOL_FIELDS:
            for coefficients, biases, a, b in biases_for_scheme(scheme):
                for seed in range(4):
                    state = (
                        all_mask if seed & 1 else 0,
                        all_mask if seed & 2 else 0,
                    )
                    for tap, (bias, symbol) in enumerate(
                            zip(biases, symbol_masks[field]), start=1):
                        state = transition4(state, symbol, a, b, bias, all_mask)
                        score, active = projection_scores(
                            masks4(*state, all_mask), branch_masks,
                            positive_mask, all_mask,
                        )
                        item = (*score[:4], field, seed, coefficients, tap,
                                STAGES[tap - 1], score[4])
                        retain_best(best, item)
                        if active is not None:
                            active_item = (*active[:4], field, seed,
                                           coefficients, tap, STAGES[tap - 1],
                                           active[4])
                            retain_best(active_best, active_item)
                            if active[2] == 0:
                                retain_best(zero_collateral_best, active_item)
                        exact += int(score[0] == 0)
                        candidates += 1
        reports[scheme] = (
            candidates, exact, sorted(best), sorted(active_best),
            sorted(zero_collateral_best),
        )
    return reports


def write_recurrences(output, title, reports):
    output.write(f"\n[{title}]\n")
    output.write("scheme\tcandidates\texact\tbest_errors\tbest_target_errors\t"
                 "best_control_errors\tbest_active_errors\t"
                 "zero_collateral_improvements\n")
    for scheme, (candidates, exact, best, active, zero) in reports.items():
        output.write(
            f"{scheme}\t{candidates}\t{exact}\t{best[0][0]}\t{best[0][1]}\t"
            f"{best[0][2]}\t{active[0][0] if active else '-'}\t{len(zero)}\n"
        )
        output.write("best\t" + "\t".join(map(str, best[0])) + "\n")
        if active:
            output.write("best_active\t" + "\t".join(map(str, active[0])) + "\n")
        if zero:
            output.write("best_zero_collateral\t" +
                         "\t".join(map(str, zero[0])) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--extra-op", default="3ffc d0d000000cc0b3f8")
    parser.add_argument("--extra-mode", default="rd")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = read_rows(args.features)
    if any(row["op"] == args.extra_op for row in rows):
        raise RuntimeError("extra operand is already in feature bank")
    extra = dump(str(args.model), args.extra_mode, [args.extra_op])[0]
    extra.update({"label": "POS", "desired": "carry1", "mode": args.extra_mode})
    rows.append(extra)

    (boolean_masks, symbol_masks, sequences, correction_distribution,
     target_traces) = reconstruct(rows)
    all_mask = (1 << len(rows)) - 1
    positive_mask = sum(
        (row["label"] == "POS") << index for index, row in enumerate(rows)
    )
    branch_masks = {
        branch: sum(
            (row["branch"] == branch) << index
            for index, row in enumerate(rows)
        )
        for branch in BRANCHES
    }
    collisions = sequence_collisions(rows, sequences)
    two_state = audit_two_state(
        boolean_masks, branch_masks, positive_mask, all_mask
    )
    four_state = audit_four_state(
        symbol_masks, branch_masks, positive_mask, all_mask
    )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"features_sha256\t{digest(args.features)}\n")
        output.write(f"model_sha256\t{digest(args.model)}\n")
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write("candidate_policy\tstagewise_US7024439_redundant_LZA_control\n")
        output.write(f"rows\t{len(rows)}\n")
        output.write(f"positive_rows\t{positive_mask.bit_count()}\n")
        output.write("stage_order\t" + ",".join(STAGES) + "\n")
        output.write("operation_kinds\t" + ",".join(KINDS) + "\n")
        output.write("lane_order\t" + ",".join(LANES) + "\n")
        output.write("representation\tP5_67x64_plus_low_radix8_or_aligned_FADD\n")
        output.write("arithmetic_check\texact_before_label_scoring\n")
        output.write("\n[complete input-sequence collisions]\n")
        output.write("symbol\tgroups\tmixed_groups\tpositive_in_mixed\t"
                     "negative_in_mixed\n")
        for name, report in collisions.items():
            output.write(
                f"{name}\t{report['groups']}\t{report['mixed']}\t"
                f"{report['positive_in_mixed']}\t"
                f"{report['negative_in_mixed']}\n"
            )
        output.write("\n[collision witnesses]\n")
        output.write("symbol\tbranch\tpositive_count\tnegative_count\t"
                     "positive_operand\tnegative_operand\n")
        for name, report in collisions.items():
            for witness in report["witnesses"][:32]:
                output.write(name + "\t" + "\t".join(map(str, witness)) + "\n")
        output.write("\n[correction distribution]\n")
        output.write("stage\tcorrection\trows\n")
        for (stage, correction), count in sorted(correction_distribution.items()):
            output.write(f"{stage}\t{correction}\t{count}\n")
        write_recurrences(output, "one-bit Boolean recurrences", two_state)
        write_recurrences(output, "two-bit affine recurrences", four_state)
        output.write("\n[target control traces]\n")
        output.write("operand\tstagewise_correction,predicted_low2,actual_low2,pattern4\n")
        for operand, trace in target_traces:
            rendered = ";".join(",".join(map(str, item)) for item in trace)
            output.write(f"{operand}\t{rendered}\n")

    total_candidates = sum(item[0] for item in two_state.values()) + sum(
        item[0] for item in four_state.values()
    )
    total_exact = sum(item[1] for item in two_state.values()) + sum(
        item[1] for item in four_state.values()
    )
    correction_collision = collisions["correction_joint"]
    print(
        f"wrote {args.report}: rows={len(rows)} candidates={total_candidates} "
        f"exact={total_exact} correction_mixed={correction_collision['mixed']} "
        f"positive_in_mixed={correction_collision['positive_in_mixed']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
