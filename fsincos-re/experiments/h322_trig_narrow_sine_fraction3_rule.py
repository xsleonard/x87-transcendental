#!/usr/bin/env python3
"""Freeze the hardware-validated Round-48 shared-sine carrier rule."""

from __future__ import annotations

import functools

import h79_table_state_bias as h79
import h283_trig_sine_bias_selector as h283
import h291_trig_sine_bias_coordinate_scan as h291
import h316_trig_narrow_sine_fraction2_rule as h316


NARROW_FRACTIONAL_COORDINATE = (-7, 17)


@functools.lru_cache(maxsize=None)
def coordinate(point):
    return h291.coordinate(point)[0]


def hidden_values(point):
    observed = point.prepared.joint.observed
    if (
        observed.family == "narrow"
        and coordinate(point) == NARROW_FRACTIONAL_COORDINATE
    ):
        rn64 = h283.state_inputs(point)[-1]
        sine = h79.bias_toward_zero(rn64, 34, 8)
        return h291.hidden_values(point, sine)
    return h316.hidden_values(point)


if __name__ == "__main__":
    print("Round 48 rule loaded; validation is frozen by h319-h321 and h323.")
