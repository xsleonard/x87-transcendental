#!/usr/bin/env python3
"""Certify reachable input widths and independently replay wider cosine data.

No producer arithmetic or parser is imported. Unbounded integer dyadics
evaluate the complete fixed graph. The source-backed width theorem concerns
the specified M66 program, not proof that silicon implements that program.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path


CURRENT = "tmp/ledger33/current/"
WIDE = CURRENT + "h1627_wider_cosine_transfer_v2/"
LOWER = CURRENT + "h1628_targeted_lower_transfer/"
LOCKS = {
    "src/fsincos_skylake.c": "0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b",
    WIDE + "report.json": "4481d624bc46037674ef0c60313c5f2f171ba5f87d65eaa368a42292655db962",
    LOWER + "report.json": "7a66c76cfc3b403173593a602ddcd89707aae5f4d1362082f9c2e61ea4428f3a",
}
M66 = 0x3243F6A8885A308D3
MODES = ("rn", "rd", "ru")
C = {1: (-0x7FFFFFFFFFFFFFFFE, -68), 2: (0x55555555555554277, -71),
     3: (-0x5B05B05B05A18A1BA, -76), 4: (0x680680675B559F2CF, -82),
     5: (-0x49F93AF61F5349300, -88), 6: (0x47A4F2483514C1AF8, -95)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add(a, b):
    scale = min(a[1], b[1])
    return (a[0] << (a[1] - scale)) + (b[0] << (b[1] - scale)), scale


def quantize(a, bits, rounding="chop"):
    n, e = a
    if not n:
        return (0, 0), 0
    negative = n < 0; n = abs(n)
    shift = n.bit_length() - bits
    increment = 0
    if shift <= 0:
        q = n << -shift
    else:
        q, rem = divmod(n, 1 << shift)
        increment = int((rounding == "away" and rem != 0) or (rounding == "rn" and (
            rem * 2 > 1 << shift or (rem * 2 == 1 << shift and q & 1))))
        q += increment
    e += shift
    if q.bit_length() > bits:
        q >>= 1; e += 1
    return (-q if negative else q, e), increment


def mul(a, b):
    return quantize((a[0] * b[0], a[1] + b[1]), 67)[0]


def rnadd(a, b):
    return quantize(add(a, b), 64, "rn")[0]


@lru_cache(maxsize=None)
def prevalue(n, e):
    square = mul((n, e), (n, e))
    fourth = mul(square, quantize(square, 64)[0])
    negative = rnadd(C[1], mul(fourth, rnadd(C[3], mul(fourth, C[5]))))
    positive = rnadd(C[2], mul(fourth, rnadd(C[4], mul(fourth, C[6]))))
    correction = quantize(add(mul(square, negative), mul(fourth, positive)), 67)[0]
    pre = add((1, 0), correction)
    assert pre[0] > 0
    return pre


def width(n):
    n = abs(n)
    return 0 if not n else (n // (n & -n)).bit_length()


def equal(a, b):
    return add(a, (-b[0], b[1]))[0] == 0


def predict(meta, mode):
    sign, exponent, word = meta["magnitude"].split(":")
    assert sign == "0"
    n, e = int(word, 16), int(exponent)
    assert meta["precision"] == width(n) <= 64
    assert meta["top"] == e + n.bit_length() - 1 and -32 <= meta["top"] <= -3
    assert meta["old_scope"] == int(meta["top"] == -3)
    lowbit = (n & -n).bit_length() - 1
    pre = prevalue(n >> lowbit, e + lowbit)
    rounded_mode = "rn" if mode == "rn" else "away" if (mode == "rd" and meta["negative"]) or (mode == "ru" and not meta["negative"]) else "chop"
    (out, scale), c1 = quantize(pre, 64, rounded_mode)
    assert out > 0 and out.bit_length() == 64
    se = scale + 63 + 16383 + (0x8000 if meta["negative"] else 0)
    return f"{se:04x}:{out:016x}", c1


def verify_reduction(operand, instruction, meta):
    se, sig = (int(v, 16) for v in operand.split())
    e, sign = (se & 0x7fff) - 16383, se >> 15
    phase = int(instruction == "fcos")
    if e < -1 or (e == -1 and sig < 0xc90fdaa22168c234):
        magnitude, signed_n, reduced = (sig, e - 63), phase, False
    else:
        assert -1 <= e <= 62
        a = sig << (e + 2)
        q, rem = divmod(a, M66)
        assert 2 * rem != M66
        q += 2 * rem > M66
        d = a - q * M66
        assert abs(d) <= M66 // 2
        magnitude, signed_n, reduced = (abs(d), -65), (-q if sign else q) + phase, True
        assert abs(d) < 1 << 63
        assert width(d) <= meta["top"] + 66 <= 63
    assert signed_n & 1 and ((signed_n >> 1) & 1) == meta["negative"]
    ms, me, mn = meta["magnitude"].split(":")
    assert ms == "0" and equal((int(mn, 16), int(me)), magnitude)
    return "reduced" if reduced else "direct"


def raw(line, status):
    words = line.lower().split()
    if words[0] == "c2":
        assert status and len(words) == 3 and words[1] == "sw" and int(words[2], 16) & 0x400
        return "C2", int(words[2], 16)
    assert words[0] == "ok" and len(words) == (5 if status else 3)
    assert len(words[1]) == 4 and len(words[2]) == 16
    value = f"{int(words[1],16):04x}:{int(words[2],16):016x}"
    sw = None
    if status:
        assert words[3] == "sw"; sw = int(words[4], 16)
        if sw & 0x400:
            value = "C2"
    return value, sw


def certificate():
    assert M66 % 2 == 1 and M66.bit_length() == 66 and M66 // 2 < 1 << 65
    intervals = []
    for top in range(-32, -2):
        lo, hi = 1 << (top + 65), (1 << (top + 66)) - 1
        assert lo.bit_length() == hi.bit_length() == top + 66 <= 63
        intervals.append({"residual_top_exponent": top, "minimum_integer_D": str(lo),
                          "maximum_integer_D": str(hi), "maximum_reduced_significant_bits": top + 66})
    assert width(C[5][0]) == 59 and width(C[6][0]) == 64
    return {"status": "SOURCE_BACKED_NUMERICAL_PROGRAM_THEOREM",
            "premises": ["Finite external significand has at most64 bits.",
                         "For reduction exponents -1..62, A=sig*2^(e+2) and N*M66 are integers at scale2^-65.",
                         "The centered quotient gives integer D=A-N*M66, |D|<=floor(M66/2). M66 is odd, so half ties are impossible.",
                         "sky_reduce_rc/wv_from_rc reconstruct D*2^-65; polynomial dispatch requires 2^-32<=|residual|<2^-2."],
            "deduction": "A reduced polynomial input has 2^33<=|D|<=2^63-1 and hence at most63 significant bits. Direct input has at most64. The >64-bit polynomial-input branch is unreachable in this specified program.",
            "per_binade_integer_bounds": intervals,
            "port_equivalence": "All ordinary product results fit67, all Horner-add results fit64, C5 fits59, C6 fits64, and every reachable initial polynomial input fits64. Every X67 input cut is an identity. Every Y64 input cut is an identity except square feeding fourth. Thus the natural all-port program equals the simplified S*T64(S) program over the whole reachable cosine-polynomial domain, not only binade -3.",
            "scope": "Exact mathematical reduction/dispatch/quantization program backed by pinned C source and independently checked finite C traces. Not formal verification of every C execution, a proof of silicon semantics, or a complete FSIN/FCOS solution."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    for name, expected in LOCKS.items():
        assert digest(root / name) == expected
    wide, lower = (json.loads((root / prefix / "report.json").read_text()) for prefix in (WIDE, LOWER))
    for report in (wide, lower):
        for name, expected in report["sha256"]["evidence"].items():
            assert digest(root / name) == expected, name
    source = (root / "src/fsincos_skylake.c").read_text()
    assert source.count("fsin_operation_class_polynomial(") == 2
    assert "else if (residual_exponent <= -3)" in source and "P5_POLY_MODEL_MIN_EXP = -32" in source
    proof = certificate()
    preparations = json.loads((root / WIDE / "prepared.json").read_text())["inventories"]
    counts = {v: Counter() for v in ("simplified", "all_ports")}
    routing, bins, rows_verified = Counter(), Counter(), 0
    for bank, inventory in zip(wide["complete_banks"], preparations):
        directory = root / WIDE / bank["bank"]
        for name, expected in bank["sha256"].items():
            assert digest(directory / name) == expected
        operands = (root / inventory["inputs"]).read_text().splitlines()
        for mode, capture in inventory["captures"].items():
            actual = (root / capture).read_text().splitlines()
            for variant in counts:
                with gzip.open(directory / f"{variant}_{mode}.metadata.gz", "rt") as stream:
                    metadata_rows = [json.loads(line) for line in stream]
                metadata = {m["index"]: m for m in metadata_rows}
                assert len(metadata) == len(metadata_rows)
                with gzip.open(directory / f"{variant}_{mode}.stdout.gz", "rt") as stream:
                    predicted = stream.read().splitlines()
                assert len(actual) == len(predicted) == len(operands) == inventory["count"]
                for index, (operand, observed, line) in enumerate(zip(operands, actual, predicted)):
                    hardware, status = raw(observed, True)
                    value = "C2" if line == "C2" else raw(line, False)[0]
                    assert value == hardware
                    meta = metadata.get(index)
                    group = "old_scope" if meta and meta["old_scope"] else "extended" if meta else "fallback"
                    counts[variant][group + "_rows"] += 1
                    if meta:
                        independent_value, c1 = predict(meta, mode)
                        assert independent_value == value and c1 == meta["C1"] == (status >> 9) & 1
                        route = verify_reduction(operand, inventory["instruction"], meta)
                        routing[variant + "." + route] += 1
                        bins[variant + "." + str(meta["top"])] += 1
                        rows_verified += 1
                        counts[variant]["independent_output_C1_checks"] += 1
            print(bank["bank"], mode, "independently verified", flush=True)
    for variant, count in counts.items():
        for group in ("old_scope", "extended", "fallback"):
            assert count[group + "_rows"] == wide["counts"][variant][group + "_rows"]
        assert count["independent_output_C1_checks"] == 288378
    lower_counts = Counter()
    inventories = json.loads((root / LOWER / "prepared.json").read_text())["inventories"]
    for bank, inventory in zip(lower["banks"], inventories):
        directory = root / LOWER / bank["bank"]
        for name, expected in bank["sha256"].items():
            assert digest(directory / name) == expected
        expected = []
        for mode in MODES:
            lane = inventory["lanes"][mode]
            operands = (root / lane["inputs"]).read_text().splitlines()
            actual = (root / lane["raw"]).read_text().splitlines()
            assert len(operands) == len(actual)
            expected.extend((mode, i, op, raw(line, False)[0]) for i, (op, line) in enumerate(zip(operands, actual)))
        for variant in counts:
            with gzip.open(directory / f"{variant}_replay.jsonl.gz", "rt") as stream:
                replay = [json.loads(line) for line in stream]
            assert len(replay) == len(expected)
            for row, (mode, index, operand, hardware) in zip(replay, expected):
                assert (row["mode"], row["raw_ordinal"], row["operand"], row["hardware"]) == (mode, index, operand, hardware)
                value, c1 = predict(row["metadata"], mode)
                assert value == hardware == row["candidate"] and c1 == row["metadata"]["C1"]
                assert row["hardware_C1"] is None
                verify_reduction(operand, "fcos", row["metadata"])
                lower_counts[variant] += 1
        print(bank["bank"], "targeted raw bank independently verified", flush=True)
    assert set(lower_counts.values()) == {53380}
    report = {"experiment": "h1629_polynomial_domain_certificate", "status": "PASS", "certificate": proof,
              "wide_counts": {v: dict(c) for v, c in counts.items()}, "routing": dict(routing), "bins": dict(bins),
              "lower_independent_output_checks": dict(lower_counts), "unique_independent_prevalues": prevalue.cache_info().currsize,
              "hardware_execution": "none", "private_ledger_access": "none", "canonical_default_or_paper_change": "none",
              "claim_boundary": "Full integer-graph plus reduction replay on every candidate-hit row of these finite retained banks. Fallback validates neither new arithmetic nor C1. No hardware or universal silicon proof.",
              "sha256": {"script": digest(Path(__file__)), "evidence": LOCKS}}
    output.mkdir(parents=True)
    with (output / "report.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True); target.write("\n")
    print(json.dumps({key: report[key] for key in ("status", "wide_counts", "lower_independent_output_checks", "unique_independent_prevalues", "routing")}, sort_keys=True))


if __name__ == "__main__":
    main()
