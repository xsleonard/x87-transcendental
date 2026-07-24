#!/usr/bin/env python3
"""Cross-validate transfer schedules for the wide table q chain.

Round 18 identified a chop67 square plus fused-RN64 Horner producer in the
direct polynomial region.  This pass independently varies whether the wide
q Horner and its final tail multiply use that square, plus the final
materialization width.  Candidates must survive the complete direct-table
capture, h59, and the fresh h67 discriminator.
"""

from __future__ import annotations

import dataclasses
import pathlib

import h58_constraint_search as h58
import h59_discriminator as h59
import h65_poly_discriminator as h65
import h67_wide_producer_discriminator as h67


ROOT = pathlib.Path(__file__).resolve().parents[1]
DENSE_CAPTURE = ROOT / "capture-kit-captures" / "pentiumII"
H59_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h59-constraints"
)
H59_INPUTS = H59_CAPTURE / "wide_inputs.txt"
H67_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_wide_producer_h67.txt"
)
H67_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h67-wide-producer"
)


@dataclasses.dataclass(frozen=True)
class Schedule:
    q_candidate: bool
    tail_square_candidate: bool
    tail_bits: int
    tail_mode: str
    q_product: bool = False

    def short(self) -> str:
        q_name = (
            "r18-product"
            if self.q_product
            else "r18"
            if self.q_candidate
            else "base"
        )
        return (
            f"q={q_name} "
            f"tail-sq={'r18' if self.tail_square_candidate else 'base'} "
            f"t={self.tail_mode}{self.tail_bits}"
        )


BASELINE = Schedule(False, False, 64, "rn")
ROUND19 = Schedule(True, True, 64, "rn")
ROUND19_PRODUCT = Schedule(True, True, 64, "rn", True)


def values(
    raw: h58.RawPoint,
    schedule: Schedule,
) -> tuple[h58.FP, h58.FP]:
    magnitude = (0, raw.sig, raw.exponent - 63)
    baseline = h67.prepare_magnitude(
        magnitude, raw.sign, h58.BASE_PRODUCER
    )
    candidate = h67.prepare_magnitude(
        magnitude, raw.sign, h65.CANDIDATE_PRODUCER
    )
    candidate_product = h67.prepare_magnitude(
        magnitude,
        raw.sign,
        h65.CANDIDATE_PRODUCER,
        h65.CANDIDATE_Q_FINAL_PRODUCT_BITS,
    )
    q_point = (
        candidate_product
        if schedule.q_product
        else candidate
        if schedule.q_candidate
        else baseline
    )
    tail_point = (
        candidate if schedule.tail_square_candidate else baseline
    )
    m = h58.fmul(baseline.p, baseline.asq, 64, "rn")
    correction = h58.fmul(m, baseline.a, 64, "rn")
    sine_a = h58.fadd(baseline.a, correction, 64, "rn")
    tail = h58.fmul(
        q_point.q,
        tail_point.asq,
        schedule.tail_bits,
        schedule.tail_mode,
    )
    one_plus_tail = h58.add_exact(h58.ONE, tail)
    sine = h58.add_exact(
        h58.mul_exact(baseline.sin_t, one_plus_tail),
        h58.mul_exact(baseline.cos_t, sine_a),
    )
    cosine = h58.add_exact(
        h58.mul_exact(baseline.cos_t, one_plus_tail),
        h58.neg(h58.mul_exact(baseline.sin_t, sine_a)),
    )
    if raw.sign:
        sine = h58.neg(sine)
    return sine, cosine


def score_many(
    raw: list[h58.RawPoint],
    schedules: list[Schedule],
) -> dict[Schedule, h58.Score]:
    results = {
        schedule: h58.Score(total_outputs=2 * len(raw))
        for schedule in schedules
    }
    for point in raw:
        magnitude = (0, point.sig, point.exponent - 63)
        baseline = h67.prepare_magnitude(
            magnitude, point.sign, h58.BASE_PRODUCER
        )
        candidate = h67.prepare_magnitude(
            magnitude, point.sign, h65.CANDIDATE_PRODUCER
        )
        candidate_product = h67.prepare_magnitude(
            magnitude,
            point.sign,
            h65.CANDIDATE_PRODUCER,
            h65.CANDIDATE_Q_FINAL_PRODUCT_BITS,
        )
        m = h58.fmul(baseline.p, baseline.asq, 64, "rn")
        correction = h58.fmul(m, baseline.a, 64, "rn")
        sine_a = h58.fadd(baseline.a, correction, 64, "rn")
        for schedule in schedules:
            result = results[schedule]
            q_point = (
                candidate_product
                if schedule.q_product
                else candidate
                if schedule.q_candidate
                else baseline
            )
            tail_point = (
                candidate
                if schedule.tail_square_candidate
                else baseline
            )
            tail = h58.fmul(
                q_point.q,
                tail_point.asq,
                schedule.tail_bits,
                schedule.tail_mode,
            )
            one_plus_tail = h58.add_exact(h58.ONE, tail)
            predicted = (
                h58.add_exact(
                    h58.mul_exact(baseline.sin_t, one_plus_tail),
                    h58.mul_exact(baseline.cos_t, sine_a),
                ),
                h58.add_exact(
                    h58.mul_exact(baseline.cos_t, one_plus_tail),
                    h58.neg(h58.mul_exact(baseline.sin_t, sine_a)),
                ),
            )
            if point.sign:
                predicted = h58.neg(predicted[0]), predicted[1]
            for side, value in enumerate(predicted):
                output_missed = False
                for rc_index, rc in enumerate(h58.RCS):
                    mismatch = (
                        h58.x87_round(value, rc)
                        != point.hw[rc_index][side]
                    )
                    result.mode_misses += mismatch
                    result.rn_misses += mismatch if rc == "rn" else 0
                    output_missed |= mismatch
                result.constrained_output_misses += output_missed
    return results


def rank(result: h58.Score) -> tuple[int, int, int]:
    return (
        int(result.mode_misses),
        int(result.constrained_output_misses),
        int(result.rn_misses),
    )


def main() -> None:
    dense = [
        point
        for point in h58.load_points(DENSE_CAPTURE)
        if h58.prepare(point).wide
    ]
    h59_points = h59.load_score_points(
        H59_INPUTS, H59_CAPTURE, "wide"
    )
    h67_points = h59.load_score_points(
        H67_INPUTS, H67_CAPTURE, "constraint_wide_producer"
    )
    datasets = (
        ("dense", dense),
        ("h59", h59_points),
        ("h67", h67_points),
    )
    schedules = [
        Schedule(q_candidate, tail_candidate, bits, mode)
        for q_candidate in (False, True)
        for tail_candidate in (False, True)
        for bits in range(64, 73)
        for mode in ("rn", "chop")
    ]
    schedules.append(ROUND19_PRODUCT)
    per_dataset = [
        score_many(points, schedules) for _, points in datasets
    ]
    scores = {
        schedule: tuple(
            dataset_scores[schedule]
            for dataset_scores in per_dataset
        )
        for schedule in schedules
    }
    baseline = scores[BASELINE]
    print(
        "datasets: "
        + ", ".join(
            f"{name}={len(points)} inputs" for name, points in datasets
        )
    )
    for name, schedule in (
        ("baseline", BASELINE),
        ("round19", ROUND19),
        ("round19-product", ROUND19_PRODUCT),
    ):
        print(name)
        for (dataset, _), result in zip(datasets, scores[schedule]):
            print(f"  {dataset:5s} {result.describe()}")

    admissible = []
    for schedule, results in scores.items():
        if all(
            rank(result) <= rank(base)
            for result, base in zip(results, baseline)
        ) and any(
            rank(result) < rank(base)
            for result, base in zip(results, baseline)
        ):
            combined = tuple(
                sum(rank(result)[index] for result in results)
                for index in range(3)
            )
            admissible.append((combined, schedule, results))
    admissible.sort(key=lambda row: (row[0], row[1].short()))
    print(f"jointly non-worse schedules: {len(admissible)}")
    for _, schedule, results in admissible[:12]:
        print(f"  {schedule.short()}")
        for (dataset, _), result in zip(datasets, results):
            print(f"    {dataset:5s} {result.describe()}")


if __name__ == "__main__":
    main()
