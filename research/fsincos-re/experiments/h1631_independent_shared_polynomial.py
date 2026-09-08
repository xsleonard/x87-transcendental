#!/usr/bin/env python3
"""Independently verify every H1630 hit with rational arithmetic/reduction.

Only Python standard-library imports. Constants are parsed from the pinned
native ROM header; no producer graph, quantizer, parser or scorer is imported.
This establishes finite replay and numerical program identities, not silicon
correctness for all inputs or a full architectural-status implementation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from pathlib import Path


PARENT = "tmp/ledger33/current/h1630_shared_polynomial_audit/"
LOCKS = {
    PARENT + "report.json": "5dc548a52e2d46749548011b2e4c2fa8ce919d2a7ab618fc4f4c2746fa54bd79",
    "src/p5_rom_constants.h": "2189e0063c913ee4004e09c8b80cb17afb16c95715ea579854e152088bbfce97",
    "src/fsincos_skylake.c": "0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b",
}
M66 = 0x3243F6A8885A308D3
COEFFICIENTS = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def power2(e):
    return Fraction(1 << e) if e >= 0 else Fraction(1, 1 << -e)


def top(value):
    assert value > 0 and not value.denominator & (value.denominator - 1)
    return value.numerator.bit_length() - value.denominator.bit_length()


def round_exact(value, bits, policy):
    if not value:
        return value, 0
    unit = power2(top(abs(value)) - bits + 1)
    scaled = abs(value) / unit
    q, rem = divmod(scaled.numerator, scaled.denominator)
    inc = int((policy == "away" and rem != 0) or (policy == "rn" and (
        rem * 2 > scaled.denominator or (rem * 2 == scaled.denominator and q % 2 == 1))))
    return (-1 if value < 0 else 1) * (q + inc) * unit, inc


def precision(value):
    n = abs(value.numerator)
    return 0 if not n else (n // (n & -n)).bit_length()


def M(x, y):
    a, _ = round_exact(x, 67, "chop")
    b, _ = round_exact(y, 64, "chop")
    return round_exact(a * b, 67, "chop")[0]


def A(x, y):
    return round_exact(x + y, 64, "rn")[0]


@lru_cache(maxsize=None)
def graph(x, cosine):
    c = COEFFICIENTS["C" if cosine else "S"]
    square = M(x, x)
    fourth = M(square, square)
    negative = A(c[1], M(fourth, A(c[3], M(fourth, c[5]))))
    positive = A(c[2], M(fourth, A(c[4], M(fourth, c[6]))))
    left, right = M(square, negative), M(fourth, positive)
    if cosine:
        correction = round_exact(left + right, 67, "chop")[0]
        pre = 1 + correction
    else:
        polynomial = A(left, right)
        pre = x + M(x, polynomial)
    assert pre > 0
    return pre


def decode_meta(meta):
    sign, e, word = meta["magnitude"].split(":")
    assert sign == "0"
    value = int(word, 16) * power2(int(e))
    assert precision(value) == meta["precision"] <= 64
    assert top(value) == meta["top"] and -32 <= top(value) <= -3
    return value


def external_reduction(operand, instruction, meta, magnitude):
    se, sig = (int(w, 16) for w in operand.split())
    e, sign = (se & 0x7fff) - 16383, se >> 15
    phase = int(instruction == "fcos")
    if e < -1 or (e == -1 and sig < 0xc90fdaa22168c234):
        reduced, residual_sign, signed_n = False, sign, phase
        expected = sig * power2(e - 63)
    else:
        assert -1 <= e <= 62
        dividend = sig << (e + 2)
        q, rem = divmod(dividend, M66)
        assert 2 * rem != M66
        q += int(2 * rem > M66)
        d = dividend - q * M66
        assert abs(d) < 1 << 63
        expected = abs(d) * power2(-65)
        residual_sign = int(d < 0) ^ sign
        signed_n = (-q if sign else q) + phase
        reduced = True
        assert precision(expected) <= 63
    cosine = signed_n & 1
    negative = ((signed_n >> 1) & 1) ^ (0 if cosine else residual_sign)
    assert magnitude == expected
    assert (meta["cosine"], meta["residual_sign"], meta["negative"]) == (cosine, residual_sign, negative)
    return reduced


def final(pre, negative, mode):
    policy = "rn" if mode == "rn" else "away" if (mode == "rd" and negative) or (mode == "ru" and not negative) else "chop"
    value, c1 = round_exact(pre, 64, policy)
    exponent = top(value)
    sig = value / power2(exponent - 63)
    assert sig.denominator == 1 and 1 << 63 <= sig < 1 << 64
    se = exponent + 16383 + (0x8000 if negative else 0)
    return f"{se:04x}:{int(sig):016x}", c1


def raw(line, status):
    words = line.lower().split()
    if words[0] == "c2":
        assert not status or (len(words) == 3 and words[1] == "sw" and int(words[2], 16) & 0x400)
        return "C2", int(words[2], 16) if status else None
    assert len(words) == (5 if status else 3) and words[0] == "ok"
    assert len(words[1]) == 4 and len(words[2]) == 16
    result = f"{int(words[1],16):04x}:{int(words[2],16):016x}"
    sw = None
    if status:
        assert words[3] == "sw"; sw = int(words[4], 16)
        if sw & 0x400:
            result = "C2"
    return result, sw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists()
    for name, expected in LOCKS.items():
        assert digest(root / name) == expected
    report = json.loads((root / PARENT / "report.json").read_text())
    prepared = json.loads((root / PARENT / "prepared.json").read_text())
    assert digest(root / PARENT / "prepared.json") == report["sha256"]["prepared"]
    for name, expected in report["sha256"]["evidence"].items():
        assert digest(root / name) == expected, name
    for kind, index, sign, exponent, hi, lo in re.findall(
        r"static const p5c_t P5([SC])6_(\d) = \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull", (root / "src/p5_rom_constants.h").read_text()):
        value = ((int(hi, 16) << 64) | int(lo, 16)) * power2(int(exponent))
        COEFFICIENTS.setdefault(kind, {})[int(index)] = -value if int(sign) else value
    assert set(COEFFICIENTS) == {"S", "C"} and all(set(c) == set(range(1, 7)) for c in COEFFICIENTS.values())
    coefficient_widths = {kind: {str(i): precision(value) for i, value in c.items()} for kind, c in COEFFICIENTS.items()}
    assert coefficient_widths["S"]["5"] == 63 and coefficient_widths["S"]["6"] == 64
    assert coefficient_widths["C"]["5"] == 59 and coefficient_widths["C"]["6"] == 64
    counts, routing, banks = Counter(), Counter(), []
    assert len(report["banks"]) == len(prepared["inventories"]) == 20 and not report["remaining_banks"]
    for bank, inventory in zip(report["banks"], prepared["inventories"]):
        assert bank["bank"] == inventory["tag"]
        directory = root / PARENT / bank["bank"]
        for name, expected in bank["sha256"].items():
            assert digest(directory / name) == expected
        operands = (root / inventory["inputs"]).read_text().splitlines()
        local = Counter()
        for mode, capture in inventory["captures"].items():
            actual = (root / capture).read_text().splitlines()
            with gzip.open(directory / (mode + "_candidate.stdout.gz"), "rt") as stream:
                values = stream.read().splitlines()
            with gzip.open(directory / (mode + "_metadata.jsonl.gz"), "rt") as stream:
                rows = [json.loads(line) for line in stream]
            metadata = {r["index"]: r for r in rows}
            assert len(rows) == len(metadata)
            assert len(operands) == len(values) == len(actual) == inventory["count"]
            for index, (operand, observed, predicted) in enumerate(zip(operands, actual, values)):
                hardware, status = raw(observed, True)
                value, _ = raw(predicted, False)
                assert value == hardware
                meta = metadata.get(index)
                lane = "cosine" if meta and meta["cosine"] else "sine" if meta else "fallback"
                local[lane + "_rows"] += 1
                if meta:
                    magnitude = decode_meta(meta)
                    reduced = external_reduction(operand, inventory["instruction"], meta, magnitude)
                    expected, c1 = final(graph(magnitude, bool(meta["cosine"])), meta["negative"], mode)
                    assert expected == value and c1 == meta["C1"] == (status >> 9) & 1
                    local[lane + "_independent_output_C1_checks"] += 1
                    routing[lane + (".reduced" if reduced else ".direct")] += 1
                    routing[lane + (".negative" if meta["negative"] else ".positive")] += 1
        for lane in ("sine", "cosine", "fallback"):
            assert local[lane + "_rows"] == bank["counts"].get(lane + "_rows", 0)
        counts.update(local)
        banks.append({"bank": bank["bank"], "counts": dict(local)})
        print(bank["bank"], "independent full-graph/reduction pass", dict(local), flush=True)
    assert counts["sine_independent_output_C1_checks"] == 289914 and counts["cosine_independent_output_C1_checks"] == 288378
    certificate = {"status": "NUMERICAL_OPERATOR_EQUIVALENCE_NOT_SILICON_PROOF", "native_coefficient_widths": coefficient_widths,
                   "input_bound": "H1629's grid proof bounds every reachable polynomial residual: direct<=64, reduced<=63 significant bits.",
                   "shared_operator": "M(x,y)=T67(T67(x)*T64(y)); A(x,y)=RN64(x+y)",
                   "only_nonidentity_port_cut": "fourth.Y=T64(square), for BOTH coefficient families",
                   "width_induction": "Product outputs fit67; Horner-add and sine-combination outputs fit64; terminal coefficient inputs S5/S6 fit63/64 and C5/C6 fit59/64. All initial inputs fit64. Thus every port input cut is identity except square on fourth.Y, including sine's final multiply by its RN64 polynomial.",
                   "sine_default_identity": "Under current default sine controls, R86 already implements the unconditional square & ~7 port cut on the normalized67 square; its remaining products are CHOP67 and sums RN64. With history experiments off, the explicit shared-operator sine graph is the same numerical program. Experimental nondefault CLI recipes are outside this claim.",
                   "distinct_terminals": {"cosine": "RC64(1 + T67(left+right))", "sine": "RC64(x + M(x,RN64(left+right)))"},
                   "scope": "Numerical program reasoning plus exhaustive finite replay of these records, not a physical micro-operation recovery, full C formal proof, all-input hardware proof, or full status implementation."}
    result = {"experiment": "h1631_independent_shared_polynomial", "status": "PASS", "counts": dict(counts), "routing": dict(routing),
              "banks": banks, "unique_prevalue_cache_keys": graph.cache_info().currsize, "certificate": certificate,
              "hardware_execution": "none", "private_ledger_access": "none", "canonical_default_or_paper_change": "none",
              "claim_boundary": "All578292 actual polynomial output/C1 appearances independently checked. Fallback is not new operator/status validation. Coefficients are parsed from the pinned shared ROM source, not independently recovered from silicon.",
              "sha256": {"script": digest(Path(__file__)), "evidence": LOCKS}}
    output.mkdir(parents=True)
    with (output / "report.json").open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True); target.write("\n")
    print(json.dumps({key: result[key] for key in ("status", "counts", "routing", "unique_prevalue_cache_keys")}, sort_keys=True))


if __name__ == "__main__":
    main()
