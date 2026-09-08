#!/usr/bin/env python3
"""Classify and causally localize the independent h349 residuals."""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib

import h58_constraint_search as h58
import h171_fsin_table_correction_discriminator as h171
import h188_table_stage_local_pairs as h188
import h207_tang_literal_fadd as h207
import h216_fadd_microcontrol_discriminator as h216
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h291_trig_sine_bias_coordinate_scan as h291
import h326_p6_tmp_sine_projection as h326
import h332_round48_sine_interval_inversion as h332
import h333_p6_carrier_metadata_semantics as h333
import h337_round49_causal_localization as h337


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "capture-kit-captures" / "skylake-trig-h349"
CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


@dataclasses.dataclass(frozen=True)
class Residual:
    index: int
    se: int
    sig: int
    rc: str
    lane: str
    hardware: tuple[int, int]
    model: tuple[int, int]
    status: int
    step: int


def load(path: pathlib.Path):
    result = []
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        result.append(Residual(
            int(fields[0]),
            int(fields[1], 16),
            int(fields[2], 16),
            fields[3],
            fields[4],
            (int(fields[5], 16), int(fields[6], 16)),
            (int(fields[7], 16), int(fields[8], 16)),
            int(fields[9], 16),
            int(fields[10]),
        ))
    return result


def point_from_input(record: Residual):
    observed = h171.observed_from_input(record.index, record.se, record.sig)
    if observed is None:
        raise AssertionError(record)
    return h207.Point(h188.prepare(h216.blank(observed)), True)


def rotated_lane(point, lane: int, node: str, delta: int):
    return h337.hidden_values(point, node, delta)[lane]


def fixes_observation(point, record: Residual, node: str, delta: int):
    lane = int(record.lane == "cos")
    value = rotated_lane(point, lane, node, delta)
    return h58.x87_round(value, record.rc) == record.hardware


def nearest_delta(point, record: Residual, node: str):
    values = [
        delta
        for delta in h337.DELTAS
        if fixes_observation(point, record, node, delta)
    ]
    return min(values, key=lambda value: (abs(value), value)) if values else None


def geometry(point, record: Residual):
    observed = point.prepared.joint.observed
    prepared = observed.point
    cosine_lane = record.lane == "cos"
    lead, cross = (
        (prepared.cos_t, prepared.sin_t)
        if cosine_lane
        else (prepared.sin_t, prepared.cos_t)
    )
    carrier = h333.universal_carrier(point)
    lower = carrier[0], carrier[1] & ~1, carrier[2]
    upper = carrier[0], lower[1] + 2, carrier[2]
    exact = h58.mul_exact(cross, upper)
    shift = exact[1].bit_length() - 67
    remainder = exact[1] & ((1 << shift) - 1)
    fraction8 = (remainder << 8) >> shift
    low = h226.quantize(h58.mul_exact(cross, lower), "chop67")
    high = h333.upper_exclusive_product(cross, upper)
    current = h333.p_product(cross, carrier, CANDIDATE)
    _, q_tail = h230.state(point, h228.CANDIDATE)
    exact_sum = h283.state_inputs(point)[-2]
    rn64 = h283.state_inputs(point)[-1]
    return {
        "source/family": (observed.source, observed.family),
        "cell": prepared.cell,
        "quadrant": observed.signed_n & 3,
        "producer": (
            "cos-state"
            if bool(observed.signed_n & 1) == (record.lane == "sin")
            else "sin-state"
        ),
        "coordinate": h291.coordinate(point)[0],
        "proxy": h326.numerator(point),
        "span": high[1] - low[1],
        "high-current": high[1] - current[1],
        "upper-frac8": fraction8,
        "cross-low3": cross[1] & 7,
        "cross-low8": cross[1] & 0xFF,
        "lead-low3": lead[1] & 7,
        "state-low3": upper[1] & 7,
        "q-low3": q_tail[1] & 7,
        "fadd-rem-sign": (h332.exact_remainder_256(exact_sum, rn64) > 0)
        - (h332.exact_remainder_256(exact_sum, rn64) < 0),
    }
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=pathlib.Path, default=DEFAULT_CAPTURE)
    args = parser.parse_args()
    records = load(args.capture / "residuals.tsv")
    counts = collections.Counter()
    affected = {(record.se, record.sig) for record in records}
    for index, record in enumerate(records):
        point = point_from_input(record)
        predicted = h333.hidden_values(point, CANDIDATE)
        lane = int(record.lane == "cos")
        if h58.x87_round(predicted[lane], record.rc) != record.model:
            raise AssertionError((record, predicted))
        values = geometry(point, record)
        for name, value in values.items():
            counts[name, value] += 1
        counts["lane", record.lane] += 1
        counts["rc", record.rc] += 1
        counts["step", record.step] += 1
        for node in h337.NODES:
            counts[f"nearest-{node}", nearest_delta(point, record, node)] += 1
        if index % 256 == 0:
            h230.state.cache_clear()

    print(
        f"h353 broad residuals: result={len(records)}/6000000 "
        f"affected-inputs={len(affected)}/1000000 "
        f"parity={(6000000 - len(records)) / 6000000:.9%}"
    )
    names = (
        "lane", "rc", "step", "source/family", "cell", "quadrant",
        "producer", "coordinate", "proxy", "span", "high-current",
        "cross-low3", "lead-low3", "state-low3", "q-low3",
        "fadd-rem-sign", "nearest-cosine_tail", "nearest-q_product",
        "nearest-p_product", "nearest-correction",
    )
    for name in names:
        selected = {
            key[1]: value
            for key, value in counts.items()
            if key[0] == name
        }
        print(f"  {name}: {dict(sorted(selected.items(), key=lambda item: str(item[0])))}")


if __name__ == "__main__":
    main()
