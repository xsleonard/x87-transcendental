#!/usr/bin/env python3
"""Audit a fixed asymmetric pre-rounded-result bypass at the terminal FMULs.

Intel US5996065A describes a P6-era floating-point bypass in which an
execution-stage pre-rounded result can feed a dependent operation two clocks
later, while a separately latched path supplies the delayed value when that
bypass timing is unavailable.  The recovered cosine schedule has two final
Horner FADD-to-FMUL dependencies.  h1400 applied one producer materialization
uniformly to both dependencies, so it did not instantiate the two fixed mixed
possibilities suggested by that timing mechanism:

    left retains the pre-rounded FAMUBUS value, right consumes RN64; or
    left consumes RN64, right retains the pre-rounded FAMUBUS value.

This audit tests exactly those two assignments across h1400's already-bounded
input encoding, FADD mode, normalization, FMUL port route, Y materialization,
and product materialization choices.  The arm assignment is fixed globally;
there are no operand predicates, learned thresholds, branch-local programs,
or x87 executions.  The patent establishes a P6-era Intel timing mechanism,
not the issue clocks of the modeled transcendental operations and not
Skylake provenance.  A passing candidate would therefore still require an
independent validation bank before promotion.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import h1400_p5_representation_audit as h1400rep
import h1400_terminal_famubus_producer as h1400bus
import h1424_subtract_final_add_interstage_carrier as h1424
import h206_p5_fadd_complete as h206
from h1110_carry_gate_mine import extract_carry_state
from h1184_upstream_halfway_audit import ExactOperation, row_value, schedule


PATENT = "US5996065A"
PATENT_URL = "https://patents.google.com/patent/US5996065A/en"
ARM_SCHEDULES = ("Lretain_Rrn64", "Lrn64_Rretain")


@dataclass(frozen=True)
class Program:
    input_encoding: str
    add_mode: str
    normalize: bool
    arm_schedule: str
    route: str
    y_mode: str
    product_mode: str

    @property
    def actions(self) -> tuple[str, str]:
        if self.arm_schedule == "Lretain_Rrn64":
            return "retain", "rn64"
        if self.arm_schedule == "Lrn64_Rretain":
            return "rn64", "retain"
        raise ValueError(self.arm_schedule)

    @property
    def name(self) -> str:
        return "/".join((
            self.input_encoding,
            self.add_mode,
            "norm" if self.normalize else "raw",
            self.arm_schedule,
            self.route,
            self.y_mode,
            self.product_mode,
        ))


@dataclass
class RowCase:
    fields: dict[str, str]
    operations: dict[str, ExactOperation]
    role: str
    allowed_delta: frozenset[int]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def programs() -> tuple[Program, ...]:
    return tuple(
        Program(
            input_encoding,
            add_mode,
            normalize,
            arm_schedule,
            route,
            y_mode,
            product_mode,
        )
        for input_encoding in h1400bus.INPUT_ENCODINGS
        for add_mode in h206.MODES
        for normalize in (False, True)
        for arm_schedule in ARM_SCHEDULES
        for route in h1400bus.ROUTES
        for y_mode in h1400bus.Y_MODES
        for product_mode in h1400bus.PRODUCT_MODES
    )


def candidate_delta(case: RowCase, program: Program) -> int | None:
    left_action, right_action = program.actions
    negative = h1400bus.factor_bus_cached(
        case.operations["negative.mul2"],
        1,
        program.input_encoding,
        program.add_mode,
        program.normalize,
        left_action,
    )
    positive = h1400bus.factor_bus_cached(
        case.operations["positive.mul2"],
        2,
        program.input_encoding,
        program.add_mode,
        program.normalize,
        right_action,
    )
    left = h1400bus.terminal_product_cached(
        row_value(case.fields, "mul"),
        negative,
        program.route,
        program.y_mode,
        program.product_mode,
    )
    right = h1400bus.terminal_product_cached(
        row_value(case.fields, "f4"),
        positive,
        program.route,
        program.y_mode,
        program.product_mode,
    )
    return h1400bus.retained_delta(case.fields, left, right)


def load_cases(
    features: Path,
    positive_allmode: Path,
    control_allmode: Path,
    model: Path,
    misses: Path,
    extra_op: str,
    adversarial_scores: list[Path],
) -> list[RowCase]:
    positive = h1400rep.allmode_allowed(positive_allmode)
    controls = h1400rep.allmode_allowed(control_allmode)
    audit_rows = h1400rep.feature_rows(
        features, positive_allmode, control_allmode
    )
    cases = []
    for row in audit_rows:
        bank = positive if row.fields["label"] == "POS" else controls
        cases.append(RowCase(
            row.fields,
            schedule(row.fields),
            row.role,
            frozenset(bank[row.fields["op"]]),
        ))

    extra_fields = [row.fields for row in audit_rows]
    h1424.append_extra_rows(extra_fields, model, misses, extra_op)
    for row in extra_fields[-2:]:
        borrow, _, _, _ = extract_carry_state(row, set(range(-8, 9)))
        # The cached RD/RZ labels require final R59 carry one, hence
        # delta = carry + borrow - 1 = borrow in h1110's convention.
        cases.append(RowCase(
            row,
            schedule(row),
            "target",
            frozenset((borrow,)),
        ))

    for row in h1400rep.adversarial_rows(model, adversarial_scores):
        _, current_delta, _, _ = extract_carry_state(
            row.fields, set(range(-8, 9))
        )
        cases.append(RowCase(
            row.fields,
            schedule(row.fields),
            "adversarial",
            frozenset((current_delta,)),
        ))
    return cases


def score(program: Program, cases: list[RowCase]) -> tuple[Counter, list]:
    counts = Counter()
    diagnostics = []
    for case in cases:
        try:
            delta = candidate_delta(case, program)
        except ValueError:
            delta = None
        wrong = delta not in case.allowed_delta
        counts["errors"] += wrong
        counts[f"{case.role}_errors"] += wrong
        counts["invalid"] += delta is None
        counts[f"delta.{delta}"] += 1
        if case.role == "target":
            diagnostics.append((
                case.fields["mode"],
                case.fields["op"],
                ",".join(map(str, sorted(case.allowed_delta))),
                delta,
                int(not wrong),
            ))
    return counts, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default="3ffc d0d000000cc0b3f8")
    parser.add_argument(
        "--adversarial-score", type=Path, action="append", default=[]
    )
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    cases = load_cases(
        args.features,
        args.positive_allmode,
        args.control_allmode,
        args.model,
        args.misses,
        args.extra_op,
        args.adversarial_score,
    )
    targets = [case for case in cases if case.role == "target"]
    if len(targets) != 11:
        raise RuntimeError(f"expected eleven target legs, got {len(targets)}")

    candidates = programs()
    target_ranking = []
    target_diagnostics = {}
    target_exact = []
    for index, program in enumerate(candidates, 1):
        counts, diagnostics = score(program, targets)
        item = (
            counts["errors"],
            counts["invalid"],
            counts["delta.-2"],
            counts["delta.-1"],
            counts["delta.0"],
            counts["delta.1"],
            counts["delta.2"],
            program.name,
        )
        target_ranking.append(item)
        target_diagnostics[program.name] = diagnostics
        if not counts["errors"]:
            target_exact.append(program)
        if index % 256 == 0:
            print(f"target programs {index}/{len(candidates)}", flush=True)
    target_ranking.sort()

    full_ranking = []
    for index, program in enumerate(target_exact, 1):
        counts, _ = score(program, cases)
        full_ranking.append((
            counts["errors"],
            counts["target_errors"],
            counts["control_errors"],
            counts["neutral_errors"],
            counts["adversarial_errors"],
            counts["invalid"],
            counts["delta.-2"],
            counts["delta.-1"],
            counts["delta.0"],
            counts["delta.1"],
            counts["delta.2"],
            program.name,
        ))
        if index % 64 == 0:
            print(
                f"full programs {index}/{len(target_exact)}", flush=True
            )
    full_ranking.sort()

    role_counts = Counter(case.role for case in cases)
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
            "source_boundary\tP6-era_Intel_bypass_timing_is_documented_"
            "but_transcendental_arm_issue_clocks_and_Skylake_provenance_"
            "are_not_proven\n"
        )
        output.write(
            "coverage_relation\th1400_used_one_uniform_producer_action_"
            "and_did_not_test_these_two_mixed_arm_assignments\n"
        )
        output.write(
            "hardware_policy\tcached_labels_only_no_x87_execution\n"
        )
        output.write(
            "candidate_policy\ttwo_fixed_global_pre-rounded_vs_RN64_"
            "arm_assignments_no_data_predicate\n"
        )
        for role in ("target", "control", "neutral", "adversarial"):
            output.write(f"{role}_rows\t{role_counts[role]}\n")
        output.write(f"programs\t{len(candidates)}\n")
        output.write(f"best_target_miss\t{target_ranking[0][0]}\n")
        output.write(f"target_exact_programs\t{len(target_exact)}\n")
        output.write(
            f"global_exact_programs\t"
            f"{sum(item[0] == 0 for item in full_ranking)}\n"
        )

        output.write("\n[target ranking]\n")
        output.write(
            "target_miss\tinvalid\tdelta_minus2\tdelta_minus1\t"
            "delta_zero\tdelta_plus1\tdelta_plus2\tprogram\n"
        )
        for item in target_ranking[:256]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[best target diagnostics]\n")
        output.write("mode\top\tallowed_delta\tpredicted_delta\tmatch\n")
        for item in target_diagnostics[target_ranking[0][-1]]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[full-wall ranking of target-exact programs]\n")
        output.write(
            "total_miss\ttarget_miss\tcontrol_miss\tneutral_miss\t"
            "adversarial_miss\tinvalid\tdelta_minus2\tdelta_minus1\t"
            "delta_zero\tdelta_plus1\tdelta_plus2\tprogram\n"
        )
        if full_ranking:
            for item in full_ranking[:256]:
                output.write("\t".join(map(str, item)) + "\n")
        else:
            output.write("none_target_exact\n")

        output.write("\n[claim boundary]\n")
        output.write(
            "A fixed mixed arm assignment is a source-bounded timing "
            "hypothesis, not a fitted selector.  It is rejected unless "
            "one program satisfies all eleven targets and the complete "
            "cached wall; no result is promoted from target fit alone.\n"
        )

    print(
        f"wrote {args.report}: programs={len(candidates)} "
        f"best_target_miss={target_ranking[0][0]} "
        f"target_exact={len(target_exact)} "
        f"global_exact={sum(item[0] == 0 for item in full_ranking)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
