#!/usr/bin/env python3
"""Put the H1487/H1495 pair ambiguity in canonical swap-local form.

The four surviving compressor layouts are one template under swaps of
first-level PP quartets.  This experiment proves those graph isomorphisms for
arbitrary compressor inputs, proves the exact nine-column dependency cone of
the final propagate bit, and bridges H1495's lower-residue boundary carries to
the resulting local swap defect.

No x87 instruction is executed and no hardware label is opened.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

try:
    import z3
except ImportError as error:
    raise SystemExit("z3-solver 4.15.3.0 is required") from error

from h1400_p5_representation_audit import tree_variants
from h1486_surviving_propagate_class import EXPECTED_SIGNALS


WIDTH = 64
POSITIONS = (45, 46)
EXPECTED_ORDER = (
    "pair_02_14_35_hold2.final.propagate.-18",
    "pair_02_15_34_hold2.final.propagate.-18",
    "pair_03_14_25_hold2.final.propagate.-18",
    "pair_03_15_24_hold2.final.propagate.-18",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bv(value: int):
    return z3.BitVecVal(value & ((1 << WIDTH) - 1), WIDTH)


def csa3(a, b, c):
    return a ^ b ^ c, ((a & b) | (a & c) | (b & c)) << 1


def csa42(values, d_slot: int):
    ordered = list(values)
    distinguished = ordered.pop(d_slot)
    first_sum, first_carry = csa3(*ordered)
    return csa3(distinguished, first_sum, first_carry)


def reduce_tree(inputs, config):
    if config.input_order != "natural" or config.d_slots != (0, 0, 0, 0):
        raise RuntimeError("surviving layout stopped using the canonical lanes")
    level1 = [
        csa42(inputs[4 * index:4 * index + 4], config.d_slots[0])
        for index in range(6)
    ]
    level2 = [
        csa42(level1[left] + level1[right], config.d_slots[1])
        for left, right in config.pairing
    ]
    remaining = [index for index in range(3) if index != config.hold]
    level3 = csa42(
        level2[remaining[0]] + level2[remaining[1]], config.d_slots[2]
    )
    return csa42(level3 + level2[config.hold], config.d_slots[3])


def permute_groups(inputs, swaps):
    groups = [list(inputs[4 * index:4 * index + 4]) for index in range(6)]
    for left, right in swaps:
        groups[left], groups[right] = groups[right], groups[left]
    return [value for group in groups for value in group]


def prop(pair, position: int):
    return z3.Extract(position, position, pair[0] ^ pair[1]) == 1


def boundary_carry(pair, position: int):
    mask = bv((1 << position) - 1)
    lower_sum = (pair[0] & mask) + (pair[1] & mask)
    return z3.UGE(lower_sum, bv(1 << position))


def solve(name: str, bad, constraints=(), timeout_ms: int = 60_000):
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(*constraints, bad)
    status = solver.check()
    result = {"status": str(status)}
    if status == z3.unknown:
        result["reason_unknown"] = solver.reason_unknown()
    if status != z3.unsat:
        raise RuntimeError(f"{name} proof is {status}")
    return result


def tight_witness(pair, inputs, position: int, timeout_ms: int):
    full_mask = ((1 << (position + 1)) - 1) \
        ^ ((1 << (position - 8)) - 1)
    narrow_mask = ((1 << (position + 1)) - 1) \
        ^ ((1 << (position - 7)) - 1)
    full_inputs = [value & bv(full_mask) for value in inputs]
    narrow_inputs = [value & bv(narrow_mask) for value in inputs]
    full = reduce_tree(full_inputs, pair)
    narrow = reduce_tree(narrow_inputs, pair)
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(prop(full, position) != prop(narrow, position))
    status = solver.check()
    result = {"status": str(status)}
    if status == z3.unknown:
        result["reason_unknown"] = solver.reason_unknown()
        raise RuntimeError(f"radius-eight tightness is {status}")
    if status != z3.sat:
        raise RuntimeError(f"radius-eight tightness unexpectedly {status}")
    model = solver.model()
    nonzero = []
    for index, value in enumerate(inputs):
        concrete = model.eval(value, model_completion=True).as_long() & full_mask
        if concrete:
            nonzero.append({"input": index, "value": f"{concrete:016x}"})
    result["nonzero_window_inputs"] = nonzero
    result["full_propagate"] = int(z3.is_true(model.eval(prop(full, position))))
    result["radius7_propagate"] = int(
        z3.is_true(model.eval(prop(narrow, position)))
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1487", type=Path)
    parser.add_argument("h1495", type=Path)
    parser.add_argument("h1486", type=Path)
    parser.add_argument("h1496", type=Path)
    parser.add_argument("h1488_freeze", type=Path)
    parser.add_argument("h1488_manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    h1487 = json.loads(args.h1487.read_text())
    h1495 = json.loads(args.h1495.read_text())
    h1486 = json.loads(args.h1486.read_text())
    h1496 = json.loads(args.h1496.read_text())
    h1488 = json.loads(args.h1488_freeze.read_text())
    with args.h1488_manifest.open(newline="") as source:
        h1488_rows = list(csv.DictReader(source, delimiter="\t"))
    signal_order = tuple(h1487["candidate_signal_order"])
    if signal_order != EXPECTED_ORDER or set(signal_order) != EXPECTED_SIGNALS:
        raise RuntimeError("H1487 signal order changed")
    pair_queries = h1487["queries"]
    if [pair_queries[key]["status"] for key in (
            "layout_0_xor_layout_1", "layout_2_xor_layout_3",
            "layout_0_xor_layout_2")] != ["unsat", "unsat", "sat"]:
        raise RuntimeError("H1487 pair partition changed")
    generic = h1495["proofs"]["generic_qf_bv_lemmas"]
    if any(value["status"] != "unsat" for value in generic.values()):
        raise RuntimeError("H1495 boundary identity changed")

    labeled_patterns = [
        row["candidate_pattern"]
        for row in h1486["survivor_class"]["labeled_patterns"]
    ]
    if len(labeled_patterns) != 28 \
            or any(pattern not in ("0000", "1111")
                   for pattern in labeled_patterns):
        raise RuntimeError("H1486 labeled pair-agreement wall changed")
    fresh_patterns = [
        row["candidate_pattern"] for row in h1496["all_endpoint_visible"]
    ]
    selected_patterns = [
        row["candidate_pattern"] for row in h1496["selected"]
    ]
    if len(fresh_patterns) != 63 or len(selected_patterns) != 8:
        raise RuntimeError("H1496 adversarial wall changed")
    if h1488["capture_state"] != "FROZEN_UNOPENED" \
            or h1488["hardware_execution"] != "none" \
            or h1488["hardware_labels"] != "none" \
            or len(h1488_rows) != 6 \
            or h1488["sha256"]["manifest"] != digest(args.h1488_manifest):
        raise RuntimeError("H1488 freeze state changed")
    for row in h1488_rows:
        defect = row["pair_a_merge"] != row["pair_b_merge"]
        expected_role = "pair_discriminator" if defect else "unanimous_control"
        if row["role"] != expected_role or row["capture_state"] != "FROZEN_UNOPENED":
            raise RuntimeError(f"{row['case_id']}: H1488 role is inconsistent")

    layouts = {name: config for name, _, config in tree_variants()}
    configs = [layouts[name.split(".final.")[0]] for name in signal_order]
    base = configs[0]
    inputs = [z3.BitVec(f"h1498_input_{index:02d}", WIDTH)
              for index in range(24)]
    outputs = [reduce_tree(inputs, config) for config in configs]

    actions = (
        (),
        ((4, 5),),
        ((2, 3),),
        ((2, 3), (4, 5)),
    )
    orbit_proofs = []
    for index, swaps in enumerate(actions):
        transformed = reduce_tree(permute_groups(inputs, swaps), base)
        orbit_proofs.append({
            "layout": signal_order[index].split(".final.")[0],
            "quartet_swaps": [list(pair) for pair in swaps],
            **solve(
                f"layout orbit {index}",
                z3.Or(outputs[index][0] != transformed[0],
                      outputs[index][1] != transformed[1]),
                timeout_ms=args.timeout_ms,
            ),
        })

    locality = []
    tightness = []
    for index, (config, output) in enumerate(zip(configs, outputs)):
        for position in POSITIONS:
            window_mask = ((1 << (position + 1)) - 1) \
                ^ ((1 << (position - 8)) - 1)
            local_output = reduce_tree(
                [value & bv(window_mask) for value in inputs], config
            )
            locality.append({
                "layout": signal_order[index].split(".final.")[0],
                "position": position,
                "input_columns": [position - 8, position],
                **solve(
                    f"layout {index} locality {position}",
                    prop(output, position) != prop(local_output, position),
                    timeout_ms=args.timeout_ms,
                ),
            })
        if index in (0, 2):
            tightness.append({
                "pair": "A" if index == 0 else "B",
                "position": POSITIONS[0],
                **tight_witness(config, inputs, POSITIONS[0], args.timeout_ms),
            })

    sigma_inputs = permute_groups(inputs, ((2, 3),))
    sigma_a = reduce_tree(sigma_inputs, configs[0])
    sigma_b = reduce_tree(sigma_inputs, configs[2])
    swap_defect = []
    for position in POSITIONS:
        defect = z3.Xor(prop(outputs[0], position), prop(outputs[2], position))
        sigma_defect = z3.Xor(prop(sigma_a, position), prop(sigma_b, position))
        equal_middle = [
            inputs[8 + lane] == inputs[12 + lane] for lane in range(4)
        ]
        generic_a = (
            z3.BitVec(f"h1498_generic_a_sum_{position}", WIDTH),
            z3.BitVec(f"h1498_generic_a_carry_{position}", WIDTH),
        )
        generic_b = (
            z3.BitVec(f"h1498_generic_b_sum_{position}", WIDTH),
            z3.BitVec(f"h1498_generic_b_carry_{position}", WIDTH),
        )
        generic_prop_defect = z3.Xor(
            prop(generic_a, position), prop(generic_b, position)
        )
        generic_carry_defect = z3.Xor(
            boundary_carry(generic_a, position),
            boundary_carry(generic_b, position),
        )
        swap_defect.append({
            "position": position,
            "sigma_invariance": solve(
                f"swap-defect invariance {position}", defect != sigma_defect,
                timeout_ms=args.timeout_ms,
            ),
            "zero_when_quartets_equal": solve(
                f"swap-defect equal-quartet zero {position}", defect,
                constraints=equal_middle, timeout_ms=args.timeout_ms,
            ),
            "boundary_carry_bridge": solve(
                f"boundary-carry bridge {position}",
                generic_prop_defect != generic_carry_defect,
                constraints=(
                    generic_a[0] + generic_a[1]
                    == generic_b[0] + generic_b[1],
                ),
                timeout_ms=args.timeout_ms,
            ),
        })

    report = {
        "experiment": "h1498_propagate_swap_locality",
        "status": "EXACT_LOCAL_SWAP_ISOMORPHISM",
        "z3_version": z3.get_version_string(),
        "abstract_input_domain": {
            "inputs": 24,
            "input_width": WIDTH,
            "constraints": "none; arbitrary compressor input words",
        },
        "canonical_template": {
            "layout": signal_order[0].split(".final.")[0],
            "pairing": [list(pair) for pair in base.pairing],
            "held_level2_branch": base.hold,
            "orbit": orbit_proofs,
            "interpretation": (
                "swap PP quartets 2 and 3 to map pair A to pair B; swap "
                "quartets 4 and 5 to map the two spellings within each pair"
            ),
        },
        "normalized_booth_domain_quotient": {
            "tau_4_5_within_pair": {
                "pair_a": pair_queries["layout_0_xor_layout_1"],
                "pair_b": pair_queries["layout_2_xor_layout_3"],
            },
            "sigma_2_3_cross_pair": pair_queries["layout_0_xor_layout_2"],
            "interpretation": (
                "H1487 proves that the quartet-4/5 coordinate swap acts "
                "trivially at columns 45 and 46 on every normalized Booth "
                "product, while the quartet-2/3 swap produces the two "
                "formally distinct surviving functions"
            ),
        },
        "sum_preservation": {
            "status": "INHERITED_EXACT_ALGEBRAIC_PROOF",
            "source": "H1495 CSA3/CSA42/tree composition proof",
            "h1495_status": h1495["status"],
        },
        "locality": {
            "positions": list(POSITIONS),
            "maximum_upward_distance_per_csa42": 2,
            "csa42_levels": 4,
            "exact_input_radius": 8,
            "proofs": locality,
            "radius_eight_is_tight": tightness,
        },
        "swap_defect": {
            "definition": "D_j(x) = F_A,j(x) XOR F_A,j(swap_2_3(x))",
            "equivalent_pair_form": "D_j = F_A,j XOR F_B,j",
            "proofs": swap_defect,
            "interpretation": (
                "the XOR of H1495's two global lower-residue boundary carries "
                "is exactly a local nine-column response to exchanging the "
                "PP8..PP11 and PP12..PP15 first-level quartets"
            ),
        },
        "evidence_reconciliation": {
            "h1486_hardware_labeled_rows": {
                "rows": len(labeled_patterns),
                "pattern_counts": dict(sorted(Counter(labeled_patterns).items())),
                "swap_defect_zero": sum(
                    pattern[0] == pattern[2] for pattern in labeled_patterns
                ),
                "swap_defect_one": sum(
                    pattern[0] != pattern[2] for pattern in labeled_patterns
                ),
            },
            "h1496_fresh_software_rows": {
                "rows": len(fresh_patterns),
                "pattern_counts": dict(sorted(Counter(fresh_patterns).items())),
                "swap_defect_zero": sum(
                    pattern[0] == pattern[2] for pattern in fresh_patterns
                ),
                "swap_defect_one": sum(
                    pattern[0] != pattern[2] for pattern in fresh_patterns
                ),
                "selected_rows": len(selected_patterns),
                "selected_swap_defect_zero": sum(
                    pattern[0] == pattern[2] for pattern in selected_patterns
                ),
                "selected_swap_defect_one": sum(
                    pattern[0] != pattern[2] for pattern in selected_patterns
                ),
            },
            "h1488_frozen_unopened_rows": {
                "rows": len(h1488_rows),
                "capture_state": h1488["capture_state"],
                "role_counts": dict(sorted(Counter(
                    row["role"] for row in h1488_rows
                ).items())),
                "swap_defect_zero": sum(
                    row["pair_a_merge"] == row["pair_b_merge"]
                    for row in h1488_rows
                ),
                "swap_defect_one": sum(
                    row["pair_a_merge"] != row["pair_b_merge"]
                    for row in h1488_rows
                ),
            },
        },
        "physical_mapping_boundary": (
            "The two functions are now one exact local circuit under a named "
            "coordinate swap. Public topology still does not identify which "
            "middle PP quartet occupies the held branch in Skylake."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1487": digest(args.h1487),
            "h1495": digest(args.h1495),
            "h1486": digest(args.h1486),
            "h1496": digest(args.h1496),
            "h1488_freeze": digest(args.h1488_freeze),
            "h1488_manifest": digest(args.h1488_manifest),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text)
    print(json.dumps({
        "output": str(args.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": report["status"],
        "orbit_unsat": sum(row["status"] == "unsat" for row in orbit_proofs),
        "locality_unsat": sum(row["status"] == "unsat" for row in locality),
        "tightness_sat": sum(row["status"] == "sat" for row in tightness),
        "swap_defect_lemmas": sum(
            proof["status"] == "unsat"
            for row in swap_defect
            for key, proof in row.items() if key != "position"
        ),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
