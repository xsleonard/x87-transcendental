#!/usr/bin/env python3
"""Report interval/product geometry for the 13 Round-49 residual lanes."""

from __future__ import annotations

import h58_constraint_search as h58
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h291_trig_sine_bias_coordinate_scan as h291
import h283_trig_sine_bias_selector as h283
import h326_p6_tmp_sine_projection as h326
import h332_round48_sine_interval_inversion as h332
import h333_p6_carrier_metadata_semantics as h333
import h337_round49_causal_localization as h337


CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


def exact_deltas(point, lane: int, node: str):
    return tuple(
        delta
        for delta in h337.DELTAS
        if h226.metric_for(
            point, h337.hidden_values(point, node, delta)
        )[lane]
        == h337.ZERO
    )


def main() -> None:
    count = 0
    for point in h228.points("sweep"):
        baseline = h226.metric_for(
            point, h333.hidden_values(point, CANDIDATE)
        )
        if baseline == h226.ZERO_JOINT:
            continue
        observed = point.prepared.joint.observed
        prepared = observed.point
        for lane in (0, 1):
            if baseline[lane] == h337.ZERO:
                continue
            if lane:
                lead, cross = prepared.cos_t, prepared.sin_t
            else:
                lead, cross = prepared.sin_t, prepared.cos_t
            carrier = h333.universal_carrier(point)
            lower = carrier[0], carrier[1] & ~1, carrier[2]
            upper = carrier[0], lower[1] + 2, carrier[2]
            exact = h58.mul_exact(cross, upper)
            shift = exact[1].bit_length() - 67
            remainder = exact[1] & ((1 << shift) - 1)
            fraction16 = (remainder << 16) >> shift
            low = h226.quantize(
                h58.mul_exact(cross, lower), "chop67"
            )
            high = h333.upper_exclusive_product(cross, upper)
            current = h333.p_product(cross, carrier, CANDIDATE)
            _, q_tail = h230.state(point, h228.CANDIDATE)
            exact_sum = h283.state_inputs(point)[-2]
            rn64 = h283.state_inputs(point)[-1]
            count += 1
            print(
                f"{count:02d} lane={'cos' if lane else 'sin'} "
                f"{observed.source}/{observed.family}/cell{prepared.cell} "
                f"coord={h291.coordinate(point)[0]} "
                f"proxy={h326.numerator(point)}/256 "
                f"p={exact_deltas(point, lane, 'p_product')} "
                f"corr={exact_deltas(point, lane, 'correction')} "
                f"qtail={exact_deltas(point, lane, 'cosine_tail')} "
                f"span={high[1] - low[1]} high-current={high[1] - current[1]} "
                f"upper-frac16=0x{fraction16:04x} "
                f"cross-low=0x{cross[1] & 0xffff:04x} "
                f"state-low=0x{upper[1] & 0xffff:04x} "
                f"q-low=0x{q_tail[1] & 0xffff:04x} "
                f"fadd-rem={h332.exact_remainder_256(exact_sum, rn64)}"
            )
    print(f"residual lanes={count}")


if __name__ == "__main__":
    main()
