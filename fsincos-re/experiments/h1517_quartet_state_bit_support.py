#!/usr/bin/env python3
"""Find the exact bit support of H1516's quartet-state isomorphism.

H1516 proves that the pair-A/pair-B defect factors through twelve nine-bit
state words: T=S+C for all six first-level quartets, ordered U=S for groups
0--3, and unordered P=S XOR C for groups 4--5.  This experiment first extends
H1516's canonical decoder to arbitrary values of those twelve words and asks
which individual coordinates can affect the defect.  It then asks whether
each retained coordinate has a sensitivity witness in the original domain of
arbitrary first-level redundant pairs.

Each phase uses one shared one-hot miter.  SAT models enumerate sensitive
coordinates; blocking only the selected coordinate preserves the bit-blasted
solver state.  The final UNSAT result proves every unenumerated coordinate
insensitive in one obligation instead of repeating an equivalent UNSAT cone
for each bit.

No x87 instruction or hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

try:
    import z3
except ImportError as error:
    raise SystemExit("z3-solver 4.15.3.0 is required") from error

try:
    import cvc5
except ImportError as error:
    raise SystemExit("cvc5 1.3.1 is required") from error

from h1400_p5_representation_audit import tree_variants
from h1516_minimal_ordered_quartet_state import (
    EXPECTED_A,
    EXPECTED_B,
    GROUPS,
    WIDTH,
    defect,
)


ORDERED = (0, 1, 2, 3)
UNORDERED = (4, 5)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def field_names():
    names = []
    for group in range(GROUPS):
        names.append(f"g{group}.T")
        names.append(f"g{group}.{'U' if group in ORDERED else 'P'}")
    return tuple(names)


def coordinates():
    return tuple(
        (field, bit)
        for field in field_names()
        for bit in range(WIDTH)
    )


def free_state(prefix: str):
    return {
        name: z3.BitVec(f"{prefix}_{name.replace('.', '_')}", WIDTH)
        for name in field_names()
    }


def decode_state(state):
    pairs = []
    for group in range(GROUPS):
        total = state[f"g{group}.T"]
        if group in ORDERED:
            first = state[f"g{group}.U"]
            pairs.append((first, total - first))
        else:
            propagate = state[f"g{group}.P"]
            generate = z3.LShR(total - propagate, 1)
            pairs.append((propagate | generate, generate))
    return pairs


def state_from_pairs(pairs):
    state = {}
    for group, (first, second) in enumerate(pairs):
        state[f"g{group}.T"] = first + second
        if group in ORDERED:
            state[f"g{group}.U"] = first
        else:
            state[f"g{group}.P"] = first ^ second
    return state


def render_state(model, state):
    return {
        name: f"{model.eval(state[name], model_completion=True).as_long():03x}"
        for name in field_names()
    }


def render_pairs(model, pairs):
    return [
        {
            "group": group,
            "sum_word": f"{model.eval(first, model_completion=True).as_long():03x}",
            "carry_word": f"{model.eval(second, model_completion=True).as_long():03x}",
        }
        for group, (first, second) in enumerate(pairs)
    ]


def selector_mask(selectors, coordinate_list, field):
    value = z3.BitVecVal(0, WIDTH)
    for selector, (candidate_field, bit) in zip(selectors, coordinate_list):
        if candidate_field == field:
            value = value | z3.If(
                selector,
                z3.BitVecVal(1 << bit, WIDTH),
                z3.BitVecVal(0, WIDTH),
            )
    return value


def selected_index(model, selectors):
    selected = [
        index for index, selector in enumerate(selectors)
        if z3.is_true(model.eval(selector, model_completion=True))
    ]
    if len(selected) != 1:
        raise RuntimeError(f"one-hot selector produced {len(selected)} choices")
    return selected[0]


def one_hot_constraints(selectors):
    return [
        z3.Or(*selectors),
        *(
            z3.Or(z3.Not(selectors[left]), z3.Not(selectors[right]))
            for left in range(len(selectors))
            for right in range(left + 1, len(selectors))
        ),
    ]


def canonical_blocked_solver(base_constraints, selectors, blocked_indices):
    solver = z3.SolverFor("QF_BV")
    solver.add(*base_constraints)
    solver.add(*(
        z3.Not(selectors[index]) for index in sorted(blocked_indices)
    ))
    return solver


def cvc5_terminal_crosscheck(solver, timeout_ms: int):
    query = solver.to_smt2().replace(
        "(set-info :status unknown)",
        "(set-logic QF_BV)\n(set-info :status unknown)",
        1,
    )
    crosscheck = cvc5.Solver()
    crosscheck.setOption("produce-models", "true")
    crosscheck.setOption("tlimit-per", str(timeout_ms))
    parser = cvc5.InputParser(crosscheck)
    parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, query, "h1517")
    result_text = ""
    while not parser.done():
        command = parser.nextCommand()
        if command.isNull():
            break
        response = command.invoke(crosscheck, parser.getSymbolManager())
        if command.getCommandName() == "check-sat":
            result_text = str(response).strip()
    if not result_text:
        raise RuntimeError("CVC5 parser executed no check-sat command")
    status = result_text.split(" ", 1)[0]
    result = {
        "status": status,
        "reason": result_text,
        "solver": f"cvc5 {cvc5.__version__}",
        "query": query,
        "query_bytes": len(query.encode()),
        "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
    }
    if status == "sat":
        result["declared_model"] = {
            str(term): str(crosscheck.getValue(term))
            for term in parser.getSymbolManager().getDeclaredTerms()
        }
    return result


def cvc5_bv_value(text: str) -> int:
    if text.startswith("#b"):
        return int(text[2:], 2)
    if text.startswith("#x"):
        return int(text[2:], 16)
    match = re.fullmatch(r"\(_ bv([0-9]+) [0-9]+\)", text)
    if match:
        return int(match.group(1))
    raise RuntimeError(f"unrecognized CVC5 bit-vector value {text}")


def cvc5_selected_index(declared_model, prefix: str, indices):
    selected = [
        index for index in indices
        if declared_model.get(f"{prefix}_select_{index}") == "true"
    ]
    if len(selected) != 1:
        raise RuntimeError(
            f"CVC5 one-hot selector produced {len(selected)} choices"
        )
    return selected[0]


def cvc5_extension_witness(declared_model, state, field: str, bit: int):
    return {
        "field": field,
        "bit": bit,
        "solver": f"cvc5 {cvc5.__version__}",
        "state": {
            name: f"{cvc5_bv_value(declared_model[str(state[name])]):03x}"
            for name in field_names()
        },
    }


def cvc5_reachable_witness(declared_model, left_state, right_state,
                           field: str, bit: int):
    return {
        "field": field,
        "bit": bit,
        "solver": f"cvc5 {cvc5.__version__}",
        "left_state": {
            name: f"{cvc5_bv_value(declared_model[str(left_state[name])]):03x}"
            for name in field_names()
        },
        "right_state": {
            name: f"{cvc5_bv_value(declared_model[str(right_state[name])]):03x}"
            for name in field_names()
        },
    }


def canonical_validity_constraints(state):
    constraints = []
    for group in UNORDERED:
        total = state[f"g{group}.T"]
        propagate = state[f"g{group}.P"]
        difference = total - propagate
        generate = z3.LShR(difference, 1)
        constraints.extend((
            z3.Extract(0, 0, difference) == 0,
            (propagate & generate) == 0,
        ))
    return constraints


def enumerate_extension(pair_a, pair_b, timeout_ms: int,
                        crosscheck_timeout_ms: int):
    coordinate_list = coordinates()
    state = free_state("extension")
    selectors = [
        z3.Bool(f"extension_select_{index}")
        for index in range(len(coordinate_list))
    ]
    changed = dict(state)
    for field in field_names():
        changed[field] = state[field] ^ selector_mask(
            selectors, coordinate_list, field
        )
    original = defect(decode_state(state), pair_a, pair_b)
    flipped = defect(decode_state(changed), pair_a, pair_b)

    base_constraints = [
        *one_hot_constraints(selectors),
        original != flipped,
    ]
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(*base_constraints)
    witnesses = {}
    checks = 0
    while True:
        status = solver.check()
        checks += 1
        if status == z3.unknown:
            terminal = canonical_blocked_solver(
                base_constraints, selectors, witnesses
            )
            crosscheck = cvc5_terminal_crosscheck(
                terminal, crosscheck_timeout_ms
            )
            if crosscheck["status"] == "sat":
                index = cvc5_selected_index(
                    crosscheck["declared_model"], "extension",
                    range(len(coordinate_list))
                )
                if index in witnesses:
                    raise RuntimeError("CVC5 repeated a blocked coordinate")
                field, bit = coordinate_list[index]
                witnesses[index] = cvc5_extension_witness(
                    crosscheck["declared_model"], state, field, bit
                )
                solver.add(z3.Not(selectors[index]))
                continue
            if crosscheck["status"] == "unsat":
                return {
                    "status": "unsat",
                    "checks": checks,
                    "witnesses": witnesses,
                    "terminal_solver": crosscheck["solver"],
                    "terminal_query": crosscheck["query"],
                    "terminal_query_bytes": crosscheck["query_bytes"],
                    "terminal_query_sha256": crosscheck["query_sha256"],
                    "z3_terminal_status": "unknown",
                    "z3_reason_unknown": solver.reason_unknown(),
                }
            return {
                "status": "unknown",
                "reason_unknown": (
                    f"z3={solver.reason_unknown()}; "
                    f"{crosscheck['solver']}={crosscheck['reason']}"
                ),
                "checks": checks,
                "enumerated": len(witnesses),
                "enumerated_coordinates": [
                    {
                        "field": coordinate_list[index][0],
                        "bit": coordinate_list[index][1],
                    }
                    for index in sorted(witnesses)
                ],
                "remaining_coordinates": [
                    {"field": field, "bit": bit}
                    for index, (field, bit) in enumerate(coordinate_list)
                    if index not in witnesses
                ],
            }
        if status == z3.unsat:
            terminal = canonical_blocked_solver(
                base_constraints, selectors, witnesses
            )
            terminal_query = terminal.to_smt2()
            return {
                "status": "unsat",
                "checks": checks,
                "witnesses": witnesses,
                "terminal_solver": f"z3 {z3.get_version_string()}",
                "terminal_query": terminal_query,
                "terminal_query_bytes": len(terminal_query.encode()),
                "terminal_query_sha256": hashlib.sha256(
                    terminal_query.encode()
                ).hexdigest(),
                "z3_terminal_status": "unsat",
            }
        model = solver.model()
        index = selected_index(model, selectors)
        field, bit = coordinate_list[index]
        witnesses[index] = {
            "field": field,
            "bit": bit,
            "defect_before": model.eval(
                original, model_completion=True
            ).as_long(),
            "defect_after": model.eval(
                flipped, model_completion=True
            ).as_long(),
            "state": render_state(model, state),
        }
        solver.add(z3.Not(selectors[index]))


def enumerate_reachable(pair_a, pair_b, timeout_ms: int,
                        crosscheck_timeout_ms: int, candidate_indices):
    coordinate_list = coordinates()
    candidate_indices = tuple(candidate_indices)
    candidate_coordinates = tuple(
        coordinate_list[index] for index in candidate_indices
    )
    left_state = free_state("reachable_left")
    right_state = free_state("reachable_right")
    left_pairs = decode_state(left_state)
    right_pairs = decode_state(right_state)
    selectors = [
        z3.Bool(f"reachable_select_{index}")
        for index in candidate_indices
    ]

    base_constraints = [
        *one_hot_constraints(selectors),
        *canonical_validity_constraints(left_state),
        *canonical_validity_constraints(right_state),
    ]
    for field in field_names():
        base_constraints.append(
            (left_state[field] ^ right_state[field])
            == selector_mask(selectors, candidate_coordinates, field)
        )
    left_defect = defect(left_pairs, pair_a, pair_b)
    right_defect = defect(right_pairs, pair_a, pair_b)
    base_constraints.append(left_defect != right_defect)

    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(*base_constraints)

    witnesses = {}
    checks = 0
    while True:
        status = solver.check()
        checks += 1
        if status == z3.unknown:
            blocked_indices = [
                candidate_indices.index(index) for index in witnesses
            ]
            terminal = canonical_blocked_solver(
                base_constraints, selectors, blocked_indices
            )
            crosscheck = cvc5_terminal_crosscheck(
                terminal, crosscheck_timeout_ms
            )
            if crosscheck["status"] == "sat":
                index = cvc5_selected_index(
                    crosscheck["declared_model"], "reachable",
                    candidate_indices
                )
                if index in witnesses:
                    raise RuntimeError("CVC5 repeated a blocked coordinate")
                field, bit = coordinate_list[index]
                witnesses[index] = cvc5_reachable_witness(
                    crosscheck["declared_model"], left_state, right_state,
                    field, bit
                )
                solver.add(z3.Not(selectors[candidate_indices.index(index)]))
                continue
            if crosscheck["status"] == "unsat":
                return {
                    "status": "unsat",
                    "checks": checks,
                    "witnesses": witnesses,
                    "terminal_solver": crosscheck["solver"],
                    "terminal_query": crosscheck["query"],
                    "terminal_query_bytes": crosscheck["query_bytes"],
                    "terminal_query_sha256": crosscheck["query_sha256"],
                    "z3_terminal_status": "unknown",
                    "z3_reason_unknown": solver.reason_unknown(),
                }
            return {
                "status": "unknown",
                "reason_unknown": (
                    f"z3={solver.reason_unknown()}; "
                    f"{crosscheck['solver']}={crosscheck['reason']}"
                ),
                "checks": checks,
                "enumerated": len(witnesses),
                "enumerated_coordinates": [
                    {
                        "field": coordinate_list[index][0],
                        "bit": coordinate_list[index][1],
                    }
                    for index in sorted(witnesses)
                ],
                "remaining_coordinates": [
                    {"field": field, "bit": bit}
                    for index, (field, bit) in enumerate(coordinate_list)
                    if index not in witnesses
                ],
            }
        if status == z3.unsat:
            blocked_indices = [
                candidate_indices.index(index) for index in witnesses
            ]
            terminal = canonical_blocked_solver(
                base_constraints, selectors, blocked_indices
            )
            terminal_query = terminal.to_smt2()
            return {
                "status": "unsat",
                "checks": checks,
                "witnesses": witnesses,
                "terminal_solver": f"z3 {z3.get_version_string()}",
                "terminal_query": terminal_query,
                "terminal_query_bytes": len(terminal_query.encode()),
                "terminal_query_sha256": hashlib.sha256(
                    terminal_query.encode()
                ).hexdigest(),
                "z3_terminal_status": "unsat",
            }
        model = solver.model()
        selector_index = selected_index(model, selectors)
        index = candidate_indices[selector_index]
        field, bit = coordinate_list[index]
        witnesses[index] = {
            "field": field,
            "bit": bit,
            "left_defect": model.eval(
                left_defect, model_completion=True
            ).as_long(),
            "right_defect": model.eval(
                right_defect, model_completion=True
            ).as_long(),
            "left_state": render_state(model, left_state),
            "right_state": render_state(model, right_state),
            "left_pairs": render_pairs(model, left_pairs),
            "right_pairs": render_pairs(model, right_pairs),
        }
        solver.add(z3.Not(selectors[selector_index]))


def query_rows(witnesses):
    return [
        {
            "field": field,
            "bit": bit,
            "status": "sat" if index in witnesses else "unsat",
        }
        for index, (field, bit) in enumerate(coordinates())
    ]


def support(rows):
    return [
        {"field": row["field"], "bit": row["bit"]}
        for row in rows if row["status"] == "sat"
    ]


def support_by_field(rows):
    return {
        field: [
            row["bit"] for row in rows
            if row["field"] == field and row["status"] == "sat"
        ]
        for field in field_names()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1516", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    parser.add_argument("--crosscheck-timeout-ms", type=int, default=60_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")
    if cvc5.__version__ != "1.3.1":
        raise RuntimeError(f"unexpected CVC5 version {cvc5.__version__}")

    source = json.loads(arguments.h1516.read_text())
    if source["status"] != "EXACT_WORD_MINIMAL_ORDERED_QUARTET_STATE" \
            or source["minimal_exact_ordered_subsets"] != [list(ORDERED)]:
        raise RuntimeError("H1516 representation changed")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]

    extension = enumerate_extension(
        pair_a, pair_b, arguments.timeout_ms,
        arguments.crosscheck_timeout_ms
    )
    if extension["status"] != "unsat":
        print(json.dumps({
            "phase": "canonical_extension",
            **extension,
        }, sort_keys=True), flush=True)
        raise RuntimeError("canonical-extension enumeration is incomplete")
    print(json.dumps({
        "phase": "canonical_extension",
        "sensitive_coordinates": len(extension["witnesses"]),
        "solver_checks": extension["checks"],
        "terminal_status": extension["status"],
        "terminal_solver": extension["terminal_solver"],
    }, sort_keys=True), flush=True)

    reachable = enumerate_reachable(
        pair_a, pair_b, arguments.timeout_ms,
        arguments.crosscheck_timeout_ms,
        sorted(extension["witnesses"]),
    )
    if reachable["status"] != "unsat":
        print(json.dumps({
            "phase": "reachable_state",
            **reachable,
        }, sort_keys=True), flush=True)
        raise RuntimeError("reachable-state enumeration is incomplete")
    print(json.dumps({
        "phase": "reachable_state",
        "sensitive_coordinates": len(reachable["witnesses"]),
        "solver_checks": reachable["checks"],
        "terminal_status": reachable["status"],
        "terminal_solver": reachable["terminal_solver"],
    }, sort_keys=True), flush=True)

    query_paths = {
        "canonical_extension": arguments.output.with_name(
            arguments.output.stem + "_extension_terminal.smt2"
        ),
        "reachable_state": arguments.output.with_name(
            arguments.output.stem + "_reachable_terminal.smt2"
        ),
    }
    for path in query_paths.values():
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    query_paths["canonical_extension"].write_text(
        extension["terminal_query"]
    )
    query_paths["reachable_state"].write_text(
        reachable["terminal_query"]
    )

    extension_rows = query_rows(extension["witnesses"])
    reachable_rows = query_rows(reachable["witnesses"])
    extension_support = support(extension_rows)
    reachable_support = support(reachable_rows)
    extension_keys = {(row["field"], row["bit"]) for row in extension_support}
    reachable_keys = {(row["field"], row["bit"]) for row in reachable_support}
    if not reachable_keys.issubset(extension_keys):
        raise RuntimeError("reachable support escaped the canonical extension")

    exact_coordinate_minimal = extension_keys == reachable_keys
    status = (
        "EXACT_COORDINATE_MINIMAL_QUARTET_STATE"
        if exact_coordinate_minimal else
        "EXACT_EXTENSION_SUPPORT_WITH_REACHABILITY_GAP"
    )
    report = {
        "experiment": "h1517_quartet_state_bit_support",
        "status": status,
        "z3_version": z3.get_version_string(),
        "cvc5_version": cvc5.__version__,
        "timeout_ms_per_incremental_check": arguments.timeout_ms,
        "crosscheck_timeout_ms": arguments.crosscheck_timeout_ms,
        "domain": {
            "extension": "arbitrary values of H1516's twelve state words",
            "reachable": "arbitrary first-level redundant quartet pairs",
            "groups": GROUPS,
            "word_width": WIDTH,
            "candidate_coordinates": len(coordinates()),
        },
        "layouts": {"pair_a": EXPECTED_A, "pair_b": EXPECTED_B},
        "ordered_groups": list(ORDERED),
        "unordered_groups": list(UNORDERED),
        "field_order": list(field_names()),
        "canonical_extension_enumeration": {
            "solver_checks": extension["checks"],
            "terminal_status": extension["status"],
            "terminal_solver": extension["terminal_solver"],
            "z3_terminal_status": extension["z3_terminal_status"],
            **({
                "z3_reason_unknown": extension["z3_reason_unknown"],
            } if "z3_reason_unknown" in extension else {}),
            "terminal_query_artifact": query_paths[
                "canonical_extension"
            ].name,
            "terminal_query_bytes": extension["terminal_query_bytes"],
            "terminal_query_sha256": extension[
                "terminal_query_sha256"
            ],
        },
        "reachable_state_enumeration": {
            "solver_checks": reachable["checks"],
            "terminal_status": reachable["status"],
            "terminal_solver": reachable["terminal_solver"],
            "z3_terminal_status": reachable["z3_terminal_status"],
            **({
                "z3_reason_unknown": reachable["z3_reason_unknown"],
            } if "z3_reason_unknown" in reachable else {}),
            "terminal_query_artifact": query_paths[
                "reachable_state"
            ].name,
            "terminal_query_bytes": reachable["terminal_query_bytes"],
            "terminal_query_sha256": reachable[
                "terminal_query_sha256"
            ],
        },
        "canonical_extension_queries": extension_rows,
        "reachable_state_queries": reachable_rows,
        "canonical_extension_support": extension_support,
        "reachable_state_support": reachable_support,
        "canonical_extension_support_by_field": support_by_field(extension_rows),
        "reachable_state_support_by_field": support_by_field(reachable_rows),
        "support_counts": {
            "canonical_extension": len(extension_support),
            "reachable_state": len(reachable_support),
            "common": len(extension_keys & reachable_keys),
            "extension_only": len(extension_keys - reachable_keys),
        },
        "proof_shape": (
            "Each phase uses one one-hot coordinate selector. Every SAT model "
            "is checked and its selected coordinate blocked. Arbitrary model "
            "assignments are not serialized in this canonical report. The "
            "terminal UNSAT check proves that no unreported coordinate can "
            "change the defect while all other named coordinates remain "
            "fixed; blockers are sorted before exporting that query."
        ),
        "interpretation": (
            "If extension and reachable support coincide, retaining exactly "
            "the reported coordinates is an exact coordinate-minimal "
            "projection on the original arbitrary-pair domain."
        ),
        "claim_boundary": (
            "This minimizes coordinates inside H1516's named state encoding. "
            "It does not prove a global minimum over all Boolean encodings, "
            "choose the physical Skylake orientation, or validate a selector."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {"h1516": digest(arguments.h1516)},
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": status,
        "support_counts": report["support_counts"],
        "extension_support_by_field": report[
            "canonical_extension_support_by_field"
        ],
        "reachable_support_by_field": report[
            "reachable_state_support_by_field"
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
