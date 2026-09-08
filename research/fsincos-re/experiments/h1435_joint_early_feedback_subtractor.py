#!/usr/bin/env python3
"""Audit both early-feedback products in one terminal subtractor tree.

h1434 instantiated the arithmetic-preserving producer-round correction row
at each final Horner-FADD-to-FMUL edge separately.  This audit tests the one
remaining schedule-local composition: preserve both corrected multiplier
sum/carry pairs, align them at a common exact scale, add the documented
payload, negate the right pair, and reduce the collection through one fixed
balanced 3:2 tree before observing the terminal R59 carry recurrence.

All 24 correction-row placements are crossed between the left and right
terminal multipliers, for 576 fixed representations.  A representation must
fit all eleven target legs before it is allowed to see the complete control
and prior one-shot Q/QX adversarial wall.  Every evaluated joint state is
also required to reconstruct the exact aligned subtraction modulo the fixed
224-bit carrier width.

The early-feedback technique is documented by IBM in US20060179096A1.  It is
physical-plausibility evidence only, not evidence that Skylake contains that
embodiment.  Likewise, retaining both product carriers into the subtractor
is a bounded alternate schedule, not established Skylake provenance.  This
script contains no operand identities, thresholds, learned trees, branch
programs, or x87 executions.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import h1400_p5_representation_audit as h1400
import h1434_early_feedback_round_correction as h1434
from h1128_fused_terminal_csa_mine import (
    MASK, WIDTH, negate_rows, reduce_balanced, shift_wire,
)


PATENT = "US20060179096A1"
PATENT_URL = "https://patents.google.com/patent/US20060179096A1/en"
SLOTS = tuple(range(24))


@dataclass(frozen=True)
class Representation:
    left_slot: int
    right_slot: int

    @property
    def name(self) -> str:
        return (
            f"joint_early_feedback.L{self.left_slot:02d}."
            f"R{self.right_slot:02d}"
        )


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def product_state(
    row: dict[str, str], source: str, slot: int
) -> tuple[int, int, int]:
    state = h1434.representation_state(
        h1434.Representation(source, slot), row
    )
    sum_vector, carry_vector, _, exact = state
    sum_vector &= h1400.PRODUCT_MASK
    carry_vector &= h1400.PRODUCT_MASK
    if ((sum_vector + carry_vector) & h1400.PRODUCT_MASK) != exact:
        raise RuntimeError("corrected product pair failed exact gate")
    return sum_vector, carry_vector, exact


def joint_state_from_products(
    representation: Representation,
    row: dict[str, str],
    left: tuple[int, int, int],
    right: tuple[int, int, int],
) -> tuple[int, int, int, int]:
    left_base = int(row["tc_mul_exp"]) + int(row["tc_lf_exp"])
    right_base = int(row["tc_f4_exp"]) + int(row["tc_rf_exp"])
    left_e2 = int(row["tc_left_exp"])
    payload = int(row["payload"])
    payload_e2 = left_e2 - 8
    cut_exponent = int(row["rscale"]) + int(row["k"])
    fine = min(
        left_base,
        right_base,
        payload_e2 if payload else left_base,
    )

    left_rows = [
        shift_wire(value, left_base - fine) for value in left[:2]
    ]
    right_rows = [
        shift_wire(value, right_base - fine) for value in right[:2]
    ]
    rows = list(left_rows)
    if payload:
        rows.append((payload << (payload_e2 - fine)) & MASK)
    rows.extend(negate_rows(right_rows))
    sum_vector, carry_vector, _ = reduce_balanced(rows)

    exact = (left[2] << (left_base - fine)) & MASK
    if payload:
        exact = (exact + (payload << (payload_e2 - fine))) & MASK
    exact = (exact - (right[2] << (right_base - fine))) & MASK
    got = (sum_vector + carry_vector) & MASK
    if got != exact:
        raise RuntimeError(
            f"joint arithmetic gate failed for {representation.name} "
            f"{row['op']}: {got:x} != {exact:x}"
        )
    cut = cut_exponent - fine
    if not 0 < cut < WIDTH:
        raise RuntimeError(f"invalid joint cut {cut} for {row['op']}")
    return sum_vector, carry_vector, cut, exact


def joint_state(
    representation: Representation, row: dict[str, str]
) -> tuple[int, int, int, int]:
    left = product_state(row, "L", representation.left_slot)
    right = product_state(row, "R", representation.right_slot)
    return joint_state_from_products(representation, row, left, right)


def target_search(
    representation: Representation,
    states: list[tuple[int, int, int, int]],
    targets: list[h1400.AuditRow],
) -> tuple[int, list[h1400.Candidate]]:
    """Return the minimum target error and every target-exact program."""
    count = len(targets)
    full_mask = (1 << count) - 1
    truth_mask = sum(row.truth << index for index, row in enumerate(targets))
    current_mask = sum(
        row.current << index for index, row in enumerate(targets)
    )
    prepared = []
    for state in states:
        sum_vector, carry_vector, cut, _ = state
        by_attachment = {}
        for attachment in h1400.ATTACHMENTS:
            end = max(0, cut + attachment)
            by_attachment[attachment] = h1400.carry_relations(
                sum_vector, carry_vector, end
            )
        prepared.append((cut, by_attachment))

    minimum = count + 1
    exact_candidates = []
    for attachment in h1400.ATTACHMENTS:
        for width in h1400.WIDTHS:
            for alignment in h1400.ALIGNMENTS:
                for seed in (0, 1):
                    block_mask = 0
                    exact_mask = 0
                    for index, (cut, relations) in enumerate(prepared):
                        end = max(0, cut + attachment)
                        zero, one = relations[attachment]
                        start = h1400.recurrence_start(
                            end, width, alignment
                        )
                        block = (zero if seed == 0 else one)[start]
                        block_mask |= block << index
                        exact_mask |= zero[0] << index
                    reset_error = block_mask ^ exact_mask
                    outputs = {
                        "block": block_mask,
                        "not_block": full_mask ^ block_mask,
                        "current_xor_reset_error": (
                            current_mask ^ reset_error
                        ),
                        "current_drop_on_reset_error": (
                            current_mask & (full_mask ^ reset_error)
                        ),
                        "current_set_on_reset_error": (
                            current_mask | reset_error
                        ),
                        "current_xor_block": current_mask ^ block_mask,
                        "current_and_block": current_mask & block_mask,
                        "current_or_block": current_mask | block_mask,
                    }
                    for transform in h1400.TRANSFORMS:
                        errors = (outputs[transform] ^ truth_mask).bit_count()
                        if errors < minimum:
                            minimum = errors
                        if errors == 0:
                            exact_candidates.append(h1400.Candidate(
                                representation.name,
                                "joint_early_feedback_subtractor",
                                "LR",
                                attachment,
                                width,
                                alignment,
                                seed,
                                transform,
                                0,
                                0,
                                0,
                                0,
                            ))
    return minimum, exact_candidates


def deduplicate(
    candidates: list[h1400.Candidate],
    by_name: dict[str, Representation],
    target_states: dict[str, list[tuple[int, int, int, int]]],
) -> list[h1400.Candidate]:
    unique = {}
    for item in candidates:
        cuts = sorted({state[2] for state in target_states[item.representation]})
        boundary_signature = tuple(
            (
                max(0, cut + item.attachment),
                h1400.recurrence_start(
                    max(0, cut + item.attachment),
                    item.width,
                    item.alignment,
                ),
            )
            for cut in cuts
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
    return list(unique.values())


def score_wall(
    candidates: list[h1400.Candidate],
    by_name: dict[str, Representation],
    rows: list[h1400.AuditRow],
) -> list[tuple]:
    grouped = defaultdict(list)
    for item in candidates:
        grouped[item.representation].append(item)
    needed_left = sorted({by_name[name].left_slot for name in grouped})
    needed_right = sorted({by_name[name].right_slot for name in grouped})
    errors = {
        name: [Counter() for _ in group] for name, group in grouped.items()
    }

    for audit_row in rows:
        if audit_row.truth is None or audit_row.role == "target":
            continue
        row = audit_row.fields
        left = {
            slot: product_state(row, "L", slot) for slot in needed_left
        }
        right = {
            slot: product_state(row, "R", slot) for slot in needed_right
        }
        for name, group in grouped.items():
            representation = by_name[name]
            sum_vector, carry_vector, cut, _ = joint_state_from_products(
                representation,
                row,
                left[representation.left_slot],
                right[representation.right_slot],
            )
            attachments = sorted({item.attachment for item in group})
            relations = {
                attachment: h1400.carry_relations(
                    sum_vector,
                    carry_vector,
                    max(0, cut + attachment),
                )
                for attachment in attachments
            }
            for item, counter in zip(group, errors[name]):
                end = max(0, cut + item.attachment)
                zero, one = relations[item.attachment]
                start = h1400.recurrence_start(
                    end, item.width, item.alignment
                )
                block = (zero if item.seed == 0 else one)[start]
                output = h1400.transform_value(
                    item.transform, audit_row.current, block, zero[0]
                )
                if output != audit_row.truth:
                    counter[audit_row.role] += 1
                    counter[audit_row.branch] += 1

    scores = []
    for name, group in grouped.items():
        representation = by_name[name]
        for item, counter in zip(group, errors[name]):
            scores.append((
                counter["control"] + counter["adversarial"],
                0,
                counter["control"],
                counter["adversarial"],
                0,
                0,
                0,
                representation.name,
                item.source,
                item.attachment,
                item.width,
                item.alignment,
                item.seed,
                item.transform,
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
    parser.add_argument("h1434_report", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default="3ffc d0d000000cc0b3f8")
    parser.add_argument(
        "--adversarial-score", type=Path, action="append", default=[]
    )
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    antecedent = args.h1434_report.read_text()
    if "representations\t48\n" not in antecedent \
            or "arithmetic_exact\t48\n" not in antecedent:
        raise RuntimeError("h1434 arithmetic-exact antecedent is missing")

    rows = h1400.feature_rows(
        args.features, args.positive_allmode, args.control_allmode
    )
    h1434.append_d0d0(rows, args.model, args.misses, args.extra_op)
    rows.extend(h1400.adversarial_rows(args.model, args.adversarial_score))
    targets = [row for row in rows if row.role == "target"]
    if len(targets) != 11:
        raise RuntimeError(f"expected eleven target legs, got {len(targets)}")

    representations = tuple(
        Representation(left, right) for left in SLOTS for right in SLOTS
    )
    by_name = {item.name: item for item in representations}
    target_states = {}
    target_exact = []
    minimum = len(targets) + 1
    exact_representations = 0
    for index, representation in enumerate(representations, 1):
        states = [joint_state(representation, row.fields) for row in targets]
        target_states[representation.name] = states
        local_minimum, exact = target_search(
            representation, states, targets
        )
        minimum = min(minimum, local_minimum)
        if exact:
            exact_representations += 1
            target_exact.extend(exact)
        if index % 24 == 0:
            print(
                f"left_slot={representation.left_slot:02d} "
                f"best_target_miss_so_far={minimum} "
                f"target_exact_representations={exact_representations}",
                flush=True,
            )

    shortlist = deduplicate(target_exact, by_name, target_states)
    scores = score_wall(shortlist, by_name, rows) if shortlist else []
    exact_global = [score for score in scores if score[0] == 0]
    role_counts = Counter(row.role for row in rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("software_model", args.model),
            ("misses", args.misses),
            ("h1434_report", args.h1434_report),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        for index, path in enumerate(args.adversarial_score):
            output.write(
                f"adversarial_score_{index}_sha256\t{digest(path)}\n"
            )
        output.write(f"source_patent\t{PATENT}\n")
        output.write(f"source_url\t{PATENT_URL}\n")
        output.write(
            "source_boundary\tIBM_FMA_early_feedback_and_joint_"
            "subtractor_are_physical_plausibility_not_Skylake_provenance\n"
        )
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write(
            "representation_policy\tboth_corrected_terminal_product_"
            "pairs_plus_payload_in_one_fixed_balanced_CSA\n"
        )
        output.write(
            "arithmetic_gate\th1434_all_products_plus_every_evaluated_"
            "joint_state\n"
        )
        for role in ("target", "control", "neutral", "adversarial"):
            output.write(f"{role}_rows\t{role_counts[role]}\n")
        output.write(f"representations\t{len(representations)}\n")
        output.write(f"best_target_miss\t{minimum}\n")
        output.write(
            f"target_exact_representations\t{exact_representations}\n"
        )
        output.write(f"target_exact_candidates\t{len(target_exact)}\n")
        output.write(
            f"scored_recurrence_equivalence_classes\t{len(shortlist)}\n"
        )
        output.write(f"global_exact_candidates\t{len(exact_global)}\n")

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
            "A target-only program is rejected.  This topology is a "
            "selector mechanism only if one fixed recurrence has zero "
            "target, control, and prior-adversarial errors.\n"
        )

    print(
        f"wrote {args.report}: representations={len(representations)} "
        f"best_target_miss={minimum} "
        f"target_exact_representations={exact_representations} "
        f"global_exact={len(exact_global)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
