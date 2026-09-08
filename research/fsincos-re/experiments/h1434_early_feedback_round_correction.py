#!/usr/bin/env python3
"""Audit an early-FADD-feedback correction row in the terminal FMULs.

The recovered cosine schedule places each final Horner FADD immediately
before a dependent FMUL.  A known high-performance implementation technique
for such dependencies forwards the normalized but unrounded FADD result and,
once the producer rounder resolves, injects ``other_operand * one_ulp`` as a
correction row in the consumer multiplier tree.  The correction leaves the
numerical product identical to multiplication by the rounded operand, but it
can change the multiplier's redundant sum/carry representation.

This audit instantiates that topology at the two final Horner-FADD-to-FMUL
edges.  The 64-bit chopped producer value is Booth-recoded normally; when the
already-fixed RN64 producer rounds upward, the 67-bit power operand is placed
in the P5 tree's otherwise-zero 24th input.  All 24 positions of that
correction input are enumerated by swapping it with the zero input before the
fixed four-level 4:2 tree.  Every representation is required to sum to the
same exact integer product as the already-reconstructed rounded operand
before any cached hardware label is consulted.

For each arithmetic-exact representation, the same bounded fixed-width carry
recurrences used by h1400 are tested against all eleven current R59 target
legs, the complete constraining control wall, and the prior one-shot Q/QX
adversaries.  There are no operand identities, numeric thresholds, learned
trees, branch-local programs, or x87 executions.

The correction-row technique is documented in US20060179096A1 for a fused
multiply-add pipeline and is not evidence that Skylake implements that IBM
embodiment.  It is used only as a source-bounded physically plausible
representation that was not instantiated by the earlier rounded-operand
tree census.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import h1400_p5_representation_audit as h1400
import h1424_subtract_final_add_interstage_carrier as h1424
from h1110_carry_gate_mine import extract_carry_state
from h1184_upstream_halfway_audit import quantize, row_value, schedule


PATENT = "US20060179096A1"
PATENT_URL = "https://patents.google.com/patent/US20060179096A1/en"
SOURCES = ("L", "R")
SLOTS = tuple(range(24))
MASK = (1 << h1400.TREE_BITS) - 1


@dataclass(frozen=True)
class Representation:
    source: str
    slot: int

    @property
    def name(self) -> str:
        return f"{self.source}.early_round_correction.slot{self.slot:02d}"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def producer_components(
    row: dict[str, str], source: str
) -> tuple[int, int, int, int]:
    """Return power, chopped factor, producer increment, exact product."""
    operations = schedule(row)
    if source == "L":
        power = row_value(row, "mul")
        operation = operations["negative.add2"]
        expected = row_value(row, "lf")
    elif source == "R":
        power = row_value(row, "f4")
        operation = operations["positive.add2"]
        expected = row_value(row, "rf")
    else:
        raise ValueError(source)

    chopped = quantize(operation, 64, False)
    rounded = quantize(operation, 64, True)
    if rounded != expected:
        raise RuntimeError(
            f"producer reconstruction mismatch for {source} {row['op']}"
        )
    if chopped.sign != rounded.sign or chopped.exponent != rounded.exponent:
        raise RuntimeError(
            f"producer overflow is outside this correction form: "
            f"{source} {row['op']}"
        )
    increment = rounded.significand - chopped.significand
    if increment not in (0, 1):
        raise RuntimeError(
            f"non-unit producer correction for {source} {row['op']}: "
            f"{increment}"
        )
    if power.significand.bit_length() != 67:
        raise RuntimeError(
            f"power is not a normalized X67 operand: {source} {row['op']}"
        )
    if chopped.significand.bit_length() != 64:
        raise RuntimeError(
            f"factor is not a normalized Y64 operand: {source} {row['op']}"
        )
    exact = power.significand * rounded.significand
    return power.significand, chopped.significand, increment, exact


def representation_state(
    representation: Representation, row: dict[str, str]
) -> tuple[int, int, int, int]:
    power, factor, increment, exact = producer_components(
        row, representation.source
    )
    inputs, zero_index = h1400.physical_inputs(
        power, factor, "next_row"
    )
    if zero_index is None or inputs[zero_index] != 0:
        raise RuntimeError("early-feedback tree lost its spare zero input")

    # The correction has a fixed physical input.  Swap the row that formerly
    # occupied that input into the spare position so no arithmetic term is
    # dropped.  When increment is clear, the selected correction input is
    # zero, preserving the same fixed routing rather than changing topology.
    slot = representation.slot
    inputs[zero_index] = inputs[slot]
    inputs[slot] = power if increment else 0
    sum_vector, carry_vector = h1400.reduce_tree(
        inputs, h1400.TreeConfig()
    )
    # The Booth encoding deliberately carries a fixed sign-correction bias
    # above the 131-bit X67*Y64 product.  As in h1400's exact gate, compare
    # the represented product field rather than that implementation-only
    # high bit.
    got = (sum_vector + carry_vector) & h1400.PRODUCT_MASK
    if got != exact:
        raise RuntimeError(
            f"arithmetic gate failed for {representation.name} {row['op']}: "
            f"{got:x} != {exact:x}"
        )
    return sum_vector, carry_vector, exact.bit_length() - 67, exact


def representations() -> tuple[Representation, ...]:
    return tuple(
        Representation(source, slot)
        for source in SOURCES
        for slot in SLOTS
    )


def append_d0d0(
    rows: list[h1400.AuditRow], model: Path, misses: Path, operand: str
) -> None:
    fields = [row.fields for row in rows]
    h1424.append_extra_rows(fields, model, misses, operand)
    for row in fields[-2:]:
        state = extract_carry_state(row, set(range(-8, 9)))
        rows.append(h1400.AuditRow(
            row, "target", 1, state[2], row["branch"]
        ))


def score_shortlist(
    candidates: list[h1400.Candidate],
    by_name: dict[str, Representation],
    rows: list[h1400.AuditRow],
) -> list[tuple]:
    grouped: dict[str, list[h1400.Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.representation].append(candidate)

    scores = []
    for name, group in grouped.items():
        representation = by_name[name]
        errors_by_candidate = [Counter() for _ in group]
        attachments = sorted({item.attachment for item in group})
        for row in rows:
            if row.truth is None or row.role == "target":
                continue
            state = representation_state(representation, row.fields)
            sum_vector, carry_vector, cut, _ = state
            relations = {
                attachment: h1400.carry_relations(
                    sum_vector, carry_vector, max(0, cut + attachment)
                )
                for attachment in attachments
            }
            for candidate, errors in zip(group, errors_by_candidate):
                end = max(0, cut + candidate.attachment)
                zero, one = relations[candidate.attachment]
                start = h1400.recurrence_start(
                    end, candidate.width, candidate.alignment
                )
                block = (zero if candidate.seed == 0 else one)[start]
                exact_carry = zero[0]
                output = h1400.transform_value(
                    candidate.transform, row.current, block, exact_carry
                )
                if output != row.truth:
                    errors[row.role] += 1
                    errors[row.branch] += 1
        for candidate, errors in zip(group, errors_by_candidate):
            scores.append((
                candidate.target_miss + errors["control"]
                + errors["adversarial"],
                candidate.target_miss,
                errors["control"],
                errors["adversarial"],
                candidate.band_miss,
                candidate.tie_miss,
                candidate.corner_miss,
                candidate.representation,
                candidate.source,
                candidate.attachment,
                candidate.width,
                candidate.alignment,
                candidate.seed,
                candidate.transform,
            ))
    scores.sort()
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--extra-op", default="3ffc d0d000000cc0b3f8"
    )
    parser.add_argument(
        "--adversarial-score", type=Path, action="append", default=[]
    )
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = h1400.feature_rows(
        args.features, args.positive_allmode, args.control_allmode
    )
    append_d0d0(rows, args.model, args.misses, args.extra_op)
    rows.extend(h1400.adversarial_rows(args.model, args.adversarial_score))
    targets = [row for row in rows if row.role == "target"]
    if len(targets) != 11:
        raise RuntimeError(f"expected eleven target legs, got {len(targets)}")

    reps = representations()
    by_name = {item.name: item for item in reps}
    best_candidates = []
    increment_counts = Counter()
    cut_sets = defaultdict(set)
    for representation in reps:
        target_states = []
        for row in rows:
            state = representation_state(representation, row.fields)
            cut_sets[representation.source].add(state[2])
            if row.role == "target":
                target_states.append(state)
        mined = h1400.mine_targets(
            h1400.Representation(
                representation.name,
                "early_feedback_round_correction",
                representation.source,
                "tree",
            ),
            target_states,
            targets,
        )
        best_candidates.extend(mined)
        print(
            f"representation {representation.name} "
            f"best_target_miss={mined[0].target_miss} aliases={len(mined)}",
            flush=True,
        )

    # Producer increment frequencies are independent of correction slot.
    for row in rows:
        for source in SOURCES:
            _, _, increment, _ = producer_components(row.fields, source)
            increment_counts[(row.role, source, increment)] += 1

    global_minimum = min(item.target_miss for item in best_candidates)
    target_exact = [
        item for item in best_candidates if item.target_miss == 0
    ]
    if target_exact:
        shortlist = target_exact
    else:
        shortlist = sorted(best_candidates, key=lambda item: (
            item.target_miss,
            max(item.band_miss, item.tie_miss, item.corner_miss),
            item.representation,
            item.attachment,
            item.width,
            item.alignment,
            item.seed,
            item.transform,
        ))[:128]

    unique = {}
    for item in shortlist:
        boundary_signature = tuple(
            (
                max(0, cut + item.attachment),
                h1400.recurrence_start(
                    max(0, cut + item.attachment),
                    item.width,
                    item.alignment,
                ),
            )
            for cut in sorted(cut_sets[item.source])
        )
        key = (
            item.representation,
            item.attachment,
            item.seed,
            item.transform,
            boundary_signature,
        )
        prior = unique.get(key)
        if prior is None or (item.width, item.alignment) < (
            prior.width, prior.alignment
        ):
            unique[key] = item
    shortlist = list(unique.values())
    scores = score_shortlist(shortlist, by_name, rows)
    exact_global = [item for item in scores if item[0] == 0]

    role_counts = Counter(row.role for row in rows)
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
        for index, path in enumerate(args.adversarial_score):
            output.write(
                f"adversarial_score_{index}_sha256\t{digest(path)}\n"
            )
        output.write(f"source_patent\t{PATENT}\n")
        output.write(f"source_url\t{PATENT_URL}\n")
        output.write(
            "source_boundary\tIBM_FMA_early_feedback_is_physical_"
            "plausibility_not_Skylake_provenance\n"
        )
        output.write(
            "hardware_policy\tcached_labels_only_no_x87_execution\n"
        )
        output.write(
            "representation_policy\tRN64_producer_round_increment_as_"
            "terminal_FMUL_correction_row\n"
        )
        output.write(
            "arithmetic_gate\tevery_cached_row_before_label_mining\n"
        )
        for role in ("target", "control", "neutral", "adversarial"):
            output.write(f"{role}_rows\t{role_counts[role]}\n")
        output.write(f"representations\t{len(reps)}\n")
        output.write(f"arithmetic_exact\t{len(reps)}\n")
        output.write(f"best_target_miss\t{global_minimum}\n")
        output.write(f"target_exact_candidates\t{len(target_exact)}\n")
        output.write(
            f"scored_recurrence_equivalence_classes\t{len(shortlist)}\n"
        )
        output.write(f"global_exact_candidates\t{len(exact_global)}\n")

        output.write("\n[producer round increments]\n")
        output.write("role\tsource\tincrement\trows\n")
        for key, count in sorted(increment_counts.items()):
            output.write("\t".join(map(str, (*key, count))) + "\n")

        output.write("\n[best fixed-width recurrence ranking]\n")
        output.write(
            "total_miss\ttarget_miss\tcontrol_miss\tadversarial_miss\t"
            "band_miss\ttie_miss\tcorner_miss\trepresentation\tsource\t"
            "attachment\twidth\talignment\tseed\ttransform\n"
        )
        for score in scores[:256]:
            output.write("\t".join(map(str, score)) + "\n")

        output.write("\n[exact transferable candidates]\n")
        if exact_global:
            for score in exact_global:
                output.write("\t".join(map(str, score)) + "\n")
        else:
            output.write("none\n")

        output.write("\n[claim boundary]\n")
        output.write(
            "An arithmetic-exact correction-row representation changes "
            "only redundant product state.  It is a selector mechanism "
            "only if one fixed recurrence also has zero target, control, "
            "and prior-adversarial errors; target-only aliases are rejected.\n"
        )

    print(
        f"wrote {args.report}: representations={len(reps)} "
        f"best_target_miss={global_minimum} "
        f"target_exact={len(target_exact)} global_exact={len(exact_global)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
