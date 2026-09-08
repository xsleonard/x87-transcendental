#!/usr/bin/env python3
"""Exhaust faithful adjacent rounding choices in the coupled direct graph.

Nondeterministic *per-input reachability*, not a fitted or executable silicon
selector. The shared square and fourth values feed both polynomial arms. All
13 materializations retain the H1592 proposed precision; architectural RC is
fixed. The empirical payload is either omitted or its original numeric value
and scale are frozen. It is never regenerated after an upstream change.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import h1592_independent_integer_spec as spec


Value = spec.Value
NODES = (
    ("square", "mul", "magnitude", "magnitude", 67, "chop"),
    ("fourth", "mul", "square", "square", 67, "chop"),
    ("negative_mul1", "mul", "fourth", "C5", 67, "chop"),
    ("negative_add1", "add", "C3", "negative_mul1", 64, "rn"),
    ("negative_mul2", "mul", "fourth", "negative_add1", 67, "chop"),
    ("negative_factor", "add", "C1", "negative_mul2", 64, "rn"),
    ("positive_mul1", "mul", "fourth", "C6", 67, "chop"),
    ("positive_add1", "add", "C4", "positive_mul1", 64, "rn"),
    ("positive_mul2", "mul", "fourth", "positive_add1", 67, "chop"),
    ("positive_factor", "add", "C2", "positive_mul2", 64, "rn"),
    ("left", "mul", "square", "negative_factor", 67, "chop"),
    ("right", "mul", "fourth", "positive_factor", 67, "chop"),
    ("correction", "add_payload", "left", "right", 67, "chop"),
)
NAMES = tuple(node[0] for node in NODES)
ALL_MASK = (1 << len(NODES))-1


def mask_of(names: tuple[str, ...] | list[str]) -> int:
    return sum(1 << NAMES.index(name) for name in names)


FAMILIES = {
    "all_graph": ALL_MASK,
    "upstream_only_terminal_ordinary": mask_of(list(NAMES[:10])),
    "all_horner_only_square_fourth_terminal_ordinary": mask_of(list(NAMES[2:10])),
    "last_horner_only": mask_of(["negative_factor", "positive_factor"]),
    "terminal_only": mask_of(["left", "right", "correction"]),
    "last_horner_and_terminal": mask_of(["negative_factor", "positive_factor", "left", "right", "correction"]),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(value: Value) -> tuple[int, int]:
    return value.n, value.e


def unpack(record: dict) -> Value:
    n = int(record["sig_hex"], 16)
    return Value(-n if record["sign"] else n, record["e2"], record.get("round_history", 0))


def initial(operand: str) -> dict[str, Value]:
    magnitude = spec.decode_external(operand)
    assert magnitude.n > 0 and magnitude.e+magnitude.n.bit_length()-1 == -3
    return {"magnitude": magnitude, **{f"C{i}": value for i, value in spec.COEFFICIENTS.items()}}


def operation(state: dict[str, Value], node: tuple, payload: Value) -> Value:
    _, kind, a, b, _, _ = node
    if kind == "mul":
        return spec.exact_mul(state[a], state[b])
    result = spec.exact_add(state[a], state[b])
    if kind == "add_payload":
        result = spec.exact_add(result, payload)
    return result


def neighbors(exact: Value, bits: int) -> tuple[Value, ...]:
    lower = spec.quantize(exact, bits, "rd")
    upper = spec.quantize(exact, bits, "ru")
    return (lower,) if key(lower) == key(upper) else (lower, upper)


def enumerate_graph(operand: str, mode: str, payload: Value):
    """Every feasible mask uniquely chooses ordinary/other at each cut."""
    state = initial(operand)

    def visit(index: int, changed_mask: int):
        if index == len(NODES):
            endpoint = spec.encode_external(spec.add(Value(1, 0), state["correction"], 64, mode))
            yield changed_mask, endpoint
            return
        node = NODES[index]
        name, _, _, _, bits, policy = node
        exact = operation(state, node, payload)
        ordinary = spec.quantize(exact, bits, policy)
        choices = neighbors(exact, bits)
        assert key(ordinary) in {key(choice) for choice in choices}
        for chosen in choices:
            state[name] = chosen
            departure = key(chosen) != key(ordinary)
            yield from visit(index+1, changed_mask | (int(departure) << index))
        del state[name]

    yield from visit(0, 0)


def replay_mask(operand: str, mode: str, payload: Value, mask: int) -> dict:
    """Reproducible witness: local default versus other faithful neighbor."""
    state = initial(operand)
    steps = []
    for index, node in enumerate(NODES):
        name, kind, a, b, bits, policy = node
        exact = operation(state, node, payload)
        ordinary = spec.quantize(exact, bits, policy)
        choices = neighbors(exact, bits)
        if mask & (1 << index):
            candidates = [v for v in choices if key(v) != key(ordinary)]
            assert len(candidates) == 1, (name, mask, choices)
            chosen = candidates[0]
        else:
            chosen = ordinary
        steps.append({"node": name, "operation": kind, "input_names": [a, b],
            "precision": bits, "ordinary_policy": policy,
            "exact_input": exact.record(), "ordinary_local_output": ordinary.record(),
            "chosen_output": chosen.record(), "departure": bool(mask & (1 << index)),
            "neighbor": "exact" if len(choices) == 1 else "floor" if key(chosen) == key(choices[0]) else "ceil"})
        state[name] = chosen
    endpoint = spec.encode_external(spec.add(Value(1, 0), state["correction"], 64, mode))
    return {"deviation_mask": mask, "departure_nodes": names_of(mask),
            "endpoint": endpoint, "steps": steps}


def names_of(mask: int) -> list[str]:
    return [name for i, name in enumerate(NAMES) if mask & (1 << i)]


def square_candidates(operand: str) -> dict:
    magnitude = initial(operand)["magnitude"]
    exact = spec.exact_mul(magnitude, magnitude)
    shift = exact.n.bit_length()-67
    assert shift > 0 and exact.n > 0
    lower, remainder = divmod(exact.n, 1 << shift)
    ordinary = spec.quantize(exact, 67, "chop")
    assert ordinary.n == lower and ordinary.e == exact.e+shift
    candidates = {name: spec.quantize(exact, 67, policy).record()
                  for name, policy in (("CHOP67", "chop"), ("RN67", "rn"),
                                       ("JAM67", "odd"), ("AWAY67", "away"))}
    return {"exact_square": exact.record(), "right_shift": shift,
            "discarded_numerator_hex": f"{remainder:x}", "discarded_denominator_power": shift,
            "half_comparison": (2*remainder > 1 << shift)-(2*remainder < 1 << shift),
            "lower_retained_is_odd": bool(lower & 1), "policies": candidates}


def summarize_masks(masks: list[int], allowed: int) -> dict:
    selected = [mask for mask in masks if not mask & ~allowed]
    if not selected:
        return {"reachable": False, "successful_masks": [], "minimum_departures": None,
                "minimum_masks": [], "must_depart_nodes": [], "inclusion_minimal_masks": []}
    minimum = min(mask.bit_count() for mask in selected)
    must = ALL_MASK
    minimal = []
    for mask in sorted(selected, key=lambda m: (m.bit_count(), m)):
        must &= mask
        if not any(previous & mask == previous for previous in minimal):
            minimal.append(mask)
    return {"reachable": True, "successful_masks": selected, "minimum_departures": minimum,
            "minimum_masks": [mask for mask in selected if mask.bit_count() == minimum],
            "must_depart_nodes": names_of(must), "inclusion_minimal_masks": minimal,
            "inclusion_minimal_supports": [names_of(mask) for mask in minimal]}


def selftest() -> dict:
    # An independent exhaustive numerical-direction traversal does not encode
    # ordinary-relative choices, and deliberately preserves exact-cut duplicates.
    comparisons = 0
    samples = ("3ffc 8000000000000000", "3ffc e73ffffd2c52df71", "3ffc f9dfffffa971b4a5")
    for operand in samples:
        for payload in (Value(0, 0), Value(-3, -80)):
            direct = dict(enumerate_graph(operand, "rd", payload))
            assert len(direct) <= 1 << len(NODES)
            brute = {}
            for numeric_directions in range(1 << len(NODES)):
                state = initial(operand)
                mask = 0
                for index, node in enumerate(NODES):
                    name, _, _, _, bits, policy = node
                    exact = operation(state, node, payload)
                    chosen = spec.quantize(exact, bits, "ru" if numeric_directions & (1 << index) else "rd")
                    ordinary = spec.quantize(exact, bits, policy)
                    mask |= int(key(chosen) != key(ordinary)) << index
                    state[name] = chosen
                endpoint = spec.encode_external(spec.add(Value(1, 0), state["correction"], 64, "rd"))
                assert brute.setdefault(mask, endpoint) == endpoint
                comparisons += 1
            assert direct == brute
            for mask in (0, min(direct), max(direct)):
                assert replay_mask(operand, "rd", payload, mask)["endpoint"] == direct[mask]
    return {"status": "PASS", "independent_direction_assignments": comparisons,
            "complete_graph_payload_cases": 6,
            "maximum_binary_assignments_per_case": 1 << len(NODES)}


def checked_rows(root: Path, source_snapshot: Path | None = None) -> tuple[list[dict], dict]:
    report_path = root/"tmp/ledger33/current/h1592_independent_integer_spec_v3/report.json"
    assert digest(report_path) == "9b986fe4baf377104feda7084129314e47d2be92bfa774cbea19592490674ed8"
    report = json.loads(report_path.read_text())
    assert digest(Path(spec.__file__)) == report["sha256"]["script"]
    source_path = source_snapshot or root/"src/fsincos_skylake.c"
    assert digest(source_path) == report["sha256"]["source"]
    evidence = {str(report_path.relative_to(root)): digest(report_path),
                "experiments/h1592_independent_integer_spec.py": digest(Path(spec.__file__))}
    for relative, expected in report["sha256"]["evidence"].items():
        assert digest(root/relative) == expected
        evidence[relative] = expected
    records = report["configurations"]["baseline_ledger_off"]["records"]
    rows = [r for r in records if r["hardware_observed"]]
    assert len(rows) == 37 and len({(r["operand"], r["mode"]) for r in rows}) == 37
    assert Counter(r["source"] for r in rows) == {"h1378": 11, "h1580": 11, "h1587": 15}
    traces = {}
    for mode in spec.MODES:
        raw_path = report_path.parent/f"baseline_ledger_off_{mode}_trace.txt"
        expected = report["sha256"]["raw_traces"][raw_path.name]
        assert digest(raw_path) == expected
        evidence[str(raw_path.relative_to(root))] = expected
        operand = None
        for line in raw_path.read_text().splitlines():
            if line.startswith("DI_IN "):
                operand = " ".join(line.split()[1:3])
                traces[operand, mode] = {}
            elif line.startswith("DI_TC "):
                traces[operand, mode]["tc_payload"] = int(re.search(r"\bpayload=(-?\d+)", line).group(1))
            elif line.startswith("DI_R59 "):
                tokens = dict(re.findall(r"\b(\w+)=(-?[0-9a-f]+)", line))
                traces[operand, mode]["r59"] = tokens
    for row in rows:
        trace = traces[row["operand"], row["mode"]]
        r59 = trace["r59"]
        consumed = int(r59["payload"])
        assert trace["tc_payload"] == consumed, (row["operand"], trace)
        left = unpack(row["stage_comparison"]["left"]["c"])
        right = unpack(row["stage_comparison"]["right"]["c"])
        assert left.n < 0 < right.n
        payload = Value(-consumed, left.e-8)
        signed_sum = spec.exact_add(spec.exact_add(left, right), payload)
        consumed_sum = Value(-int(r59["umag"], 16), int(r59["rscale"]))
        assert spec.exact_add(signed_sum, Value(-consumed_sum.n, consumed_sum.e)).n == 0
        row["frozen_payload"] = payload.record()
        row["consumed_payload_integer"] = consumed
        row["tc_equals_consumed_r59_payload"] = True
    # The e73 excluded-cut claim is compared directly with H1593's immutable
    # independent inverse report, without importing that implementation.
    previous = root/"tmp/ledger33/current/h1593_inverse_rounding_constraints_v3.json"
    assert digest(previous) == "c2d9e1250fd32791d49b937c8aa504980d45622d426b4c0d986afe21158dad37"
    evidence[str(previous.relative_to(root))] = digest(previous)
    return rows, evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-snapshot", type=Path,
        help="optional preserved de04 source after canonical source changes; hash must match H1592")
    args = parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(), sort_keys=True))
        return
    if not args.root or not args.output_dir:
        parser.error("use --selftest or --root/--output-dir")
    root = args.root.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"refusing existing output: {output}")
    source_path = (args.source_snapshot or root/"src/fsincos_skylake.c").resolve()
    rows, evidence = checked_rows(root, source_path)
    checks = selftest()
    output.mkdir(parents=True)
    results = []
    counts = Counter()
    raw_path = output/"all_graph_outcomes.tsv.gz"
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", mtime=0, filename="") as raw:
        raw.write(b"source\tmode\toperand\tpayload\tdeviation_mask\tendpoint\tmatches_observed\n")
        for row in rows:
            variants = {}
            square_record = square_candidates(row["operand"])
            for payload_name, payload in (("omitted", Value(0, 0)), ("frozen_numeric", unpack(row["frozen_payload"]))):
                outcomes = {}
                for mask, endpoint in enumerate_graph(row["operand"], row["mode"], payload):
                    assert mask not in outcomes
                    outcomes[mask] = endpoint
                    raw.write((f"{row['source']}\t{row['mode']}\t{row['operand']}\t{payload_name}\t{mask}\t{endpoint}\t{int(endpoint == row['hardware'])}\n").encode())
                assert 0 in outcomes
                if payload_name == "omitted":
                    assert outcomes[0] == row["ordinary_spec_endpoint"]
                successful = sorted(mask for mask, endpoint in outcomes.items() if endpoint == row["hardware"])
                summaries = {name: summarize_masks(successful, allowed) for name, allowed in FAMILIES.items()}
                witness_masks = sorted({mask for summary in summaries.values() for mask in summary["minimum_masks"]})
                witnesses = {str(mask): replay_mask(row["operand"], row["mode"], payload, mask) for mask in witness_masks}
                assert all(w["endpoint"] == row["hardware"] for w in witnesses.values())
                square_only = {}
                ordinary_square = unpack(square_record["policies"]["CHOP67"])
                for policy, candidate in square_record["policies"].items():
                    mask = int(key(unpack(candidate)) != key(ordinary_square))
                    assert mask in outcomes
                    square_only[policy] = {"deviation_mask": mask, "endpoint": outcomes[mask],
                        "matches_observed": outcomes[mask] == row["hardware"]}
                    counts[payload_name+".fixed_square_only."+policy+(".exact" if outcomes[mask] == row["hardware"] else ".miss")] += 1
                variants[payload_name] = {"payload_signed_dyadic": payload.record(),
                    "graph_path_count": len(outcomes), "distinct_endpoint_count": len(set(outcomes.values())),
                    "endpoint_histogram": dict(Counter(outcomes.values())),
                    "ordinary_schedule_endpoint": outcomes[0], "families": summaries,
                    "fixed_square_only_policies": square_only,
                    "minimum_witnesses": witnesses}
                counts[payload_name+".graph_paths"] += len(outcomes)
                for family, summary in summaries.items():
                    counts[payload_name+"."+family+(".reachable" if summary["reachable"] else ".unreachable")] += 1
                    if summary["reachable"]:
                        counts[payload_name+"."+family+".minimum="+str(summary["minimum_departures"])] += 1
            result = {k: row[k] for k in ("source", "operand", "mode", "hardware", "c_endpoint",
                       "consumed_payload_integer", "tc_equals_consumed_r59_payload")}
            result["variants"] = variants
            result["square_rounding_analysis"] = square_record
            results.append(result)
            print(row["mode"], row["operand"], {k: (v["families"]["all_graph"]["minimum_departures"],
                v["families"]["upstream_only_terminal_ordinary"]["minimum_departures"])
                for k, v in variants.items()}, flush=True)
    e73 = [r for r in results if r["operand"] == "3ffc e73ffffd2c52df71" and r["mode"] == "rd"]
    assert len(e73) == 1
    assert all(not v["families"]["last_horner_only"]["reachable"] for v in e73[0]["variants"].values())
    report = {"experiment": "h1595_coupled_faithful_reachability", "status": "NONDETERMINISTIC_REACHABILITY_NOT_SELECTOR",
        "hardware_execution": "none", "unobserved_labels_inferred": False, "observed_rows": len(rows),
        "observed_operands": len({r["operand"] for r in rows}),
        "source_counts": dict(Counter(r["source"] for r in rows)), "selftest": checks,
        "nodes": [dict(zip(("name", "operation", "left", "right", "precision", "ordinary_policy"), node)) for node in NODES],
        "departure_definition": "chosen output differs numerically from ordinary local rounding of the same exact inputs along that altered path; not a signed ulp tweak relative to the baseline register",
        "faithful_definition": "adjacent numerical floor/ceil normalized p-bit values of each exact local operation; identical exact choices collapse; normalization exponent may change",
        "payload_definition": "omitted or original signed numeric consumed DI_R59 payload at the original left exponent minus eight; DI_TC equality verified; never rederived after upstream changes",
        "shared_dependencies": "one square and one fourth state feed both arms and terminal products on every path",
        "claim_boundary": "per-input existential finite-width reachability only; no common policy, no silicon-equivalence claim, no arbitrary predicates, no hardware-label generalization",
        "summary": dict(counts), "rows": results,
        "fixed_square_policy_boundary": "four operation-wide square policies, all other operations ordinary; finite-bank diagnostics, not promoted candidates; no new operand predicates",
        "sha256": {"script": digest(Path(__file__)), "source": digest(source_path),
            "evidence": evidence, "all_graph_outcomes": digest(raw_path)}}
    with (output/"report.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
