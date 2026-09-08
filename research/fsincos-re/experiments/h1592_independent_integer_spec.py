#!/usr/bin/env python3
"""Independent dyadic-integer replay of a *proposed* direct-cosine schedule.

This specification is not a silicon model. It shares documented constants and
the hypothesized operation sequence with the C model, but no arithmetic code,
fixed accumulator, multiplier topology, terminal selector, or trace parser.
Python integers represent exact signed numerators times powers of two. Fraction
is used only by independent tests, never by the production arithmetic.

The audit compiles C only as an external comparator. No hardware is executed.
Terminal CHOP67(L+R) is an explicit ordinary-arithmetic hypothesis, not an
attempt to translate the empirical R59/R96 terminal replacement.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")


@dataclass(frozen=True)
class Value:
    """Exact signed dyadic n*2**e; rh is numerical last-round direction."""
    n: int
    e: int
    rh: int = 0

    def record(self) -> dict:
        return {"sign": int(self.n < 0), "sig_hex": f"{abs(self.n):x}",
                "e2": self.e, "round_history": self.rh}

    def fraction(self) -> Fraction:
        return Fraction(self.n << self.e) if self.e >= 0 else Fraction(self.n, 1 << -self.e)


def exact_add(a: Value, b: Value) -> Value:
    e = min(a.e, b.e)
    return Value((a.n << (a.e-e)) + (b.n << (b.e-e)), e)


def exact_mul(a: Value, b: Value) -> Value:
    return Value(a.n*b.n, a.e+b.e)


def quantize(x: Value, bits: int, mode: str = "rn") -> Value:
    """Round to normalized bits-significand, unbounded-exponent dyadics.

    mode chop/rz truncates magnitude; away rounds magnitude upward; odd jams
    the low retained bit. Signed up/down are ru/rd. rn means ties-to-even.
    No floating-point arithmetic, bounded word, or C helper is involved.
    """
    if bits < 2 or mode not in ("rn", "chop", "rz", "away", "odd", "ru", "rd"):
        raise ValueError((bits, mode))
    if not x.n:
        return Value(0, 0)
    sign = -1 if x.n < 0 else 1
    magnitude = abs(x.n)
    shift = magnitude.bit_length()-bits
    if shift <= 0:
        return Value(sign*(magnitude << -shift), x.e+shift)
    units, rem = divmod(magnitude, 1 << shift)
    increment = False
    if rem:
        if mode == "rn":
            comparison = 2*rem-(1 << shift)
            increment = comparison > 0 or (comparison == 0 and units % 2 == 1)
        elif mode == "odd":
            increment = units % 2 == 0
        elif mode == "away" or (mode == "ru" and sign > 0) or (mode == "rd" and sign < 0):
            increment = True
    units += increment
    history = sign*(1 if increment else -1) if rem else 0
    if units == 1 << bits:
        units >>= 1
        shift += 1
    return Value(sign*units, x.e+shift, history)


def add(a: Value, b: Value, bits: int, mode: str = "rn") -> Value:
    return quantize(exact_add(a, b), bits, mode)


def mul(a: Value, b: Value, bits: int, mode: str = "chop") -> Value:
    return quantize(exact_mul(a, b), bits, mode)


# Literal 67-bit ROM values. These are shared factual inputs, not independently
# recovered silicon constants; the audit verifies them against the header.
COEFFICIENTS = {
    1: Value(-0x7FFFFFFFFFFFFFFFE, -68),
    2: Value(0x55555555555554277, -71),
    3: Value(-0x5B05B05B05A18A1BA, -76),
    4: Value(0x680680675B559F2CF, -82),
    5: Value(-0x49F93AF61F5349300, -88),
    6: Value(0x47A4F2483514C1AF8, -95),
}


def decode_external(operand: str) -> Value:
    se, sig = (int(word, 16) for word in operand.replace(":", " ").split())
    if not (0 < (se & 0x7FFF) < 0x7FFF) or not (sig & (1 << 63)):
        raise ValueError("audit is finite-normal only")
    return Value(-sig if se >> 15 else sig, (se & 0x7FFF)-16383-63)


def encode_external(value: Value) -> str:
    if not value.n:
        return "0000:0000000000000000"
    assert abs(value.n).bit_length() == 64
    exponent = value.e+63+16383
    assert 0 < exponent < 0x7FFF
    return f"{exponent | (0x8000 if value.n < 0 else 0):04x}:{abs(value.n):016x}"


def replay(operand: str, mode: str = "rn") -> dict[str, Value]:
    """Proposed direct [1/8,1/4) cosine schedule; no empirical correction."""
    magnitude = decode_external(operand)
    magnitude = Value(abs(magnitude.n), magnitude.e)
    if magnitude.e + magnitude.n.bit_length()-1 != -3:
        raise ValueError("direct six-coefficient polynomial domain only")
    stages = {"magnitude": magnitude}
    stages["square"] = mul(magnitude, magnitude, 67)
    stages["fourth"] = mul(stages["square"], stages["square"], 67)
    for arm, numbers in (("negative", (5, 3, 1)), ("positive", (6, 4, 2))):
        c_hi, c_mid, c_lo = (COEFFICIENTS[k] for k in numbers)
        stages[arm+"_mul1"] = mul(stages["fourth"], c_hi, 67)
        stages[arm+"_add1"] = add(c_mid, stages[arm+"_mul1"], 64)
        stages[arm+"_mul2"] = mul(stages["fourth"], stages[arm+"_add1"], 67)
        stages[arm+"_factor"] = add(c_lo, stages[arm+"_mul2"], 64)
    stages["left"] = mul(stages["square"], stages["negative_factor"], 67)
    stages["right"] = mul(stages["fourth"], stages["positive_factor"], 67)
    stages["correction"] = add(stages["left"], stages["right"], 67, "chop")
    stages["result"] = add(Value(1, 0), stages["correction"], 64, mode)
    return stages


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selftest() -> dict:
    """Oracle enumerates neighboring rational representables, not bit cuts."""
    checks = 0
    modes = ("rn", "rd", "ru", "rz", "away", "odd")
    # Enumerating the representable set also covers asymmetric binade gaps.
    for bits in range(2, 7):
        representables = {}
        for exponent in range(-9, 9):
            for sig in range(1 << (bits-1), 1 << bits):
                for sign in (-1, 1):
                    value = Value(sign*sig, exponent)
                    representables[value.fraction()] = value
        keys = sorted(representables)
        import bisect
        for n in range(-511, 512):
            x = Value(n, -4)
            if not n:
                assert quantize(x, bits) == Value(0, 0)
                continue
            actual = x.fraction()
            i = bisect.bisect_left(keys, actual)
            if keys[i] == actual:
                low = high = keys[i]
            else:
                low, high = keys[i-1:i+1]
            toward = low if n > 0 else high
            away = high if n > 0 else low
            for mode in modes:
                if mode == "rd":
                    expected = low
                elif mode == "ru":
                    expected = high
                elif mode == "rz":
                    expected = toward
                elif mode == "away":
                    expected = away
                elif mode == "odd":
                    expected = toward if low == high or abs(representables[toward].n) % 2 else away
                else:
                    expected = min((low, high), key=lambda v: (abs(v-actual), abs(representables[v].n) % 2))
                output = quantize(x, bits, mode)
                assert output.fraction() == expected, (x, bits, mode, output, expected)
                assert output.rh == (expected > actual)-(expected < actual)
                checks += 1
    rng = random.Random(0x1592)
    algebra_checks = 0
    for _ in range(4000):
        a = Value(rng.randrange(-(1 << 140), 1 << 140), rng.randrange(-400, 300))
        b = Value(rng.randrange(-(1 << 140), 1 << 140), rng.randrange(-400, 300))
        assert exact_add(a, b).fraction() == a.fraction()+b.fraction()
        assert exact_mul(a, b).fraction() == a.fraction()*b.fraction()
        for bits in (64, 67, 127):
            for mode in modes:
                out = quantize(a, bits, mode)
                assert abs(out.n).bit_length() == bits
                assert out.rh == (out.fraction() > a.fraction())-(out.fraction() < a.fraction())
                assert quantize(out, bits, mode).fraction() == out.fraction()
        algebra_checks += 1
    return {"enumerated_rational_rounding_checks": checks,
            "wide_signed_exact_algebra_cases": algebra_checks,
            "wide_quantizer_history_idempotence_checks": algebra_checks*18,
            "status": "PASS"}


WIDE = re.compile(r"\b(\w+)=([01]):(-?\d+):([0-9a-fA-F]+)")


def parse_c_dump(stderr: str, operands: list[str]) -> list[dict]:
    """Independent parser retains original records minus noncausal ASLR ra."""
    result = []
    for line in stderr.splitlines():
        if line.startswith("DI_IN "):
            result.append({"operand": " ".join(line.split()[1:3]), "stages": {}, "lines": []})
        if not result:
            continue
        record = result[-1]
        line = re.sub(r" ra=0x[0-9a-f]+", " ra=ASLR_OMITTED", line)
        record["lines"].append(line)
        values = {name: Value(-int(sig, 16) if sign == "1" else int(sig, 16), int(e))
                  for name, sign, e, sig in WIDE.findall(line)}
        if line.startswith("DI_TC "):
            histories = {name: int(value) for name, value in re.findall(r"\brh_(\w+)=(-?\d+)", line)}
            record["exposed_histories"] = {}
            for old, new in (("mag", "magnitude"), ("mul", "square"), ("f4", "fourth"),
                             ("lf", "negative_factor"), ("rf", "positive_factor"),
                             ("left", "left"), ("right", "right")):
                record["stages"][new] = values[old]
                if old in histories:
                    record["exposed_histories"][new] = histories[old]
        elif line.startswith("DI_CORR "):
            record["stages"]["correction"] = values["out"]
        elif line.startswith("DI_FIN "):
            record["stages"]["final_left"] = values["L"]
            record["stages"]["final_right"] = values["R"]
    assert [r["operand"] for r in result] == operands
    for row in result:
        assert set(row["stages"]) == {"magnitude", "square", "fourth", "negative_factor",
            "positive_factor", "left", "right", "correction", "final_left", "final_right"}
    return result


def compare_values(actual: Value, reference: Value) -> dict:
    delta = exact_add(actual, Value(-reference.n, reference.e))
    if delta.e >= reference.e:
        units = Fraction(delta.n << (delta.e-reference.e))
    else:
        units = Fraction(delta.n, 1 << (reference.e-delta.e))
    actual_record = actual.record()
    # Numerical state records must not fabricate an unexposed history as zero.
    del actual_record["round_history"]
    return {"equal": not delta.n, "c_minus_spec_units": str(units),
            "units_e2": reference.e, "c": actual_record, "spec": reference.record()}


def audit(root: Path, output: Path, random_cases: int) -> None:
    if output.exists():
        raise SystemExit(f"refusing existing output directory: {output}")
    output.mkdir(parents=True)
    source = root/"src/fsincos_skylake.c"
    constants_path = root/"src/p5_rom_constants.h"
    parsed_constants = re.findall(r"P5C6_([1-6]) = \{ ([01]), (-?\d+), .*?0x([0-9a-f]+)ull<<64\)\|0x([0-9a-f]+)ull", constants_path.read_text())
    assert len(parsed_constants) == 6
    for i, sign, exponent, hi, lo in parsed_constants:
        n = (int(hi, 16) << 64) | int(lo, 16)
        assert Value(-n if sign == "1" else n, int(exponent)) == COEFFICIENTS[int(i)]
    observed = []
    paths = [root/"tmp/ledger33/current/h1568_expanded_causal_frontier.json",
             root/"tmp/ledger33/current/h1581_equality_off_branch_score.tsv",
             root/"tmp/ledger33/current/h1588_both_equality_taps_score.tsv"]
    provenance_path = root/"tmp/ledger33/current/h1590_signed_threshold_ub_audit/report.json"
    provenance = json.loads(provenance_path.read_text())
    assert digest(source) == provenance["sha256"]["source_after"]
    checked_evidence = {}
    for path in paths:
        relative = str(path.relative_to(root))
        assert digest(path) == provenance["sha256"]["evidence"][relative]
        checked_evidence[relative] = digest(path)
    for path, campaign in zip(paths[1:], ("h1580", "h1587")):
        kit = root/"transfer-tests"/campaign
        opened_path = kit/"OPENED.json"
        relative = str(opened_path.relative_to(root))
        assert digest(opened_path) == provenance["sha256"]["evidence"][relative]
        opened = json.loads(opened_path.read_text())
        assert opened["capture_state"] == "OPENED_ONCE" and opened["repeats"] == 0
        assert digest(path) == opened["sha256"]["score"]
        checked_evidence[relative] = digest(opened_path)
        for filename, expected in opened["sha256"]["raw_captures"].items():
            raw = kit/"hardware-output"/filename
            assert digest(raw) == expected
            checked_evidence[str(raw.relative_to(root))] = expected
    for row in json.loads(paths[0].read_text())["rows"]:
        if row["source"] == "h1378":
            observed.append({"source": "h1378", "mode": row["mode"], "operand": row["operand"], "hardware": row["hardware"]})
    historical_path = root/"tmp/ledger33/current/h1378_x67y64_attached_noledger_misses.tsv"
    relative = str(historical_path.relative_to(root))
    assert digest(historical_path) == provenance["sha256"]["evidence"][relative]
    checked_evidence[relative] = digest(historical_path)
    historical = {}
    for line in historical_path.read_text().splitlines():
        fields = line.split("\t")
        assert len(fields) == 7 and fields[1] == "cos"
        output_fields = fields[6].split()
        assert output_fields[0] == "OK"
        historical[fields[4], fields[2]] = output_fields[1]+":"+output_fields[2]
    assert {(r["operand"], r["mode"]): r["hardware"] for r in observed} == historical
    for path, campaign in zip(paths[1:], ("h1580", "h1587")):
        with path.open() as inp:
            for row in csv.DictReader(inp, delimiter="\t"):
                observed.append({"source": campaign, "mode": row["mode"], "operand": row["operand"], "hardware": row["hardware"]})
    assert len(observed) == 37
    hardware = {(r["operand"], r["mode"]): r for r in observed}
    assert len(hardware) == len(observed)
    named_operands = sorted({r["operand"] for r in observed})
    assert len(named_operands) == 36
    rng = random.Random(0x1592D1AD)
    random_operands = sorted({f"3ffc {rng.randrange(1 << 63, 1 << 64):016x}" for _ in range(random_cases)})
    assert len(random_operands) == random_cases
    assert not set(random_operands) & set(named_operands)
    operands = sorted(named_operands+random_operands)
    configs = {
        "baseline_ledger_off": ["G_ROUND84=0"],
        "ordinary_horner_ledger_off": ["G_ROUND84=0", "G_R1186FADD=0", "G_R1200HISTFADD=0",
            "G_R1231CPAFADD=0", "G_R1237CPAFADD=0", "G_R1378X67Y64=0", "G_R1290FADDWORD=0",
            "G_R1297FADDBOOTH1=0", "G_R1299FADDLOWBIT=0"],
    }
    reports, binary_hashes, raw_hashes = {}, {}, {}
    for config, defines in configs.items():
        binary = (output/config).resolve()
        subprocess.run(["cc", "-O2", "-std=c11", *["-D"+x for x in defines],
                        str(source), "-lm", "-o", str(binary)], check=True, capture_output=True, text=True)
        binary_hashes[config] = digest(binary)
        records = []
        mismatches = Counter()
        history_mismatches = Counter()
        observed_scores = Counter()
        for mode in MODES:
            cp = subprocess.run([str(binary), "--batch", "--fcos-standalone", f"--rc={mode}", "--dump-internals"],
                input="\n".join(operands)+"\n", check=True, capture_output=True, text=True)
            traces = parse_c_dump(cp.stderr, operands)
            outs = []
            for line in cp.stdout.splitlines():
                fields = line.split()
                assert len(fields) >= 3 and fields[0] == "OK"
                outs.append(fields[1]+":"+fields[2])
            assert len(outs) == len(operands)
            raw_path = output/f"{config}_{mode}_trace.txt"
            with raw_path.open("x") as target:
                for trace, endpoint in zip(traces, outs):
                    target.write("\n".join(trace["lines"])+"\nRESULT "+endpoint+"\n")
            raw_hashes[raw_path.name] = digest(raw_path)
            for operand, trace, endpoint in zip(operands, traces, outs):
                spec = replay(operand, mode)
                comparison = {stage: compare_values(trace["stages"][stage], spec[stage])
                              for stage in ("magnitude", "square", "fourth", "negative_factor", "positive_factor", "left", "right", "correction")}
                for stage, entry in comparison.items():
                    if not entry["equal"]:
                        mismatches[stage] += 1
                histories = {stage: {"c": value, "spec": spec[stage].rh, "equal": value == spec[stage].rh}
                             for stage, value in trace["exposed_histories"].items()}
                for stage, entry in histories.items():
                    if not entry["equal"]:
                        history_mismatches[stage] += 1
                # Conditioning only on observed C final inputs checks the
                # architecture-round implementation independently of upstream
                # schedule correctness. It supplies no new hardware label.
                final_replay = encode_external(add(trace["stages"]["final_left"], trace["stages"]["final_right"], 64, mode))
                assert final_replay == endpoint, (config, operand, mode, endpoint, final_replay)
                spec_endpoint = encode_external(spec["result"])
                label = hardware.get((operand, mode))
                if label:
                    observed_scores["c_exact" if endpoint == label["hardware"] else "c_miss"] += 1
                    observed_scores["ordinary_spec_exact" if spec_endpoint == label["hardware"] else "ordinary_spec_miss"] += 1
                if config == "ordinary_horner_ledger_off":
                    assert all(comparison[s]["equal"] for s in comparison if s != "correction"), (operand, comparison)
                # Keep all named rows, and all random discrepancies upstream.
                if operand in named_operands or any(not comparison[s]["equal"] for s in comparison if s != "correction"):
                    records.append({"operand": operand, "mode": mode, "hardware_observed": bool(label),
                        "hardware": label["hardware"] if label else None,
                        "source": label["source"] if label else "software_only_no_label",
                        "c_endpoint": endpoint, "ordinary_spec_endpoint": spec_endpoint,
                        "stage_comparison": comparison,
                        "history_comparison": histories,
                        "independent_stages": {k: v.record() for k, v in spec.items()}})
        reports[config] = {"defines": defines, "stage_mismatch_counts_over_all_software_modes": dict(mismatches),
            "history_mismatch_counts_over_all_software_modes": dict(history_mismatches),
            "observed_scores": dict(observed_scores), "records": records,
            "all_final_round_replays_exact": True,
            "tested_operands": len(operands), "tested_mode_rows": 4*len(operands)}
    report = {"experiment": "h1592_independent_integer_spec", "status": "ANALYSIS_ONLY_NOT_SILICON_SOLUTION",
        "selftest": selftest(), "named_operand_count": len(named_operands), "random_software_operands": random_cases,
        "hardware_observed_rows": len(observed), "no_new_hardware": True, "no_inferred_hardware_modes": True,
        "input_evidence_hashes_checked_against_h1590_and_opened_sidecars": True,
        "ordinary_schedule": ["square=CHOP67(x*x)", "fourth=CHOP67(square*square)",
            "N=RN64(C1+CHOP67(fourth*RN64(C3+CHOP67(fourth*C5))))",
            "P=RN64(C2+CHOP67(fourth*RN64(C4+CHOP67(fourth*C6))))",
            "L=CHOP67(square*N)", "R=CHOP67(fourth*P)", "C=CHOP67(L+R)", "result=RC64(1+C)"],
        "claim_boundary": "Independent integer implementation of a hypothesized schedule; no internal silicon observations, no universal selector, no proof of silicon equivalence.",
        "configurations": reports,
        "sha256": {"source": digest(source), "constants": digest(constants_path), "script": digest(Path(__file__)),
            "provenance_anchor_h1590": digest(provenance_path), "evidence": checked_evidence,
            "binaries": binary_hashes, "raw_traces": raw_hashes}}
    with (output/"report.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({config: {k: v for k, v in content.items() if k not in ("records", "defines")}
                      for config, content in reports.items()}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--random-cases", type=int, default=2048)
    args = parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(), sort_keys=True))
    elif args.root and args.output_dir:
        audit(args.root.resolve(), args.output_dir.resolve(), args.random_cases)
    else:
        parser.error("use --selftest or --root/--output-dir")


if __name__ == "__main__":
    main()
