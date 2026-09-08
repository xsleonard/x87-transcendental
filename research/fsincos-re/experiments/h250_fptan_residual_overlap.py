#!/usr/bin/env python3
"""Map FPTAN residuals against FSIN/FSINCOS table residuals."""

from __future__ import annotations

import collections

import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h245_fptan_shared_state as h245
import h246_fptan_operation_search as h246


FPTAN = h246.Candidate("away67", "chop67")


def main() -> None:
    joint = collections.Counter()
    strata = collections.Counter()
    for name in ("dense", "sweep"):
        hardware = h245.captures(name)
        for point in h228.points(name):
            observed = point.prepared.joint.observed
            fptan = h246.metric(point, hardware, FPTAN)[0]
            fsin, cosine = h226.metric_for(
                point, h230.hidden_values(point, h228.CANDIDATE)
            )
            fsin_miss = fsin[0]
            cosine_miss = cosine[0]
            joint[
                name,
                bool(fptan),
                bool(fsin_miss),
                bool(cosine_miss),
            ] += 1
            if fptan or fsin_miss or cosine_miss:
                strata[
                    name,
                    observed.source,
                    observed.point.cell,
                    observed.signed_n & 3,
                    bool(fptan),
                    bool(fsin_miss),
                    bool(cosine_miss),
                ] += 1
    print("joint input overlap:")
    for key, count in sorted(joint.items()):
        if any(key[1:]):
            print(f"  {key}: {count}")
    print("residual strata:")
    for key, count in sorted(strata.items()):
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
