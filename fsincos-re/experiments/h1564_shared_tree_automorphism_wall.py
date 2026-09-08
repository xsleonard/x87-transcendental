#!/usr/bin/env python3
"""Close graph-isomorphic remapping of the H1486 tree against R1263/R1272.

H1531 showed that selecting any H1486 pairing globally regresses three or
four cached hardware rows.  Its conservative claim boundary left open a
"topology-relative remapping" of the older held-branch consumer.  The held
level-2 branch is structurally unique, however: unlike the other two level-2
branches it bypasses level 3 and feeds the final compressor directly.  This
script enumerates every group-level automorphism of the published tree and
proves that all keep that branch and the final node fixed.  It then replays
the complete five-row R1263/R1272 constraint wall and also checks the larger
set of arbitrary same-column single-node retargetings in either polarity.

No x87 instruction or hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import trace_tree


LAYOUTS = (
    "pair_02_14_35_hold2",
    "pair_02_15_34_hold2",
    "pair_03_14_25_hold2",
    "pair_03_15_24_hold2",
)

# These are precisely the union of the cached exact rows changed by at least
# one H1531 topology binary.  The selected value is the required output of the
# existing R1263 equality gate, except d800 where it is the raw R1272 held
# carry (the merge is exact when that carry is zero).
CASES = (
    {
        "name": "f9e_r1263_b2",
        "mode": "rn",
        "operand": "3ffc f9e0000000a5925b",
        "hardware": "3ffe:f86a7d8633772a42",
        "consumer": "R1263",
        "required": 1,
        "threshold": "b2",
    },
    {
        "name": "fcc_r1263_b2",
        "mode": "rn",
        "operand": "3ffc fcc0000003541b35",
        "hardware": "3ffe:f83dc8dae0e301aa",
        "consumer": "R1263",
        "required": 1,
        "threshold": "b2",
    },
    {
        "name": "d800_r1272_merge",
        "mode": "ru",
        "operand": "3ffc d80000000b15da62",
        "hardware": "3ffe:fa5365e8f13f3e9e",
        "consumer": "R1272",
        "required": 0,
        "threshold": "merge",
    },
    {
        "name": "de4_r1263_b1",
        "mode": "ru",
        "operand": "3ffc de4000000ec121bd",
        "hardware": "3ffe:f9fe744b93b2f346",
        "consumer": "R1263",
        "required": 1,
        "threshold": "b1",
    },
    {
        "name": "e740_r1263_b1",
        "mode": "ru",
        "operand": "3ffc e7400000015584c1",
        "hardware": "3ffe:f97ff29661a1e59d",
        "consumer": "R1263",
        "required": 1,
        "threshold": "b1",
    },
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def group_automorphisms() -> list[tuple[int, ...]]:
    """Return automorphisms of the six-leaf published tree at group level."""
    long_pairs = {frozenset((0, 1)), frozenset((2, 3))}
    held_pair = frozenset((4, 5))
    result = []
    for permutation in itertools.permutations(range(6)):
        mapped_long = {
            frozenset((permutation[0], permutation[1])),
            frozenset((permutation[2], permutation[3])),
        }
        mapped_held = frozenset((permutation[4], permutation[5]))
        if mapped_long == long_pairs and mapped_held == held_pair:
            result.append(permutation)
    return result


def cached_h1531_rows(report: dict[str, object]) -> dict[tuple[str, str], str]:
    rows: dict[tuple[str, str], str] = {}
    for layout in report["layouts"]:
        for row in layout["changed_rows"]:
            key = row["mode"], row["op"]
            if row["baseline"] != row["hardware"]:
                raise RuntimeError(f"{key}: H1531 row stopped being baseline-exact")
            prior = rows.setdefault(key, row["hardware"])
            if prior != row["hardware"]:
                raise RuntimeError(f"{key}: inconsistent cached hardware")
    return rows


def replay_cases(model: Path, h1531: dict[str, object]):
    cached = cached_h1531_rows(h1531)
    records = []
    for case in CASES:
        key = case["mode"], case["operand"]
        if cached.get(key) != case["hardware"]:
            raise RuntimeError(f"{case['name']}: H1531 provenance changed")
        values, stderr = run(
            model, case["mode"], [case["operand"]], dump=True)
        if values != [case["hardware"]]:
            raise RuntimeError(f"{case['name']}: baseline stopped matching hardware")
        row = parse_dump(stderr, [case["operand"]])[0]
        shift = int(row["rsh"])
        discarded = int(row["rd3"], 16)
        if case["threshold"] == "b1" and discarded != 1 << shift:
            raise RuntimeError(f"{case['name']}: b1 equality changed")
        if case["threshold"] == "b2" and discarded != 1 << (shift + 1):
            raise RuntimeError(f"{case['name']}: b2 equality changed")
        records.append((case, row))
    return records


def signal_value(case, row, config, node_name: str, vector_index: int,
                 invert: bool = False) -> tuple[int, int, int]:
    nodes, _, final = trace_tree(row, config)
    position = int(row["rsh"]) + 4
    bit = (nodes[node_name][vector_index] >> position) & 1
    if invert:
        bit ^= 1
    kill_position = int(row["rsh"]) + 15
    final_kill = 1 ^ ((final[0] | final[1]) >> kill_position) & 1
    selected = bit if case["consumer"] == "R1272" else bit & final_kill
    return selected, bit, final_kill


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1531", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    h1531 = json.loads(arguments.h1531.read_text())
    if h1531["status"] \
            != "R1272_ORIENTS_D800_BUT_NO_H1486_LAYOUT_SURVIVES_GLOBAL_REPLAY":
        raise RuntimeError("H1531 conclusion changed")
    records = replay_cases(arguments.model, h1531)
    truth = "".join(str(case["required"]) for case, _ in records)
    if truth != "11011":
        raise RuntimeError("shared-tree truth vector changed")

    automorphisms = group_automorphisms()
    if len(automorphisms) != 16:
        raise RuntimeError("published-tree automorphism census changed")
    if any(set((permutation[4], permutation[5])) != {4, 5}
           for permutation in automorphisms):
        raise RuntimeError("an automorphism moved the held branch")

    configs = {name: config for name, _, config in tree_variants()}
    baseline = configs["patent"]
    if baseline.pairing != ((0, 1), (2, 3), (4, 5)) \
            or baseline.hold != 2:
        raise RuntimeError("published topology transcription changed")

    results = []
    for layout_name in ("patent", *LAYOUTS):
        config = configs[layout_name]
        if config.input_order != "natural" \
                or config.correction != "next_row" \
                or config.d_slots != (0, 0, 0, 0) \
                or config.hold != 2:
            raise RuntimeError(f"{layout_name}: topology assumptions changed")

        rows = []
        pattern = ""
        for case, row in records:
            selected, held_carry, final_kill = signal_value(
                case, row, config, "l2_2", 1)
            pattern += str(selected)
            rows.append({
                "name": case["name"],
                "consumer": case["consumer"],
                "mode": case["mode"],
                "operand": case["operand"].replace(" ", ":"),
                "hardware": case["hardware"],
                "required_signal": case["required"],
                "held_carry": held_carry,
                "final_kill": final_kill,
                "selected_signal": selected,
                "exact": selected == case["required"],
            })

        wire_patterns: dict[tuple[str, str], str] = {}
        for invert in (False, True):
            for node_name in (
                    *(f"l1_{index}" for index in range(6)),
                    *(f"l2_{index}" for index in range(3)),
                    "l3_0", "l4_0"):
                for vector_index, vector_name in enumerate(
                        ("sum", "carry", "first_sum", "first_carry")):
                    candidate = ""
                    for case, row in records:
                        selected, _, _ = signal_value(
                            case, row, config, node_name, vector_index, invert)
                        candidate += str(selected)
                    wire_patterns[(
                        ("!" if invert else "") + node_name,
                        vector_name,
                    )] = candidate
        exact_retargets = [
            f"{node}.{vector}"
            for (node, vector), candidate in sorted(wire_patterns.items())
            if candidate == truth
        ]

        flattened = tuple(value for pair in config.pairing for value in pair)
        held_images = {
            tuple(sorted((flattened[permutation[4]],
                          flattened[permutation[5]])))
            for permutation in automorphisms
        }
        if held_images != {tuple(sorted(config.pairing[2]))}:
            raise RuntimeError(f"{layout_name}: held image is not invariant")

        results.append({
            "layout": layout_name,
            "pairing": [list(pair) for pair in config.pairing],
            "held_pp_groups": list(config.pairing[2]),
            "held_pp_rows": [
                f"PP{4 * group}..PP{4 * group + 3}"
                for group in config.pairing[2]
            ],
            "automorphism_distinct_held_images": len(held_images),
            "selected_pattern": pattern,
            "errors": sum(actual != wanted
                          for actual, wanted in zip(pattern, truth)),
            "rows": rows,
            "same_column_node_literals_with_complements": len(wire_patterns),
            "exact_same_column_retargets": exact_retargets,
        })

    if results[0]["selected_pattern"] != truth \
            or "l2_2.carry" not in results[0]["exact_same_column_retargets"] \
            or len(results[0]["exact_same_column_retargets"]) != 3:
        raise RuntimeError("published-tree positive control changed")
    if [item["errors"] for item in results[1:]] != [3, 4, 4, 3]:
        raise RuntimeError("H1486 shared-tree error vector changed")
    if any(item["exact_same_column_retargets"] for item in results[1:]):
        raise RuntimeError("an H1486 same-column wire retarget survived")

    report = {
        "experiment": "h1564_shared_tree_automorphism_wall",
        "status": "NO_H1486_GRAPH_ISOMORPHISM_PRESERVES_R1263_R1272",
        "hardware_execution": "none",
        "hardware_policy": "cached_files_only_no_x87_execution",
        "hardware_constraints": {
            "rows": len(records),
            "truth": truth,
            "r1263_equality_rows": 4,
            "r1272_merge_rows": 1,
            "provenance": "union of cached baseline-exact H1531 changes",
        },
        "graph_automorphisms": {
            "group_level_count": len(automorphisms),
            "permutations": [list(item) for item in automorphisms],
            "held_level2_branch_fixed": True,
            "final_node_fixed": True,
            "reason": (
                "The held level-2 branch is the unique level-2 node that "
                "bypasses level 3 and feeds the final compressor directly."
            ),
        },
        "layouts": results,
        "conclusion": (
            "H1531's failure cannot be repaired by a graph-relative rename: "
            "every topology automorphism preserves the held level-2 carry "
            "and final kill used by R1263/R1272. The four H1486 layouts make "
            "three, four, four, and three errors on the five cached hardware "
            "constraints. A strict superset search over every same-column "
            "tree-node wire and both polarities also has zero H1486 survivor."
        ),
        "claim_boundary": (
            "This rejects a single shared-tree physical interpretation of "
            "the H1486 propagate formulas; it does not falsify those formulas "
            "as finite candidate selectors, nor does it choose pair A or B. "
            "A repair would require a different consumer circuit, a different "
            "tree representation, or a new control observable rather than a "
            "graph isomorphism. No selector is promoted."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(arguments.model),
            "h1531": digest(arguments.h1531),
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output": str(arguments.output),
        "automorphisms": len(automorphisms),
        "truth": truth,
        "h1486_errors": [item["errors"] for item in results[1:]],
        "h1486_exact_retargets": sum(
            len(item["exact_same_column_retargets"])
            for item in results[1:]),
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
