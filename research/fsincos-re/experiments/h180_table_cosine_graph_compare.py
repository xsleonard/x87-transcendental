#!/usr/bin/env python3
"""Compare recovered table graphs on the shared cosine lane.

h177/h178 prove the architectural table values are shared by
FSIN/FCOS/FSINCOS.  The standalone-FSIN Tang graph was selected only through
the architectural sine result and predicts cosine poorly.  This pass scores
the earlier shared Round-24 graph, path-aware terminal graph, literal Tang
graph, and current Tang/P5 graph against paired cosine RN/RD/RU+C1.
"""

from __future__ import annotations

import collections
import dataclasses

import h58_constraint_search as h58
import h104_table_final_partial_search as h104
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h177_table_sibling_triangulation as h177


def cosine_points() -> list[h131.Observed]:
    points = h131.load_dataset(
        "dense", h131.INPUTS / "dense_qn.txt"
    )
    paired = {
        rc: h177.parse_pair(
            h177.PAIRED / f"dense_fsincos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    result = []
    for point in points:
        outputs = tuple(
            paired[rc][point.index][1] for rc in h58.RCS
        )
        c1 = tuple(
            paired[rc][point.index][2] for rc in h58.RCS
        )
        result.append(
            dataclasses.replace(
                point,
                signed_n=point.signed_n + 1,
                outputs=outputs,
                c1=c1,
            )
        )
    return result


def hidden(
    point: h131.Observed, graph: str
) -> h58.FP:
    if graph == "shared-round24":
        return h104.values(
            point.point, h104.Variant("delta-correction", 67, "rn")
        )[1]
    if graph == "shared-exact":
        return h104.values(point.point, h104.EXACT)[1]
    if graph == "path-aware":
        return h134.hidden_value(
            point, h135.path_candidate(point)
        )
    if graph == "tang-exact":
        return h136.hidden_value(point, h136.EXACT)
    if graph == "tang-p5":
        return h173.hidden(
            h173.make_terms(point), h173.CURRENT
        )
    raise ValueError(graph)


def main() -> None:
    points = cosine_points()
    graphs = (
        "shared-round24",
        "shared-exact",
        "path-aware",
        "tang-exact",
        "tang-p5",
    )
    for graph in graphs:
        groups = collections.Counter()
        for point in points:
            metric = h170.point_metric(
                point, hidden(point, graph)
            )
            key = (
                "train" if h131.is_train(point) else "held",
                point.family,
            )
            for index, name in enumerate(
                ("mode", "input", "c1")
            ):
                groups[key[0], key[1], name] += metric[index]
        total = tuple(
            sum(
                value
                for key, value in groups.items()
                if key[2] == metric_name
            )
            for metric_name in ("mode", "input", "c1")
        )
        print(f"h180 {graph:14s}: {total}")
        for partition in ("train", "held"):
            for family in ("narrow", "wide"):
                print(
                    f"  {partition:5s} {family:6s}: "
                    + "/".join(
                        str(groups[partition, family, name])
                        for name in ("mode", "input", "c1")
                    )
                )


if __name__ == "__main__":
    main()
