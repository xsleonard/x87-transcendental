#!/usr/bin/env python3
"""Project joint table error onto Tang's p(r) and q(r) state axes.

For every dense table residual, FSINCOS exposes both sine and cosine while
h177 proves those values are shared with standalone FSIN/FCOS.  The current
model is evaluated for both lanes.  Hardware interval midpoint deltas
``dS,dC`` are rotated approximately back into:

    dp = Cj*dS - Sj*dC
    dq = Sj*dS + Cj*dC

Opposite S/C directions are p-like; equal directions are q-like.  This
localizes which producer state deserves the next low-bit search.
"""

from __future__ import annotations

import collections
import dataclasses

import h58_constraint_search as h58
import h131_fsin_table_c1_search as h131
import h155_fsin_cosine_state_tomography as h155
import h169_fsin_table_round33_tomography as h169
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h177_table_sibling_triangulation as h177


def main() -> None:
    points = h131.load_dataset(
        "dense", h131.INPUTS / "dense_qn.txt"
    )
    paired = {
        rc: h177.parse_pair(
            h177.PAIRED / f"dense_fsincos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    kinds: collections.Counter[
        tuple[str, str]
    ] = collections.Counter()
    mechanism: collections.Counter[str] = collections.Counter()
    families: dict[
        tuple[str, int], collections.Counter[str]
    ] = collections.defaultdict(collections.Counter)
    scores = collections.Counter()

    for point in points:
        index = point.index
        pair_cosine = tuple(
            paired[rc][index][1] for rc in h58.RCS
        )
        pair_c1 = tuple(
            paired[rc][index][2] for rc in h58.RCS
        )
        cosine_observed = dataclasses.replace(
            point, outputs=pair_cosine, c1=pair_c1
        )
        cosine_lane = dataclasses.replace(
            cosine_observed,
            signed_n=cosine_observed.signed_n + 1,
        )

        sine_hidden = h169.hidden(point)
        cosine_hidden = h173.hidden(
            h173.make_terms(cosine_lane), h173.CURRENT
        )
        sine_kind, ds = h169.magnitude_relation(
            point, sine_hidden
        )
        cosine_kind, dc = h169.magnitude_relation(
            cosine_observed, cosine_hidden
        )
        kinds[sine_kind, cosine_kind] += 1

        sine_metric = h170.point_metric(
            point, sine_hidden
        )
        cosine_metric = h170.point_metric(
            cosine_observed, cosine_hidden
        )
        scores["sine-mode"] += sine_metric[0]
        scores["sine-input"] += sine_metric[1]
        scores["sine-c1"] += sine_metric[2]
        scores["cosine-mode"] += cosine_metric[0]
        scores["cosine-input"] += cosine_metric[1]
        scores["cosine-c1"] += cosine_metric[2]

        if sine_kind == "inside" and cosine_kind == "inside":
            continue
        sj = h155.fp_fraction(point.point.sin_t)
        cj = h155.fp_fraction(point.point.cos_t)
        dp = cj * ds - sj * dc
        dq = sj * ds + cj * dc
        if abs(dp) > abs(dq):
            label = "p-dominant"
        elif abs(dq) > abs(dp):
            label = "q-dominant"
        else:
            label = "tied"
        mechanism[label] += 1
        families[point.family, point.point.cell][label] += 1

    print(f"h179 dense joint table points: {len(points)}")
    print(f"  model scores: {dict(scores)}")
    print("  joint interval directions:")
    for key, count in kinds.most_common():
        if key != ("inside", "inside"):
            print(f"    {key}: {count}")
    print(f"  projected outside states: {dict(mechanism)}")
    print("  projected state by family/cell:")
    for key, counts in sorted(families.items()):
        print(f"    {key}: {dict(counts)}")


if __name__ == "__main__":
    main()
