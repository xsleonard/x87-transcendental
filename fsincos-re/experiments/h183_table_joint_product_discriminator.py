#!/usr/bin/env python3
"""Build fresh joint-lane separators for h182's wide P*square carrier.

Six away/odd 64..66-bit representatives survive all existing sine and
cosine gates.  Generation is hardware-blind and keeps table inputs where a
representative changes either lane's output or increment prediction.
Hardware scoring uses standalone FSIN for sine+C1 and paired FSINCOS for
cosine+C1.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import random
import sys

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h135_fsin_table_terminal_discriminator as h135
import h171_fsin_table_correction_discriminator as h171
import h175_fsin_table_path_discriminator as h175
import h177_table_sibling_triangulation as h177
import h182_table_joint_terminal_edges as h182


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_joint_product_h183.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_joint_product_h183.meta.txt"
)
SEED = 0xF183C5
CANDIDATES = tuple(
    h182.Candidate("p-square", h110.Quant(bits, mode))
    for bits in (64, 65, 66)
    for mode in ("away", "odd")
)


@dataclasses.dataclass(frozen=True)
class Prepared:
    point: h182.Point
    square: h58.FP
    p: h58.FP
    one_plus_tail: h58.FP


def prepare(point: h182.Point) -> Prepared:
    observed = point.observed
    schedule = h135.path_candidate(observed)
    square = h58.fmul(
        observed.point.a, observed.point.a, 64, "rn"
    )
    p = h134.horner(
        h58.S6,
        square,
        schedule.p_coefficients,
        schedule.p_products,
        schedule.p_sums,
    )
    q = h134.horner(
        h58.C6,
        square,
        schedule.q_coefficients,
        schedule.q_products,
        schedule.q_sums,
    )
    tail = h58.fmul(q, square, 64, "rn")
    return Prepared(
        point, square, p, h58.add_exact(h58.ONE, tail)
    )


def candidate_values(
    prepared: Prepared, candidate: h182.Candidate
) -> tuple[h58.FP, h58.FP]:
    point = prepared.point.observed
    quant = (
        candidate.quant
        if candidate.edge == "p-square"
        else h110.Quant(64, "rn")
    )
    m = h110.quantize(
        h58.mul_exact(prepared.p, prepared.square), quant
    )
    correction = h58.fmul(m, point.point.a, 64, "rn")
    sine_a = h58.fadd(point.point.a, correction, 64, "rn")
    sine_a = h79.bias_toward_zero(sine_a, 5)
    sine = h104.lane_value(
        point.point.sin_t,
        point.point.cos_t,
        prepared.one_plus_tail,
        sine_a,
        False,
        h134.VARIANT,
    )
    cosine = h104.lane_value(
        point.point.cos_t,
        point.point.sin_t,
        prepared.one_plus_tail,
        sine_a,
        True,
        h134.VARIANT,
    )
    if point.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate((sine, cosine), point.signed_n)


def profile(
    point: Prepared, candidate: h182.Candidate
) -> tuple[tuple[tuple[tuple[int, int], bool], ...], ...]:
    values = candidate_values(point, candidate)
    return tuple(
        tuple(
            (
                output := h58.x87_round(value, rc),
                h110.compare_magnitude(output, value) > 0,
            )
            for rc in h58.RCS
        )
        for value in values
    )


def difference_mask(left, right) -> int:
    mask = 0
    for lane, (old_lane, new_lane) in enumerate(
        zip(left, right)
    ):
        for index, (old, new) in enumerate(
            zip(old_lane, new_lane)
        ):
            bit = lane * 6 + index
            if old[0] != new[0]:
                mask |= 1 << bit
            if old[1] != new[1]:
                mask |= 1 << (bit + 3)
    return mask


def blank(point: h131.Observed) -> h182.Point:
    return h182.Point(
        point,
        ((0, 0),) * len(h58.RCS),
        (False,) * len(h58.RCS),
    )


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    per_candidate: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    rows = []
    meta = []
    counts: collections.Counter[str] = collections.Counter()
    states = set()
    for scan_index in range(scan_limit):
        constructed = None
        if rng.getrandbits(1):
            se, sig = h135.direct_operand(rng, "wide")
        else:
            constructed = h175.construct_table_input(rng)
            if constructed is None:
                continue
            se, sig = constructed[:2]
        observed = h171.observed_from_input(
            scan_index, se, sig
        )
        if observed is None or observed.family != "wide":
            continue
        if (
            constructed is not None
            and abs(observed.signed_n) != constructed[2]
        ):
            continue
        key = (
            observed.source,
            observed.signed_n & 3,
            observed.point.cell,
            observed.point.a,
        )
        if key in states:
            continue
        point = prepare(blank(observed))
        baseline = profile(point, h182.CURRENT)
        separated = []
        masks = []
        for candidate in CANDIDATES:
            name = candidate.short()
            if counts[name] >= per_candidate:
                continue
            mask = difference_mask(
                baseline, profile(point, candidate)
            )
            if mask:
                separated.append(candidate)
                masks.append(mask)
        if not separated:
            continue
        states.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        labels = ",".join(
            f"{candidate.short()}:{mask:03x}"
            for candidate, mask in zip(separated, masks)
        )
        meta.append(
            f"{scan_index} {observed.source} "
            f"{observed.signed_n} {observed.point.cell} {labels}"
        )
        for candidate in separated:
            counts[candidate.short()] += 1
        if all(
            counts[candidate.short()] >= per_candidate
            for candidate in CANDIDATES
        ):
            break
    missing = {
        candidate.short(): counts[candidate.short()]
        for candidate in CANDIDATES
        if counts[candidate.short()] < per_candidate
    }
    if missing:
        raise SystemExit(
            f"h183 stopped after {scan_limit} scans; "
            f"incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h183: selected {len(rows)} inputs from "
        f"{scan_index + 1} scans; "
        f"per-candidate={dict(sorted(counts.items()))}; "
        f"seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path, capture: pathlib.Path
) -> list[h182.Point]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    sine_modes = [
        (
            capture
            / f"constraint_table_joint_product_h183_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    pair_modes = [
        (
            capture
            / f"constraint_table_joint_product_h183_fsincos_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(
        len(lines) != len(operands)
        for lines in (*sine_modes, *pair_modes)
    ):
        raise SystemExit("h183 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        point = h171.observed_from_input(index, se, sig)
        if point is None or point.family != "wide":
            raise SystemExit(
                f"h183 input {index + 1} is not wide table"
            )
        sine_outputs = []
        sine_c1 = []
        cosine_outputs = []
        cosine_c1 = []
        for sine_lines, pair_lines in zip(
            sine_modes, pair_modes
        ):
            sine_fields = sine_lines[index].split()
            pair_fields = pair_lines[index].split()
            if (
                len(sine_fields) != 5
                or sine_fields[0] != "OK"
                or sine_fields[3] != "SW"
                or len(pair_fields) != 7
                or pair_fields[0] != "OK"
                or pair_fields[5] != "SW"
            ):
                raise ValueError(
                    (sine_lines[index], pair_lines[index])
                )
            sine_outputs.append(
                (int(sine_fields[1], 16), int(sine_fields[2], 16))
            )
            sine_c1.append(
                bool(int(sine_fields[4], 16) & 0x0200)
            )
            cosine_outputs.append(
                (int(pair_fields[3], 16), int(pair_fields[4], 16))
            )
            cosine_c1.append(
                bool(int(pair_fields[6], 16) & 0x0200)
            )
        observed = dataclasses.replace(
            point,
            outputs=tuple(sine_outputs),
            c1=tuple(sine_c1),
        )
        result.append(
            h182.Point(
                observed,
                tuple(cosine_outputs),
                tuple(cosine_c1),
            )
        )
    return result


def score(
    points: list[h182.Point],
    candidate: h182.Candidate,
) -> tuple[h182.Metric, h182.Metric]:
    return h182.score(points, candidate)


def componentwise(value, baseline) -> bool:
    return all(
        all(new <= old for new, old in zip(new_lane, old_lane))
        for new_lane, old_lane in zip(value, baseline)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-candidate", type=int, default=64)
    parser.add_argument(
        "--scan-limit", type=int, default=30_000_000
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=DEFAULT_OUTPUT
    )
    parser.add_argument(
        "--metadata",
        type=pathlib.Path,
        default=DEFAULT_METADATA,
    )
    args = parser.parse_args()
    if args.generate:
        generate(
            args.output,
            args.metadata,
            args.per_candidate,
            args.scan_limit,
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        metadata = args.metadata.read_text().splitlines()
        print(f"loaded {len(points)} fresh h183 separators")
        for candidate in CANDIDATES:
            name = candidate.short()
            targeted = [
                point
                for point, line in zip(points, metadata)
                if any(
                    item.split(":", 1)[0] == name
                    for item in line.split()[-1].split(",")
                )
            ]
            baseline = score(targeted, h182.CURRENT)
            value = score(targeted, candidate)
            status = (
                "PASS" if componentwise(value, baseline) else "FAIL"
            )
            print(
                f"{status} {name:15s} n={len(targeted):3d} "
                f"sine {baseline[0]}->{value[0]} "
                f"cosine {baseline[1]}->{value[1]}"
            )
    if not args.generate and args.score is None:
        parser.error(
            "select --generate and/or --score CAPTURE_DIRECTORY"
        )


if __name__ == "__main__":
    main()
