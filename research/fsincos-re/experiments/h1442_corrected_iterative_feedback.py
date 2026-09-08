#!/usr/bin/env python3
"""Audit the exact low-first feedback recurrence omitted by h1441.

Tan, Lemonds, and Schulte's Figure 4 explicitly includes a sign-extension
term from the previous iteration.  h1441 retained the two 76-bit redundant
feedback rows but omitted that term.  Its local modulo-103 arithmetic checks
therefore passed even though the assembled three-pass product was not exact.

This audit supplies the missing term.  If a 103-bit carry-save output S+C
wraps once modulo 2^103, independently shifting S and C right by 27 leaves a
spurious +2^76 in their redundant feedback sum.  The published sign-extension
row is exactly -2^76 modulo 2^103 when that wrap occurs.  The low-first carry
recurrence then composes the carry-zero/carry-one endpoints of the first two
passes, and the third-pass value receives the selected incoming carry.  A
full-product identity is asserted at every one of the eight modeled FMUL
sites for both the recovered 67-bit carrier and the paper's IP68 precision,
in both operand-port orientations.

Two isomorphic Booth representations are retained: a full-width two's-
complement row and Figure 4's compact ``{P,N,N}`` / ``{1,P}`` sign encoding.
Both are asserted to represent the exact partial-product sum before labels
are consulted.

Only source-defined state is scored: the wrap/sign-extension bit, the two
carry endpoints and their selected value, cumulative sticky, and ordinary
final-product GRS/rounding signals.  Every such wire is composed with the
incumbent R59 carry by a global Boolean gate.  Three-input gates are exhausted
only for fixed architectural pairings: p67/p68 format twins, written/swapped
port twins, and the terminal left/right product pair.  No operand identity,
threshold, interval, learned tree, or x87 execution is used.  This AMD design
establishes a physically plausible isomorphism, not Intel Skylake provenance.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import h1425_p5_public_mux_signals as h1425
import h1432_multiformat_split_adder_logic as h1432
import h1441_iterative_multiplier_feedback as h1441
from h1110_carry_gate_mine import GATE_NAMES


PAPER = "Tan_Lemonds_Schulte_IEEE_TC_2009"
PAPER_DOI = "10.1109/TC.2008.203"
H1441_REPORT = Path(
    "tmp/ledger33/current/h1441_iterative_multiplier_feedback.txt"
)
FMUL_STAGES = h1441.FMUL_STAGES
PROJECTIONS = h1441.PROJECTIONS
ROLES = h1441.ROLES
REPRESENTATIONS = ("full_twos", "compact_sign")
SUMMARY_SUFFIXES = (
    "pass1.tree_wrap",
    "pass1.carry0",
    "pass1.carry1",
    "pass1.selected_carry",
    "pass1.selected_sticky",
    "pass2.tree_wrap",
    "pass2.carry0",
    "pass2.carry1",
    "pass2.selected_carry",
    "pass2.selected_sticky",
    "prior.selected_carry1",
    "prior.selected_carry2",
    "prior.cumulative_sticky",
    "pass3.tree_wrap",
    "pass3.incoming_carry",
    "pass3.selected_sticky",
    "final.product_overflow",
    "final.retained_lsb",
    "final.round_bit",
    "final.sticky",
    "final.tie",
    "final.rne_increment",
    "final.rne_round_carry",
)


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


def corrected_tree(
    rows: list[int], feedback_sum: int, feedback_carry: int,
    sign_extension: int,
) -> tuple[int, int]:
    """Figure-3 tree with Figure-4's feedback sign-extension term."""
    combined_sum, combined_carry = h1441.csa(
        feedback_sum, feedback_carry, sign_extension
    )
    return h1441.source_tree(rows, combined_sum, combined_carry)


def compact_booth_rows(multiplicand: int, multiplier: int) -> list[int]:
    """Figure-4 compact sign encoding, including next-row hot ones.

    A radix-4 multiple needs 77 data bits for a 76-bit multiplicand.  The
    first row prefixes ``{P,N,N}``; subsequent rows prefix ``{1,P}``, where
    N is the partial-product sign and P its complement.  Their aggregate
    constant is 2^105, hence zero modulo the 103-bit product bus.
    """
    data_width = h1441.FEEDBACK_WIDTH + 1
    data_mask = (1 << data_width) - 1
    encoded = (multiplier & h1441.CHUNK_MASK) << 1
    rows = []
    pending_hot_one = 0
    for row_index, column in enumerate(range(0, 28, 2)):
        digit = h1441.DIGIT[(encoded >> column) & 7]
        negative = int(digit < 0)
        positive_sign = 1 - negative
        magnitude = abs(digit) * multiplicand
        data = ((~magnitude) & data_mask) if negative else magnitude
        row = (data << column) | pending_hot_one
        if row_index == 0:
            row |= (
                (positive_sign << (column + data_width + 2))
                | (negative << (column + data_width + 1))
                | (negative << (column + data_width))
            )
        else:
            row |= (
                (1 << (column + data_width + 1))
                | (positive_sign << (column + data_width))
            )
        pending_hot_one = (1 << column) if negative else 0
        rows.append(row & h1441.PRODUCT_MASK)
    if pending_hot_one:
        raise RuntimeError("top radix-4 digit unexpectedly negative")
    if (sum(rows) & h1441.PRODUCT_MASK) != multiplicand * multiplier:
        raise RuntimeError("compact Figure-4 Booth rows changed arithmetic")
    return rows


def booth_rows(
    multiplicand: int, multiplier: int, representation: str,
) -> list[int]:
    if representation == "full_twos":
        rows = h1441.booth_rows(multiplicand, multiplier)
        if (sum(rows) & h1441.PRODUCT_MASK) != multiplicand * multiplier:
            raise RuntimeError("full two's-complement Booth rows changed arithmetic")
        return rows
    if representation == "compact_sign":
        return compact_booth_rows(multiplicand, multiplier)
    raise ValueError(representation)


def rounding_signals(product: int, precision: int) -> dict[str, int]:
    width = product.bit_length()
    if width not in (2 * precision - 1, 2 * precision):
        raise RuntimeError(
            f"unexpected {width}-bit product at precision {precision}"
        )
    shift = width - precision
    retained = product >> shift
    discarded = product & ((1 << shift) - 1)
    round_bit = (discarded >> (shift - 1)) & 1
    sticky = int(bool(discarded & ((1 << (shift - 1)) - 1)))
    increment = round_bit & (sticky | (retained & 1))
    rounded = retained + increment
    return {
        "product_overflow": int(width == 2 * precision),
        "retained_lsb": retained & 1,
        "round_bit": round_bit,
        "sticky": sticky,
        "tie": round_bit & (1 - sticky),
        "inexact": int(bool(discarded)),
        "rne_increment": increment,
        "rne_round_carry": int(rounded.bit_length() > precision),
    }


def iteration_state(
    left: h1441.Value, right: h1441.Value, precision: int, role: str,
    representation: str,
) -> tuple[dict[str, int], tuple[object, ...]]:
    a = h1441.normalized_significand(left, precision)
    b = h1441.normalized_significand(right, precision)
    if role == "swapped":
        a, b = b, a
    elif role != "written":
        raise ValueError(role)

    multiplicand = a << (h1441.FEEDBACK_WIDTH - precision)
    low_width = precision - 2 * h1441.CHUNK_WIDTH
    chunks = (
        (b & ((1 << low_width) - 1))
        << (h1441.CHUNK_WIDTH - low_width),
        (b >> low_width) & h1441.CHUNK_MASK,
        (b >> (low_width + h1441.CHUNK_WIDTH)) & h1441.CHUNK_MASK,
    )

    values: dict[str, int] = {}
    pass_trace = []
    feedback_sum = 0
    feedback_carry = 0
    sign_extension = 0
    incoming_carry = 0
    cumulative_sticky = 0
    low_segments = []
    selected_carries = []

    for pass_index, chunk in enumerate(chunks, start=1):
        product_sum, product_carry = corrected_tree(
            booth_rows(multiplicand, chunk, representation),
            feedback_sum,
            feedback_carry,
            sign_extension,
        )
        raw_sum = product_sum + product_carry
        tree_wrap = raw_sum >> h1441.PRODUCT_WIDTH
        if tree_wrap not in (0, 1):
            raise RuntimeError("103-bit redundant tree wrapped more than once")
        resolved = raw_sum & h1441.PRODUCT_MASK
        expected = (
            multiplicand * chunk
            + feedback_sum
            + feedback_carry
            + sign_extension
        ) & h1441.PRODUCT_MASK
        if resolved != expected:
            raise RuntimeError("corrected Figure-3 tree failed modulo arithmetic")

        low_sum = product_sum & h1441.CHUNK_MASK
        low_carry = product_carry & h1441.CHUNK_MASK
        low_total = low_sum + low_carry
        carry0 = (low_total >> h1441.CHUNK_WIDTH) & 1
        carry1 = ((low_total + 1) >> h1441.CHUNK_WIDTH) & 1
        selected_total = low_total + incoming_carry
        selected_carry = (selected_total >> h1441.CHUNK_WIDTH) & 1
        if selected_carry != (carry1 if incoming_carry else carry0):
            raise RuntimeError("carry-select recurrence disagrees with addition")
        selected_low = selected_total & h1441.CHUNK_MASK
        selected_sticky = int(bool(selected_low))
        cumulative_sticky |= selected_sticky

        prefix = f"pass{pass_index}"
        local = {
            "incoming_carry": incoming_carry,
            "tree_wrap": tree_wrap,
            "sign_extension_active": int(bool(sign_extension)),
            "carry0": carry0,
            "carry1": carry1,
            "carry_propagate": carry0 ^ carry1,
            "selected_carry": selected_carry,
            "selected_sticky": selected_sticky,
            "cumulative_sticky": cumulative_sticky,
            "selected_lsb": selected_low & 1,
            "selected_low2_zero": int((selected_low & 3) == 0),
            "sum_boundary": (low_sum >> 26) & 1,
            "carry_boundary": (low_carry >> 26) & 1,
            "selected_boundary": (selected_low >> 26) & 1,
            "feedback_sum_lsb": (product_sum >> 27) & 1,
            "feedback_carry_lsb": (product_carry >> 27) & 1,
        }
        values.update({f"{prefix}.{name}": value
                       for name, value in local.items()})
        pass_trace.append((
            pass_index,
            tree_wrap,
            incoming_carry,
            carry0,
            carry1,
            selected_carry,
            selected_sticky,
            cumulative_sticky,
        ))

        if pass_index < 3:
            low_segments.append(selected_low)
            selected_carries.append(selected_carry)
            next_feedback_sum = (
                product_sum >> h1441.CHUNK_WIDTH
            ) & h1441.FEEDBACK_MASK
            next_feedback_carry = (
                product_carry >> h1441.CHUNK_WIDTH
            ) & h1441.FEEDBACK_MASK
            signed_feedback = (
                next_feedback_sum
                + next_feedback_carry
                - tree_wrap * (1 << h1441.FEEDBACK_WIDTH)
            )
            if signed_feedback != (
                (resolved >> h1441.CHUNK_WIDTH) - carry0
            ):
                raise RuntimeError("feedback sign-extension identity failed")
            feedback_sum = next_feedback_sum
            feedback_carry = next_feedback_carry
            sign_extension = (
                -tree_wrap * (1 << h1441.FEEDBACK_WIDTH)
            ) & h1441.PRODUCT_MASK
            incoming_carry = selected_carry
        else:
            # The incoming carry belongs at bit zero of the final high part;
            # a carry out of its low 27 bits is merely an internal resolution.
            final_high = resolved + incoming_carry

    if len(low_segments) != 2 or len(selected_carries) != 2:
        raise RuntimeError("missing iterative product segments")
    assembled = (
        low_segments[0]
        | (low_segments[1] << h1441.CHUNK_WIDTH)
        | (final_high << (2 * h1441.CHUNK_WIDTH))
    )
    padded_multiplier = b << (h1441.CHUNK_WIDTH - low_width)
    exact_product = multiplicand * padded_multiplier
    if assembled != exact_product:
        raise RuntimeError("corrected three-pass product is not exact")
    unpadded_product = a * b

    values.update({
        "prior.selected_carry1": selected_carries[0],
        "prior.selected_carry2": selected_carries[1],
        "prior.carry_changed": selected_carries[0] ^ selected_carries[1],
        "prior.cumulative_sticky": pass_trace[1][7],
        **{f"final.{name}": value
           for name, value in rounding_signals(
               unpadded_product, precision
           ).items()},
    })
    return values, (representation, precision, role, a, b, tuple(pass_trace))


def source_signals(
    row: dict[str, str],
) -> tuple[dict[str, int], tuple[tuple[object, ...], ...]]:
    values: dict[str, int] = {}
    traces = []
    for stage, operands in h1441.fmul_inputs(row).items():
        for representation in REPRESENTATIONS:
            for precision in PROJECTIONS:
                for role in ROLES:
                    local, trace = iteration_state(
                        *operands, precision, role, representation
                    )
                    stem = (
                        f"{stage}.{representation}.p{precision}.{role}"
                    )
                    values.update({f"{stem}.{name}": value
                                   for name, value in local.items()})
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
            raise RuntimeError("corrected iterative signal schema changed")
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


def gate_output(
    gate: int, current: np.ndarray, signal: np.ndarray,
) -> np.ndarray:
    return ((gate >> (2 * current + signal)) & 1).astype(np.uint8)


def structural_pairs(names: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    available = set(names)
    pairs = set()
    for stage in FMUL_STAGES:
        for representation in REPRESENTATIONS:
            for role in ROLES:
                for suffix in SUMMARY_SUFFIXES:
                    pair = (
                        f"{stage}.{representation}.p67.{role}.{suffix}",
                        f"{stage}.{representation}.p68.{role}.{suffix}",
                    )
                    if set(pair) <= available:
                        pairs.add(pair)
            for precision in PROJECTIONS:
                for suffix in SUMMARY_SUFFIXES:
                    pair = (
                        f"{stage}.{representation}.p{precision}.written."
                        f"{suffix}",
                        f"{stage}.{representation}.p{precision}.swapped."
                        f"{suffix}",
                    )
                    if set(pair) <= available:
                        pairs.add(pair)
        for precision in PROJECTIONS:
            for role in ROLES:
                for suffix in SUMMARY_SUFFIXES:
                    pair = (
                        f"{stage}.full_twos.p{precision}.{role}.{suffix}",
                        f"{stage}.compact_sign.p{precision}.{role}.{suffix}",
                    )
                    if set(pair) <= available:
                        pairs.add(pair)
    for representation in REPRESENTATIONS:
        for precision in PROJECTIONS:
            for role in ROLES:
                for suffix in SUMMARY_SUFFIXES:
                    pair = (
                        f"left.{representation}.p{precision}.{role}.{suffix}",
                        f"right.{representation}.p{precision}.{role}.{suffix}",
                    )
                    if set(pair) <= available:
                        pairs.add(pair)
    return tuple(sorted(pairs))


def score_pair_gates(
    names: tuple[str, ...], matrix: np.ndarray,
    pairs: tuple[tuple[str, str], ...], current: np.ndarray,
    required: np.ndarray, target: np.ndarray,
) -> list[tuple]:
    indices = {name: index for index, name in enumerate(names)}
    ranking = []
    for left_name, right_name in pairs:
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
                f"0x{gate:02x}",
                left_name,
                right_name,
            ))
    ranking.sort()
    return ranking


def collision_summary(
    prepared: list[PreparedRow], names: tuple[str, ...],
) -> tuple[list[tuple], int]:
    summary_indices = tuple(
        index for index, name in enumerate(names)
        if any(name.endswith("." + suffix) for suffix in SUMMARY_SUFFIXES)
    )
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        key = (
            item.row["branch"],
            item.current,
            bytes(item.signals[index] for index in summary_indices),
        )
        groups[key][item.required].append(item)
    mixed = []
    targets_in_mixed = 0
    for members in groups.values():
        if not members[0] or not members[1]:
            continue
        targets = [item for side in members for item in side if item.target]
        targets_in_mixed += len(targets)
        mixed.append((
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
    matrix = np.frombuffer(
        b"".join(item.signals for item in prepared), dtype=np.uint8
    ).reshape(len(prepared), len(names))
    current = np.asarray([item.current for item in prepared], dtype=np.uint8)
    required = np.asarray([item.required for item in prepared], dtype=np.uint8)
    target = np.asarray([item.target for item in prepared], dtype=bool)
    target_count = int(target.sum())

    gate_ranking = []
    for signal_index, name in enumerate(names):
        signal = matrix[:, signal_index]
        for gate in range(16):
            prediction = gate_output(gate, current, signal)
            score = h1432.score_prediction(prediction, required, target)
            changed = prediction != current
            gate_ranking.append((
                *score,
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

    pairs = structural_pairs(names)
    pair_ranking = score_pair_gates(
        names, matrix, pairs, current, required, target
    )
    pair_exact = [item for item in pair_ranking if item[0] == 0]
    pair_improvements = [
        item for item in pair_ranking
        if item[2] == 0 and item[1] < target_count
    ]
    mixed, collision_targets = collision_summary(prepared, names)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for label, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
            ("primary_paper", h1441.PAPER_PATH),
            ("superseded_h1441_script", Path(__file__).with_name(
                "h1441_iterative_multiplier_feedback.py")),
            ("superseded_h1441_report", H1441_REPORT),
        ):
            output.write(f"{label}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(f"primary_source\t{PAPER}\tdoi:{PAPER_DOI}\n")
        output.write("source_vendor\tAMD\n")
        output.write(
            "source_scope\tphysical_plausibility_not_Intel_or_Skylake_provenance\n"
        )
        output.write(
            "h1441_status\tsuperseded_missing_published_feedback_sign_extension\n"
        )
        output.write(
            "feedback_identity\t(S>>27)+(C>>27)-wrap*2^76="
            "((S+C)mod2^103>>27)-carry0\n"
        )
        output.write(
            "full_product_identity\tassembled_low27_low27_final_high="
            "multiplicand_times_padded_multiplier\n"
        )
        output.write("projection_precisions\t67,68\n")
        output.write("operand_roles\twritten,swapped\n")
        output.write("booth_representations\tfull_twos,compact_sign\n")
        output.write(
            "compact_sign_encoding\tFigure4_first_{P,N,N}_rest_{1,P}_"
            "aggregate_constant_2^105_zero_mod_2^103\n"
        )
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
        output.write(f"structural_pairs\t{len(pairs)}\n")
        output.write(f"structural_pair_gate_programs\t{len(pair_ranking)}\n")
        output.write(f"structural_pair_gate_exact\t{len(pair_exact)}\n")
        output.write(
            "structural_pair_gate_zero_control_improvements\t"
            f"{len(pair_improvements)}\n"
        )
        output.write(f"summary_history_mixed_groups\t{len(mixed)}\n")
        output.write(
            "targets_in_summary_history_mixed_groups\t"
            f"{collision_targets}\n"
        )

        output.write("\n[best global gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in gate_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-control global improvements]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in gate_improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best structural pair gates]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate_mask\tleft_signal\tright_signal\n"
        )
        for item in pair_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-control structural pair improvements]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate_mask\tleft_signal\tright_signal\n"
        )
        for item in pair_improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[summary-history mixed groups]\n")
        output.write(
            "required0\trequired1\ttargets\texample0\texample1\n"
        )
        for item in mixed[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[target corrected feedback traces]\n")
        output.write("mode\top\tcurrent\trequired\titeration_traces\n")
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
            output.write("corrected_iterative_feedback_selector\tCANDIDATE_ONLY\n")
        else:
            output.write("corrected_iterative_feedback_selector\tno_exact_program\n")


if __name__ == "__main__":
    main()
