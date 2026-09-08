#!/usr/bin/env python3
"""Reduce the natural X67/Y64 candidate to its only effective input cut.

Inductive significand-width bounds prove every port materialization is an
identity except the Y copy of square consumed by fourth. This proves an
equivalence between numerical programs, NOT either program's silicon truth.
The saved independent H1616 stages also receive a complete finite replay.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import h1616_independent_asymmetric_direct_audit as verified


spec, V, rounding = verified.spec, verified.V, verified.independent.internal_round
PARENT = "tmp/ledger33/current/h1616_independent_asymmetric_direct_audit"
LOCKS = {
    PARENT+"/report.json": "51f70688d18c6fcc0aa524b9cbf8da9f631f5ea4a86079d7397173b1fd77e3c4",
    "experiments/h1616_independent_asymmetric_direct_audit.py":
        "407883c2e4e25c55ab66a41f4e1d1b3960ea5b3ac1fe42f8acecd29930944d6e",
}


def significant_bits(value: V) -> int:
    n = abs(value.n)
    return 0 if not n else (n//(n & -n)).bit_length()


def simplified_graph(operand: str) -> dict[str, V]:
    """Original ordinary split graph, with only S*CHOP64(S) at fourth."""
    x = spec.decode_external(operand)
    assert x.n > 0 and x.e+x.n.bit_length()-1 == -3
    def mul(a, b):
        return rounding(spec.exact_mul(a, b), 67, 0)
    def add(a, b):
        return rounding(spec.exact_add(a, b), 64, 1)
    c = spec.COEFFICIENTS
    square = mul(x, x)
    fourth = mul(square, rounding(square, 64, 0))
    n1 = mul(fourth, c[5])
    na = add(c[3], n1)
    n2 = mul(fourth, na)
    negative = add(c[1], n2)
    p1 = mul(fourth, c[6])
    pa = add(c[4], p1)
    p2 = mul(fourth, pa)
    positive = add(c[2], p2)
    left, right = mul(square, negative), mul(fourth, positive)
    correction = rounding(spec.exact_add(left, right), 67, 0)
    return {"square": square, "fourth": fourth, "negative_mul1": n1,
            "negative_add1": na, "negative_mul2": n2, "negative_factor": negative,
            "positive_mul1": p1, "positive_add1": pa, "positive_mul2": p2,
            "positive_factor": positive, "left": left, "right": right, "correction": correction}


def width_certificate() -> dict:
    widths = {"x": 64, **{f"C{i}": significant_bits(value) for i, value in spec.COEFFICIENTS.items()}}
    checks, nonidentity = [], []
    for name, op, left, right, result_bits in verified.independent.OPS:
        if op == "*":
            record = {"node": name, "X_source": left, "Y_source": right,
                      "X_bound": widths[left], "Y_bound": widths[right],
                      "X_chop67_is_identity": widths[left] <= 67,
                      "Y_chop64_is_identity": widths[right] <= 64}
            assert record["X_chop67_is_identity"]
            if not record["Y_chop64_is_identity"]:
                nonidentity.append(name)
            checks.append(record)
        # Each natural materialization returns a normalized value with at
        # most this many significant bits, including exact/zero results.
        widths[name] = result_bits
    assert widths["C5"] == 59 and widths["C6"] == 64
    assert nonidentity == ["fourth"]
    return {"initial_and_inductive_bounds": widths, "multiply_port_checks": checks,
        "only_potentially_nonidentity_input_cut": "fourth.Y=CHOP64(square)",
        "proof": "CHOPp(v)=v whenever v has at most p significant bits. Initial external x has64; native C5/C6 have59/64. Multiply results have<=67 and all Horner-add results<=64. In topological order every X input therefore fits67 and every Y input fits64 except square feeding fourth. Removing only those identity cuts preserves every subsequent exact operation and materialization by induction.",
        "scope": "natural fixed output policies, native coefficients, normalized external64 direct inputs and unbounded-dyadic numerical arithmetic; not arbitrary H1614 policy choices or a hardware correctness theorem"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists(), "refusing existing output directory"
    evidence = dict(LOCKS)
    for relative, expected in evidence.items():
        assert verified.digest(root/relative) == expected
    prior = json.loads((root/PARENT/"report.json").read_text())
    for relative, expected in prior["sha256"]["evidence"].items():
        assert verified.digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    stream_path = PARENT+"/independent_direct_replay.jsonl.gz"
    assert verified.digest(root/stream_path) == prior["sha256"]["independent_replay"]
    evidence[stream_path] = prior["sha256"]["independent_replay"]
    certificate = width_certificate()
    operands = stages_checked = outputs_checked = 0
    with gzip.open(root/stream_path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            stages = simplified_graph(row["operand"])
            assert set(stages) == set(row["stages"])
            for name, value in stages.items():
                assert value.fraction() == verified.independent.from_record(row["stages"][name]).fraction()
                stages_checked += 1
            for observation in row["observations"]:
                predicted, c1, prevalue = verified.final_output(stages["correction"], observation["mode"])
                assert predicted == observation["predicted"] == observation["hardware"]
                assert c1 == observation["predicted_ordinary_C1"]
                assert str(prevalue.fraction()) == observation["prevalue"]
                outputs_checked += 1
            operands += 1
    assert operands == prior["unique_observed_operands"]
    assert stages_checked == 13*operands and outputs_checked == prior["unique_observed_rows"]
    result = {"experiment": "h1617_asymmetric_width_reduction", "status": "NUMERICAL_PROGRAM_EQUIVALENCE_VERIFIED",
        "width_certificate": certificate, "finite_stage_equalities": stages_checked,
        "finite_output_equalities": outputs_checked, "finite_operand_replays": operands,
        "simplified_formula": "S=CHOP67(x*x); F=CHOP67(S*CHOP64(S)); N=RN64(C1+CHOP67(F*RN64(C3+CHOP67(F*C5)))); P=RN64(C2+CHOP67(F*RN64(C4+CHOP67(F*C6)))); C=CHOP67(CHOP67(S*N)+CHOP67(F*P)); Y=RC64(1+C)",
        "claim_boundary": "equivalence of two specified numerical programs plus cached observations, not a proof of silicon behavior, recovered port controls or general FSIN/FCOS emulation",
        "hardware_execution": "none", "selector_promotion": "none",
        "sha256": {"script": verified.digest(Path(__file__)), "evidence": evidence}}
    output.mkdir(parents=True)
    with (output/"report.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("status", "finite_stage_equalities", "finite_output_equalities", "finite_operand_replays")}, sort_keys=True))


if __name__ == "__main__":
    main()
