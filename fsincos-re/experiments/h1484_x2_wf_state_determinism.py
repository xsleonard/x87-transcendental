#!/usr/bin/env python3
"""Test whether retained X2-to-WF state can determine the R1475 function.

H1483 excluded every tested retained signal individually.  This audit treats
the complete grouped state as a vector: an opposite-value collision proves
that no deterministic downstream circuit over that vector can implement
R1475.  If a vector is collision-free on the finite wall, the script also
searches every pair of its distinct Boolean columns for a two-input support.

H1476 rows supply R1475 software function values, not hardware labels.  This
script executes only the diagnostic software model and never opens H1477.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import (
    replay_anchors,
    replay_disjoint,
    replay_h1472,
    trace_tree,
)
from h1483_p5_wf_latch_isomorphism import bit, group_state, latch_features


RELATIVE_GROUP = re.compile(r"^[^.]+\.w04\.rel([+-][0-9]+)\.")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def full_p5_features(row: dict[str, str], config) -> dict[str, int]:
    _, _, (sum_vector, carry_vector) = trace_tree(row, config)
    values = {}
    for group in range(32):
        start = 2 + 4 * group
        end = start + 4
        state = group_state(sum_vector, carry_vector, start, end)
        stem = f"fullp5.group{group:02d}"
        for name, value in zip(
                ("g", "p", "c0", "c1", "cin", "cout"), state):
            values[f"{stem}.{name}"] = value
        for assumed in (0, 1):
            carry = assumed
            for offset, position in enumerate(range(start, end)):
                left = bit(sum_vector, position)
                right = bit(carry_vector, position)
                values[f"{stem}.sum{assumed}.b{offset}"] = (
                    left ^ right ^ carry
                )
                carry = (left & right) | ((left ^ right) & carry)

        prefix = group_state(sum_vector, carry_vector, 2, end)
        for name, value in zip(("g", "p", "c0", "c1"), prefix[:4]):
            values[f"fullp5.prefix{group:02d}.{name}"] = value

    top_cin = group_state(sum_vector, carry_vector, 2, 130)[5]
    top_left = bit(sum_vector, 130)
    top_right = bit(carry_vector, 130)
    values.update({
        "fullp5.top.sum": top_left,
        "fullp5.top.carry": top_right,
        "fullp5.top.propagate": top_left ^ top_right,
        "fullp5.top.generate": top_left & top_right,
        "fullp5.top.cin": top_cin,
        "fullp5.top.out": top_left ^ top_right ^ top_cin,
    })
    return values


def family_names(names: list[str]) -> dict[str, list[str]]:
    families = {
        "bounded_mixed_width_gp": [
            name for name in names
            if not name.startswith("fullp5.")
            and name.endswith((".g", ".p"))
        ],
        "p5_w04_local_gp": [
            name for name in names
            if name.startswith("p5.w04.") and name.endswith((".g", ".p"))
        ],
        "p5_w04_local_state": [
            name for name in names if name.startswith("p5.w04.")
        ],
        "p5_local_prefix_gp": [
            name for name in names
            if name.startswith("p5prefix.") and name.endswith((".g", ".p"))
        ],
        "p5_w04_full_gp": [
            name for name in names
            if name.startswith("fullp5.group")
            and name.endswith((".g", ".p"))
        ],
        "p5_w04_full_group_state": [
            name for name in names if name.startswith("fullp5.group")
        ],
        "p5_w04_full_gp_and_prefix": [
            name for name in names
            if name.startswith(("fullp5.group", "fullp5.prefix"))
            and name.endswith((".g", ".p"))
        ],
        "p5_w04_full_state": [
            name for name in names if name.startswith("fullp5.")
        ],
        "full_bounded_state": names,
    }
    for radius in range(5):
        selected = []
        for name in names:
            match = RELATIVE_GROUP.match(name)
            if match is not None and name.startswith("p5.w04.") \
                    and abs(int(match.group(1))) <= radius:
                selected.append(name)
        families[f"p5_w04_radius_{radius}"] = selected
    return families


def bit_pattern(rows: list[dict[str, int]], name: str) -> int:
    result = 0
    for index, row in enumerate(rows):
        result |= int(row[name]) << index
    return result


def popcount(value: int) -> int:
    return bin(value).count("1")


def collision_audit(
        rows: list[dict[str, object]], features: list[dict[str, int]],
        names: list[str], context_fields: tuple[str, ...] = ()) -> dict[str, object]:
    groups: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for index, values in enumerate(features):
        context = tuple(rows[index][field] for field in context_fields)
        groups[context + tuple(values[name] for name in names)].append(index)
    mixed = []
    for indexes in groups.values():
        values = {int(rows[index]["value"]) for index in indexes}
        if len(values) != 2:
            continue
        left = next(index for index in indexes if int(rows[index]["value"]) == 0)
        right = next(index for index in indexes if int(rows[index]["value"]) == 1)
        mixed.append({
            "zero": {
                "name": rows[left]["name"],
                "mode": rows[left]["mode"],
                "operand": rows[left]["operand"],
                "provenance": rows[left]["provenance"],
            },
            "one": {
                "name": rows[right]["name"],
                "mode": rows[right]["mode"],
                "operand": rows[right]["operand"],
                "provenance": rows[right]["provenance"],
            },
            "group_rows": len(indexes),
        })
    return {
        "features": len(names),
        "context_fields": list(context_fields),
        "unique_signatures": len(groups),
        "mixed_signatures": len(mixed),
        "mixed_rows": sum(item["group_rows"] for item in mixed),
        "opposite_value_witnesses": mixed,
        "deterministic_on_wall": not mixed,
    }


def exact_pair_supports(
        rows: list[dict[str, object]], features: list[dict[str, int]],
        names: list[str], detail_limit: int = 24) -> dict[str, object]:
    count = len(rows)
    universe = (1 << count) - 1
    truth = sum(int(row["value"]) << index for index, row in enumerate(rows))
    by_pattern: dict[int, list[str]] = defaultdict(list)
    for name in names:
        by_pattern[bit_pattern(features, name)].append(name)
    patterns = sorted(by_pattern)

    exact_literals = []
    for pattern in patterns:
        if pattern == truth or (pattern ^ universe) == truth:
            exact_literals.extend(by_pattern[pattern])

    table_counts: Counter[str] = Counter()
    support_pattern_pairs = 0
    support_signal_pairs = 0
    details = []
    for left_index, left in enumerate(patterns):
        for right in patterns[left_index + 1:]:
            buckets = (
                ((~left) & (~right) & universe),
                ((~left) & right & universe),
                (left & (~right) & universe),
                (left & right),
            )
            table = []
            for bucket in buckets:
                positive = bucket & truth
                if not bucket:
                    table.append("x")
                elif not positive:
                    table.append("0")
                elif positive == bucket:
                    table.append("1")
                else:
                    table.append("m")
            if "m" in table:
                continue
            encoded = "".join(table)
            support_pattern_pairs += 1
            syntaxes = len(by_pattern[left]) * len(by_pattern[right])
            support_signal_pairs += syntaxes
            table_counts[encoded] += syntaxes
            if len(details) < detail_limit:
                details.append({
                    "left_pattern": format(left, f"0{count}b")[::-1],
                    "right_pattern": format(right, f"0{count}b")[::-1],
                    "left_signals": sorted(by_pattern[left]),
                    "right_signals": sorted(by_pattern[right]),
                    "truth_table_00_01_10_11": encoded,
                    "signal_pair_syntaxes": syntaxes,
                })
    return {
        "features": len(names),
        "distinct_feature_patterns": len(patterns),
        "exact_single_literals": sorted(exact_literals),
        "exact_pair_pattern_supports": support_pattern_pairs,
        "exact_pair_signal_supports": support_signal_pairs,
        "truth_table_signal_pair_counts": dict(sorted(table_counts.items())),
        "support_details_limited": details,
        "detail_limit": detail_limit,
    }


def minimum_arbitrary_support(
        rows: list[dict[str, object]], features: list[dict[str, int]],
        names: list[str], maximum: int = 4) -> dict[str, object]:
    """Find the smallest signal set whose joint value determines the label.

    Feature columns are canonicalized up to complement because arbitrary
    downstream Boolean logic can invert an input without gaining information.
    """
    count = len(rows)
    universe = (1 << count) - 1
    truth = sum(int(row["value"]) << index for index, row in enumerate(rows))
    by_pattern: dict[int, list[str]] = defaultdict(list)
    for name in names:
        raw = bit_pattern(features, name)
        canonical = min(raw, raw ^ universe)
        oriented = name if raw == canonical else "!" + name
        by_pattern[canonical].append(oriented)
    by_pattern.pop(0, None)
    patterns = sorted(by_pattern)

    zeros = [index for index, row in enumerate(rows) if not int(row["value"])]
    ones = [index for index, row in enumerate(rows) if int(row["value"])]
    cross_pairs = [(zero, one) for zero in zeros for one in ones]
    pair_universe = (1 << len(cross_pairs)) - 1
    patterns_by_cover: dict[int, list[int]] = defaultdict(list)
    for pattern in patterns:
        cover = 0
        for pair_index, (zero, one) in enumerate(cross_pairs):
            if ((pattern >> zero) ^ (pattern >> one)) & 1:
                cover |= 1 << pair_index
        if cover:
            patterns_by_cover[cover].append(pattern)

    covers = sorted(patterns_by_cover, key=lambda item: (-popcount(item), item))
    maximal_covers = []
    for cover in covers:
        if any(cover | kept == kept for kept in maximal_covers):
            continue
        maximal_covers.append(cover)
    covers = maximal_covers
    bit_candidates = [[] for _ in cross_pairs]
    for cover_index, cover in enumerate(covers):
        for bit_index in range(len(cross_pairs)):
            if (cover >> bit_index) & 1:
                bit_candidates[bit_index].append(cover_index)

    search_nodes: dict[str, int] = {}
    selected_cover_indexes = None
    for width in range(1, maximum + 1):
        seen: set[tuple[int, int]] = set()
        nodes = 0

        def search(covered: int, remaining: int, chosen: tuple[int, ...]):
            nonlocal nodes
            nodes += 1
            if covered == pair_universe:
                return chosen
            if not remaining:
                return None
            key = (covered, remaining)
            if key in seen:
                return None
            seen.add(key)
            uncovered = pair_universe ^ covered
            gains = [
                popcount(cover & uncovered) for cover in covers
            ]
            best_gain = max(gains, default=0)
            if not best_gain or (popcount(uncovered) + best_gain - 1) \
                    // best_gain > remaining:
                return None
            uncovered_bits = [
                bit_index for bit_index in range(len(cross_pairs))
                if (uncovered >> bit_index) & 1
            ]
            pivot = min(
                uncovered_bits,
                key=lambda bit_index: sum(
                    gains[index] > 0
                    for index in bit_candidates[bit_index]
                ),
            )
            candidates = sorted(
                bit_candidates[pivot],
                key=lambda index: (-gains[index], covers[index], index),
            )
            for index in candidates:
                if not gains[index]:
                    continue
                result = search(
                    covered | covers[index], remaining - 1,
                    chosen + (index,))
                if result is not None:
                    return result
            return None

        selected_cover_indexes = search(0, width, ())
        search_nodes[str(width)] = nodes
        if selected_cover_indexes is not None:
            break

    if selected_cover_indexes is not None:
        selected_covers = [covers[index] for index in selected_cover_indexes]
        selected_patterns = [
            patterns_by_cover[cover][0] for cover in selected_covers
        ]
        table_values: list[str | None] = [None] * (1 << len(selected_patterns))
        for row_index in range(count):
            code = sum(
                ((pattern >> row_index) & 1) << bit_index
                for bit_index, pattern in enumerate(selected_patterns)
            )
            value = str((truth >> row_index) & 1)
            if table_values[code] is not None and table_values[code] != value:
                raise RuntimeError("set-cover support did not determine truth")
            table_values[code] = value
        return {
            "features": len(names),
            "canonical_nonconstant_patterns": len(patterns),
            "cross_label_pairs": len(cross_pairs),
            "distinct_pair_separation_covers": len(patterns_by_cover),
            "nondominated_pair_separation_covers": len(covers),
            "minimum_support": len(selected_patterns),
            "support_witness": {
                "patterns": [
                    format(pattern, f"0{count}b")[::-1]
                    for pattern in selected_patterns
                ],
                "signals": [
                    sorted(by_pattern[pattern])
                    for pattern in selected_patterns
                ],
                "equivalent_patterns_per_cover": [
                    len(patterns_by_cover[cover]) for cover in selected_covers
                ],
                "truth_table_lsb_first": "".join(
                    value if value is not None else "x"
                    for value in table_values
                ),
            },
            "search_nodes_by_width": search_nodes,
        }
    return {
        "features": len(names),
        "canonical_nonconstant_patterns": len(patterns),
        "cross_label_pairs": len(cross_pairs),
        "distinct_pair_separation_covers": len(patterns_by_cover),
        "nondominated_pair_separation_covers": len(covers),
        "minimum_support": None,
        "maximum_width_searched": maximum,
        "support_witness": None,
        "search_nodes_by_width": search_nodes,
    }


def selftest_minimum_support() -> None:
    xor_rows = [{"value": ((index >> 0) ^ (index >> 1)) & 1}
                for index in range(4)]
    xor_features = [
        {"a": (index >> 0) & 1, "b": (index >> 1) & 1}
        for index in range(4)
    ]
    if minimum_arbitrary_support(
            xor_rows, xor_features, ["a", "b"], maximum=2
            )["minimum_support"] != 2:
        raise RuntimeError("two-input support selftest failed")

    parity_rows = [{"value": bin(index).count("1") & 1}
                   for index in range(8)]
    parity_features = [
        {name: (index >> bit_index) & 1
         for bit_index, name in enumerate(("a", "b", "c"))}
        for index in range(8)
    ]
    if minimum_arbitrary_support(
            parity_rows, parity_features, ["a", "b", "c"], maximum=3
            )["minimum_support"] != 3:
        raise RuntimeError("three-input support selftest failed")

    collision_rows = [{"value": 0}, {"value": 1}]
    collision_features = [{"a": 0}, {"a": 0}]
    if minimum_arbitrary_support(
            collision_rows, collision_features, ["a"], maximum=2
            )["minimum_support"] is not None:
        raise RuntimeError("collision support selftest failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1472_score", type=Path)
    parser.add_argument("h1476_bank", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    selftest_minimum_support()

    labeled = replay_h1472(args.model, args.h1472_score)
    labeled.extend(replay_anchors(args.model))
    disjoint = replay_disjoint(args.model, args.h1476_bank)
    rows = labeled + disjoint
    if len(labeled) != 18 or len(disjoint) != 22:
        raise RuntimeError("H1472/H1476 row census changed")

    layouts = []
    aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    labeled_aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    mode_aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    labeled_mode_aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    pair_aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    minimum_aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    for layout_name, axis, config in tree_variants():
        feature_rows = []
        for row in rows:
            features = latch_features(row["row"], config)
            if len(features) != 898:
                raise RuntimeError("H1483 feature schema changed")
            features.update(full_p5_features(row["row"], config))
            feature_rows.append(features)
        names = sorted(feature_rows[0])
        if any(sorted(item) != names for item in feature_rows):
            raise RuntimeError("combined latch feature schema changed")
        families = family_names(names)
        collision_results = {}
        for family, selected in families.items():
            result = collision_audit(rows, feature_rows, selected)
            collision_results[family] = result
            aggregate[family]["layouts"] += 1
            aggregate[family]["deterministic"] += int(
                bool(result["deterministic_on_wall"]))
            aggregate[family]["mixed"] += int(
                not bool(result["deterministic_on_wall"]))
        labeled_collision_results = {}
        for family, selected in families.items():
            result = collision_audit(
                labeled, feature_rows[:len(labeled)], selected)
            labeled_collision_results[family] = result
            labeled_aggregate[family]["layouts"] += 1
            labeled_aggregate[family]["deterministic"] += int(
                bool(result["deterministic_on_wall"]))
            labeled_aggregate[family]["mixed"] += int(
                not bool(result["deterministic_on_wall"]))
        mode_collision_results = {}
        for family, selected in families.items():
            result = collision_audit(
                rows, feature_rows, selected, context_fields=("mode",))
            mode_collision_results[family] = result
            mode_aggregate[family]["layouts"] += 1
            mode_aggregate[family]["deterministic"] += int(
                bool(result["deterministic_on_wall"]))
            mode_aggregate[family]["mixed"] += int(
                not bool(result["deterministic_on_wall"]))
        labeled_mode_collision_results = {}
        for family, selected in families.items():
            result = collision_audit(
                labeled, feature_rows[:len(labeled)], selected,
                context_fields=("mode",))
            labeled_mode_collision_results[family] = result
            labeled_mode_aggregate[family]["layouts"] += 1
            labeled_mode_aggregate[family]["deterministic"] += int(
                bool(result["deterministic_on_wall"]))
            labeled_mode_aggregate[family]["mixed"] += int(
                not bool(result["deterministic_on_wall"]))

        pair_results = {}
        for family in (
                "bounded_mixed_width_gp",
                "p5_w04_local_gp",
                "p5_w04_local_state",
                "p5_w04_full_gp",
                "p5_w04_full_gp_and_prefix",
                "p5_w04_full_group_state"):
            result = exact_pair_supports(
                rows, feature_rows, families[family])
            pair_results[family] = result
            pair_aggregate[family]["layouts"] += 1
            pair_aggregate[family]["layouts_with_pair_support"] += int(
                int(result["exact_pair_pattern_supports"]) > 0)
            pair_aggregate[family]["pair_pattern_supports"] += int(
                result["exact_pair_pattern_supports"])
            pair_aggregate[family]["pair_signal_supports"] += int(
                result["exact_pair_signal_supports"])

        minimum_results = {}
        if layout_name == "patent":
            for family, maximum in (
                    ("bounded_mixed_width_gp", 4),
                    ("p5_w04_local_state", 4),
                    ("p5_w04_full_gp", 8)):
                result = minimum_arbitrary_support(
                    rows, feature_rows, families[family], maximum=maximum)
                minimum_results[family] = result
                minimum = result["minimum_support"]
                minimum_aggregate[family]["layouts"] += 1
                minimum_aggregate[family][
                    (f"no_support_through_{result['maximum_width_searched']}"
                     if minimum is None else f"minimum_{minimum}")
                ] += 1

        layouts.append({
            "layout": layout_name,
            "axis": axis,
            "collision_families": collision_results,
            "labeled_collision_families": labeled_collision_results,
            "mode_conditioned_collision_families": mode_collision_results,
            "labeled_mode_conditioned_collision_families": (
                labeled_mode_collision_results
            ),
            "pair_support_families": pair_results,
            "minimum_support_families": minimum_results,
        })

    report = {
        "experiment": "h1484_x2_wf_state_determinism",
        "status": "BOUNDED_RETAINED_STATE_AUDIT",
        "hardware_policy": (
            "cached_h1472_and_prior_anchor_labels_only; h1476 supplies "
            "software function values; no_x87_execution"
        ),
        "labeled_rows": len(labeled),
        "disjoint_function_rows": len(disjoint),
        "combined_rows": len(rows),
        "tree_layouts": len(layouts),
        "collision_aggregate": {
            family: dict(counts) for family, counts in sorted(aggregate.items())
        },
        "labeled_collision_aggregate": {
            family: dict(counts)
            for family, counts in sorted(labeled_aggregate.items())
        },
        "mode_conditioned_collision_aggregate": {
            family: dict(counts)
            for family, counts in sorted(mode_aggregate.items())
        },
        "labeled_mode_conditioned_collision_aggregate": {
            family: dict(counts)
            for family, counts in sorted(labeled_mode_aggregate.items())
        },
        "pair_support_aggregate": {
            family: dict(counts)
            for family, counts in sorted(pair_aggregate.items())
        },
        "minimum_support_aggregate": {
            family: dict(counts)
            for family, counts in sorted(minimum_aggregate.items())
        },
        "layout_results": layouts,
        "claim_boundary": (
            "A mixed full-vector signature is an exact impossibility witness "
            "for that reconstructed layout and state family. Collision-free "
            "or pair-supported finite rows do not prove a general identity, "
            "a physical layout, or the R1475 selector."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1472_score": digest(args.h1472_score),
            "h1476_bank": digest(args.h1476_bank),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "layouts": len(layouts),
        "collision_aggregate": report["collision_aggregate"],
        "labeled_collision_aggregate": report["labeled_collision_aggregate"],
        "mode_conditioned_collision_aggregate": (
            report["mode_conditioned_collision_aggregate"]
        ),
        "labeled_mode_conditioned_collision_aggregate": (
            report["labeled_mode_conditioned_collision_aggregate"]
        ),
        "pair_support_aggregate": report["pair_support_aggregate"],
        "minimum_support_aggregate": report["minimum_support_aggregate"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
