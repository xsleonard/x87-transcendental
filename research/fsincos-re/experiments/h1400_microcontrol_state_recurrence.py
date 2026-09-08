#!/usr/bin/env python3
"""Bounded audit of fixed microcontrol/carry-history state at R59.

The current R59 residual is sparse enough that a static gate search can hide
the more physical alternative: the terminal branch may observe a small state
register updated by the fixed cosine program.  This audit reconstructs
the twelve value-producing phases of the numerical model and
tests fixed state recurrences over patent-bounded rounding/carry symbols.

The phase order is

    square, fourth,
    negative.mul1, positive.mul1,
    negative.add1, positive.add1,
    negative.mul2, positive.mul2,
    negative.add2, positive.add2,
    left, right.

The tested recurrences use relative phase, operation kind, and lane.
They do not require absolute hardware addresses.  Since all three are
fixed for every row, a control-only machine is constant within an R59 branch;
only the input-determined carry/history symbol can separate rows.

Two recurrence families are exhausted:

1. Every two-state Boolean transition, with one law globally, independent
   FMUL/FADD laws, or independent common/negative/positive-lane laws.
2. Every affine four-state transition modulo four with a shared multiplier
   on prior state and symbol, and either global, FMUL/FADD, lane, or affine
   phase bias.

Every phase is allowed as the output latch point.  At that point each of the
four existing R59 branch classes receives an arbitrary state decoder.  This
branch-local decoder is a generous upper bound on any literal ROM-address
projection; if even it has an opposite-label state collision, the recurrence
cannot be the missing selector.  No operand identity, threshold, decision
tree, or hardware execution is used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import quantize, schedule
from h1191_grs_history_isomorphism import compare_values
from h1322_attached_history_field_audit import history_fields


STAGES = (
    "square", "fourth",
    "negative.mul1", "positive.mul1",
    "negative.add1", "positive.add1",
    "negative.mul2", "positive.mul2",
    "negative.add2", "positive.add2",
    "left", "right",
)
KINDS = (
    "mul", "mul", "mul", "mul", "add", "add",
    "mul", "mul", "add", "add", "mul", "mul",
)
LANES = (
    "common", "common", "negative", "positive", "negative", "positive",
    "negative", "positive", "negative", "positive", "negative", "positive",
)
NATIVE = {
    "square": (67, False),
    "fourth": (67, False),
    "negative.mul1": (67, False),
    "positive.mul1": (67, False),
    "negative.add1": (64, True),
    "positive.add1": (64, True),
    "negative.mul2": (67, False),
    "positive.mul2": (67, False),
    "negative.add2": (64, True),
    "positive.add2": (64, True),
    "left": (67, False),
    "right": (67, False),
}

# These are semantic carry/rounding classes named by US5612909 or direct
# one-bit components of them.  Wider top/bottom remainder words are omitted:
# treating arbitrary operand bits as state input would defeat this audit.
BOOLEAN_FIELDS = (
    "discarded.any",
    "discarded.all_ones",
    "discarded.half",
    "discarded.below_half",
    "discarded.above_half",
    "discarded.guard",
    "discarded.round",
    "discarded.sticky",
    "round.increment",
    "round.direction.down",
    "round.direction.exact",
    "round.direction.up",
    "retained.lsb",
    "shift.parity",
    "remainder.tz.parity",
)
SYMBOL_FIELDS = (
    "discarded.top2",
    "discarded.bottom2",
    "discarded.grs2",
    "discarded.class4",
    "discarded.tz_mod4",
    "retained.low2",
    "shift.mod4",
    "round.increment_inexact",
    "round.direction_increment",
)
BRANCHES = ("band", "corner", "q67th2", "tie")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def trailing_zeros(value: int) -> int:
    return (value & -value).bit_length() - 1 if value else 0


def rounding_symbols(operation, bits: int, nearest: bool) -> dict[str, int]:
    """The fixed two-bit symbol vocabulary used by h1330, dependency-free."""
    stored = quantize(operation, bits, nearest)
    shift = max(0, operation.magnitude.bit_length() - bits)
    denominator = 1 << shift if shift else 1
    remainder = operation.magnitude & (denominator - 1) if shift else 0
    retained = operation.magnitude >> shift
    half = denominator >> 1 if shift else 0
    increment = int(stored.significand != retained)
    inexact = int(bool(remainder))
    if not remainder:
        class4 = 0
    elif remainder < half:
        class4 = 1
    elif remainder == half:
        class4 = 2
    else:
        class4 = 3
    if shift >= 2:
        top2 = remainder >> (shift - 2)
    else:
        top2 = remainder << (2 - shift)
    bottom2 = remainder & 3
    guard = (remainder >> (shift - 1)) & 1 if shift else 0
    sticky = int(
        shift > 1 and bool(remainder & ((1 << (shift - 1)) - 1)))
    exact_value = type(stored)(
        operation.sign, operation.exponent, operation.magnitude)
    direction = compare_values(stored, exact_value)
    direction_code = {-1: 0, 0: 1, 1: 2}[direction]
    return {
        "discarded.top2": top2 & 3,
        "discarded.bottom2": bottom2,
        "discarded.grs2": ((guard << 1) | sticky) & 3,
        "discarded.class4": class4,
        "discarded.tz_mod4": trailing_zeros(remainder) & 3,
        "retained.low2": retained & 3,
        "shift.mod4": shift & 3,
        "round.increment_inexact": increment | (inexact << 1),
        "round.direction_increment": direction_code | (increment << 1),
    }


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError("empty feature bank")
    unknown = sorted({row["branch"] for row in rows} - set(BRANCHES))
    if unknown:
        raise RuntimeError("unknown R59 branches: " + ", ".join(unknown))
    return rows


def byte_columns(count: int, names: tuple[str, ...]
                 ) -> dict[str, list[bytearray]]:
    return {
        name: [bytearray(count) for _ in STAGES]
        for name in names
    }


def bytes_to_mask(values: bytearray) -> int:
    packed = bytearray((len(values) + 7) // 8)
    for index, value in enumerate(values):
        packed[index >> 3] |= int(bool(value)) << (index & 7)
    return int.from_bytes(packed, "little")


def reconstruct(rows: list[dict[str, str]]):
    boolean = byte_columns(len(rows), BOOLEAN_FIELDS)
    symbols = byte_columns(len(rows), SYMBOL_FIELDS)
    sequences: dict[str, list[tuple[int, ...]]] = {
        name: [] for name in SYMBOL_FIELDS
    }
    joint_sequences: dict[str, list[tuple[tuple[int, ...], ...]]] = {
        "class4": [],
        "carry": [],
        "patent_joint": [],
    }
    for row_index, row in enumerate(rows):
        operations = schedule(row)
        stage_boolean = []
        stage_symbols = []
        for stage_index, stage in enumerate(STAGES):
            bits, nearest = NATIVE[stage]
            fields, _ = history_fields(operations[stage], bits, nearest)
            encoded = rounding_symbols(operations[stage], bits, nearest)
            stage_boolean.append(fields)
            stage_symbols.append(encoded)
            for name in BOOLEAN_FIELDS:
                boolean[name][stage_index][row_index] = fields[name]
            for name in SYMBOL_FIELDS:
                symbols[name][stage_index][row_index] = encoded[name]
        for name in SYMBOL_FIELDS:
            sequences[name].append(tuple(item[name] for item in stage_symbols))
        joint_sequences["class4"].append(tuple(
            (item["discarded.class4"],) for item in stage_symbols))
        joint_sequences["carry"].append(tuple(
            (item["round.increment_inexact"],
             item["round.direction_increment"])
            for item in stage_symbols))
        joint_sequences["patent_joint"].append(tuple(
            (item["discarded.class4"],
             item["round.direction_increment"],
             item["retained.low2"], item["shift.mod4"])
            for item in stage_symbols))
    boolean_masks = {
        name: tuple(bytes_to_mask(column) for column in columns)
        for name, columns in boolean.items()
    }
    symbol_masks = {
        name: tuple(
            (bytes_to_mask(bytearray(value & 1 for value in column)),
             bytes_to_mask(bytearray((value >> 1) & 1 for value in column)))
            for column in columns)
        for name, columns in symbols.items()
    }
    return boolean_masks, symbol_masks, sequences, joint_sequences


def transition2(law: int, state: int, symbol: int, all_mask: int) -> int:
    not_state = all_mask ^ state
    not_symbol = all_mask ^ symbol
    result = 0
    if law & 1:
        result |= not_state & not_symbol
    if law & 2:
        result |= state & not_symbol
    if law & 4:
        result |= not_state & symbol
    if law & 8:
        result |= state & symbol
    return result


def masks4(low: int, high: int, all_mask: int) -> tuple[int, ...]:
    not_low = all_mask ^ low
    not_high = all_mask ^ high
    return (
        not_low & not_high,
        low & not_high,
        not_low & high,
        low & high,
    )


def transition4(
        state: tuple[int, int], symbol: tuple[int, int],
        a: int, b: int, c: int, all_mask: int) -> tuple[int, int]:
    state_cells = masks4(*state, all_mask)
    symbol_cells = masks4(*symbol, all_mask)
    output_low = 0
    output_high = 0
    for old, old_cell in enumerate(state_cells):
        for incoming, incoming_cell in enumerate(symbol_cells):
            cell = old_cell & incoming_cell
            value = (a * old + b * incoming + c) & 3
            if value & 1:
                output_low |= cell
            if value & 2:
                output_high |= cell
    return output_low, output_high


def projection_scores(
        state_cells: tuple[int, ...], branch_masks: dict[str, int],
        positive_mask: int, all_mask: int
        ) -> tuple[tuple[int, int, int, int, str],
                   tuple[int, int, int, int, str] | None]:
    negative_mask = all_mask ^ positive_mask
    errors = positive_errors = negative_errors = predicted = 0
    decoders = []
    cells = []
    for branch in BRANCHES:
        decoder = 0
        branch_mask = branch_masks[branch]
        for value, state_cell in enumerate(state_cells):
            cell = branch_mask & state_cell
            positives = (cell & positive_mask).bit_count()
            negatives = (cell & negative_mask).bit_count()
            cells.append((branch, value, positives, negatives))
            if positives > negatives:
                decoder |= 1 << value
                negative_errors += negatives
                errors += negatives
                predicted += positives + negatives
            else:
                positive_errors += positives
                errors += positives
        decoders.append(f"{branch}:{decoder:x}")
    best = (errors, positive_errors, negative_errors, predicted,
            ",".join(decoders))
    if predicted:
        return best, best

    # The optimal decoder is usually the all-zero incumbent because positives
    # are extremely sparse.  Also report the best decoder forced to act.  With
    # no majority-positive cell, enabling more than one cell can only add its
    # independent (negative-positive) penalty, so one cell is optimal.
    active = []
    for branch, value, positives, negatives in cells:
        if not positives:
            continue
        branch_decoders = [f"{name}:0" for name in BRANCHES]
        branch_decoders[BRANCHES.index(branch)] = f"{branch}:{1 << value:x}"
        active.append((
            positive_mask.bit_count() - positives + negatives,
            positive_mask.bit_count() - positives,
            negatives,
            positives + negatives,
            ",".join(branch_decoders),
        ))
    return best, min(active) if active else None


def retain_best(best: list[tuple], item: tuple, limit: int = 256) -> None:
    best.append(item)
    if len(best) >= 2 * limit:
        best.sort()
        del best[limit:]


def laws_for_scheme(scheme: str):
    if scheme == "shared":
        for law in range(16):
            yield (law,), tuple(law for _ in STAGES)
    elif scheme == "opcode":
        for mul_law, add_law in itertools.product(range(16), repeat=2):
            yield (mul_law, add_law), tuple(
                mul_law if kind == "mul" else add_law for kind in KINDS)
    elif scheme == "lane":
        for common, negative, positive in itertools.product(range(16), repeat=3):
            law = {"common": common, "negative": negative, "positive": positive}
            yield (common, negative, positive), tuple(law[lane] for lane in LANES)
    else:
        raise ValueError(scheme)


def audit_two_state(
        boolean_masks, branch_masks, positive_mask, all_mask):
    reports = {}
    for scheme in ("shared", "opcode", "lane"):
        best: list[tuple] = []
        active_best: list[tuple] = []
        zero_collateral_best: list[tuple] = []
        exact = 0
        candidates = 0
        for field in BOOLEAN_FIELDS:
            for laws, stage_laws in laws_for_scheme(scheme):
                for seed in (0, 1):
                    state = all_mask if seed else 0
                    for tap, (law, symbol) in enumerate(
                            zip(stage_laws, boolean_masks[field]), start=1):
                        state = transition2(law, state, symbol, all_mask)
                        score, active_score = projection_scores(
                            (all_mask ^ state, state), branch_masks,
                            positive_mask, all_mask)
                        item = (*score[:4], field, seed, laws, tap,
                                STAGES[tap - 1], score[4])
                        retain_best(best, item)
                        if active_score is not None:
                            active_item = (
                                *active_score[:4], field, seed, laws, tap,
                                STAGES[tap - 1], active_score[4])
                            retain_best(active_best, active_item)
                            if active_score[2] == 0:
                                retain_best(zero_collateral_best, active_item)
                        exact += int(score[0] == 0)
                        candidates += 1
        best.sort()
        active_best.sort()
        zero_collateral_best.sort()
        reports[scheme] = (
            candidates, exact, best[:256], active_best[:256],
            zero_collateral_best[:256])
    return reports


def biases_for_scheme(scheme: str):
    if scheme == "shared":
        for a, b, c in itertools.product(range(4), repeat=3):
            yield (a, b, c), tuple(c for _ in STAGES), a, b
    elif scheme == "opcode":
        for a, b, cmul, cadd in itertools.product(range(4), repeat=4):
            yield (a, b, cmul, cadd), tuple(
                cmul if kind == "mul" else cadd for kind in KINDS), a, b
    elif scheme == "lane":
        for a, b, common, negative, positive in itertools.product(
                range(4), repeat=5):
            bias = {"common": common, "negative": negative,
                    "positive": positive}
            yield ((a, b, common, negative, positive),
                   tuple(bias[lane] for lane in LANES), a, b)
    elif scheme == "phase":
        for a, b, base, phase in itertools.product(range(4), repeat=4):
            yield ((a, b, base, phase),
                   tuple((base + phase * index) & 3
                         for index in range(len(STAGES))), a, b)
    else:
        raise ValueError(scheme)


def audit_four_state(
        symbol_masks, branch_masks, positive_mask, all_mask):
    reports = {}
    for scheme in ("shared", "opcode", "lane", "phase"):
        best: list[tuple] = []
        active_best: list[tuple] = []
        zero_collateral_best: list[tuple] = []
        exact = 0
        candidates = 0
        for field in SYMBOL_FIELDS:
            for coefficients, biases, a, b in biases_for_scheme(scheme):
                for seed in range(4):
                    state = (
                        all_mask if seed & 1 else 0,
                        all_mask if seed & 2 else 0,
                    )
                    for tap, (bias, symbol) in enumerate(
                            zip(biases, symbol_masks[field]), start=1):
                        state = transition4(
                            state, symbol, a, b, bias, all_mask)
                        score, active_score = projection_scores(
                            masks4(*state, all_mask), branch_masks,
                            positive_mask, all_mask)
                        item = (*score[:4], field, seed, coefficients, tap,
                                STAGES[tap - 1], score[4])
                        retain_best(best, item)
                        if active_score is not None:
                            active_item = (
                                *active_score[:4], field, seed, coefficients,
                                tap, STAGES[tap - 1], active_score[4])
                            retain_best(active_best, active_item)
                            if active_score[2] == 0:
                                retain_best(zero_collateral_best, active_item)
                        exact += int(score[0] == 0)
                        candidates += 1
        best.sort()
        active_best.sort()
        zero_collateral_best.sort()
        reports[scheme] = (
            candidates, exact, best[:256], active_best[:256],
            zero_collateral_best[:256])
    return reports


def sequence_collisions(rows, sequences):
    reports = {}
    for name, values in sequences.items():
        groups: dict[tuple, Counter] = defaultdict(Counter)
        members: dict[tuple, dict[str, str]] = defaultdict(dict)
        for row, sequence in zip(rows, values):
            key = (row["branch"], sequence)
            groups[key][row["label"]] += 1
            members[key].setdefault(row["label"], row["op"])
        mixed = [key for key, counts in groups.items()
                 if counts["POS"] and counts["NEG"]]
        reports[name] = {
            "groups": len(groups),
            "mixed_groups": len(mixed),
            "positive_in_mixed": sum(groups[key]["POS"] for key in mixed),
            "negative_in_mixed": sum(groups[key]["NEG"] for key in mixed),
            "witnesses": [
                (key[0], groups[key]["POS"], groups[key]["NEG"],
                 members[key]["POS"], members[key]["NEG"])
                for key in mixed[:32]
            ],
        }
    return reports


def write_state_reports(output, title: str, reports) -> None:
    for scheme, (candidates, exact, best, active_best,
                 zero_collateral_best) in reports.items():
        output.write(f"\n[{title} {scheme}]\n")
        output.write(f"candidates\t{candidates}\n")
        output.write(f"exact\t{exact}\n")
        header = (
            "errors\tpositive_errors\tnegative_errors\tpredicted_positive\t"
            "symbol\tseed\ttransition\ttap\tphase\tdecoder\n")
        for subtitle, items in (
                ("best overall", best),
                ("best nontrivial", active_best),
                ("best zero-collateral", zero_collateral_best)):
            output.write("\n" + subtitle + "\n")
            output.write(header)
            for item in items[:32]:
                output.write("\t".join(map(str, item)) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))

    rows = read_rows(args.features)
    all_mask = (1 << len(rows)) - 1
    positive_mask = sum(
        int(row["label"] == "POS") << index for index, row in enumerate(rows))
    branch_masks = {
        branch: sum(int(row["branch"] == branch) << index
                    for index, row in enumerate(rows))
        for branch in BRANCHES
    }
    boolean, symbols, symbol_sequences, joint_sequences = reconstruct(rows)
    sequence_report = sequence_collisions(
        rows, {**symbol_sequences, **joint_sequences})
    two_state = audit_two_state(
        boolean, branch_masks, positive_mask, all_mask)
    four_state = audit_four_state(
        symbols, branch_masks, positive_mask, all_mask)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write("features_sha256\t" + digest(args.features) + "\n")
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write("candidate_policy\tfixed_control_state_recurrences\n")
        output.write(f"rows\t{len(rows)}\n")
        output.write(f"positive_rows\t{positive_mask.bit_count()}\n")
        output.write("stage_order\t" + ",".join(STAGES) + "\n")
        output.write("operation_kinds\t" + ",".join(KINDS) + "\n")
        output.write("lane_order\t" + ",".join(LANES) + "\n")
        output.write("absolute_rom_addresses\tunavailable_not_invented\n")
        output.write("control_only_result\timpossible_branch_local_mixed_labels\n")
        output.write("\n[branch label counts]\n")
        output.write("branch\tpositive\tnegative\n")
        for branch in BRANCHES:
            mask = branch_masks[branch]
            output.write(
                f"{branch}\t{(mask & positive_mask).bit_count()}\t"
                f"{(mask & (all_mask ^ positive_mask)).bit_count()}\n")

        output.write("\n[complete input-sequence collisions]\n")
        output.write(
            "symbol\tgroups\tmixed_groups\tpositive_in_mixed\t"
            "negative_in_mixed\n")
        for name, report in sequence_report.items():
            output.write(
                f"{name}\t{report['groups']}\t{report['mixed_groups']}\t"
                f"{report['positive_in_mixed']}\t"
                f"{report['negative_in_mixed']}\n")
        output.write("\n[sequence collision witnesses]\n")
        output.write(
            "symbol\tbranch\tpositive_count\tnegative_count\t"
            "positive_operand\tnegative_operand\n")
        for name, report in sequence_report.items():
            for witness in report["witnesses"]:
                output.write(name + "\t" + "\t".join(map(str, witness)) + "\n")

        write_state_reports(output, "two-state arbitrary Boolean", two_state)
        write_state_reports(output, "four-state affine mod4", four_state)

    exact_total = sum(report[1] for report in two_state.values()) + sum(
        report[1] for report in four_state.values())
    best_error = min(
        report[2][0][0]
        for report in (*two_state.values(), *four_state.values()))
    print(
        f"wrote {args.report}: rows={len(rows)} positive={positive_mask.bit_count()} "
        f"exact={exact_total} best_errors={best_error}",
        flush=True,
    )


if __name__ == "__main__":
    main()
