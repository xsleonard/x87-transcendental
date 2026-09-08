#!/usr/bin/env python3
"""Exact backwards constraints from cached FCOS labels; no x87 execution.

The architectural inverse is independent of the C emulator.  Intermediate
inverses are explicitly conditional on the exposed C operands and a plain
67-bit chopped terminal subtraction, not a claim about the silicon sequence.
The finite semantic audit tries operation-wide precisions/rounding policies;
it does not invent operand predicates or use unobserved rounding-mode labels.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def power(exponent: int) -> F:
    return F(1 << exponent) if exponent >= 0 else F(1, 1 << -exponent)


def ceil(x: F) -> int:
    return -((-x.numerator) // x.denominator)


def floor(x: F) -> int:
    return x.numerator // x.denominator


def quantize(x: F, precision: int | None, policy: str) -> F:
    """Positive dyadic rounding; JAM means truncate then set sticky LSB."""
    assert x > 0 and x.denominator & (x.denominator - 1) == 0
    if precision is None:
        assert policy == "EXACT"
        return x
    exponent = x.numerator.bit_length() - 1 - (x.denominator.bit_length() - 1)
    unit = power(exponent - precision + 1)
    scaled = x / unit
    q, rem = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * rem
    inc = False
    if policy == "RN":
        inc = twice > scaled.denominator or (twice == scaled.denominator and q & 1)
    elif policy == "RNAWAY":
        inc = twice >= scaled.denominator
    elif policy == "AWAY":
        inc = rem != 0
    elif policy == "JAM":
        inc = rem != 0 and not q & 1
    else:
        assert policy == "CHOP"
    return (q + int(inc)) * unit


@dataclass(frozen=True)
class Interval:
    lo: F
    hi: F
    lo_closed: bool
    hi_closed: bool

    def contains(self, x: F) -> bool:
        return (x > self.lo or self.lo_closed and x == self.lo) and (
            x < self.hi or self.hi_closed and x == self.hi)

    def grid(self, unit: F) -> tuple[int, int]:
        lo = ceil(self.lo / unit) if self.lo_closed else floor(self.lo / unit) + 1
        hi = floor(self.hi / unit) if self.hi_closed else ceil(self.hi / unit) - 1
        return lo, hi

    def minus_from(self, value: F) -> Interval:
        return Interval(value - self.hi, value - self.lo, self.hi_closed, self.lo_closed)

    def shifted(self, value: F) -> Interval:
        return Interval(self.lo + value, self.hi + value, self.lo_closed, self.hi_closed)

    def divided(self, value: F) -> Interval:
        assert value > 0
        return Interval(self.lo / value, self.hi / value, self.lo_closed, self.hi_closed)

    def json(self) -> dict:
        return {"lower": str(self.lo), "upper": str(self.hi),
                "lower_closed": self.lo_closed, "upper_closed": self.hi_closed}


def correction_inverse(significand: int, exponent: int, mode: str) -> Interval:
    """For positive non-binade-edge y=sig*2**exp, invert round(1-c)=y."""
    y, ulp = significand * power(exponent), power(exponent)
    if mode == "rn":
        y_interval = Interval(y - ulp / 2, y + ulp / 2,
                              not significand & 1, not significand & 1)
    elif mode == "ru":
        y_interval = Interval(y - ulp, y, False, True)
    else:
        assert mode in ("rd", "rz")
        y_interval = Interval(y, y + ulp, True, False)
    return y_interval.minus_from(F(1))


def ext_value(value: str) -> tuple[int, int]:
    se, sig = (int(s, 16) for s in value.split(":"))
    assert 0 < se < 0x8000
    assert 1 << 63 < sig < (1 << 64) - 1  # no binade-edge asymmetry here
    return sig, se - 16383 - 63


def wide_values(line: str) -> dict[str, tuple[int, int, int]]:
    return {k: (int(s), int(e), int(v, 16)) for k, s, e, v in
            re.findall(r"(\w+)=([01]):(-?\d+):([0-9a-f]+)", line)}


def as_fraction(value: tuple[int, int, int]) -> F:
    sign, exp, sig = value
    return (-1 if sign else 1) * sig * power(exp)


def tokens(line: str) -> dict[str, str]:
    return dict(re.findall(r"(\w+)=([0-9a-fA-F,-]+)", line))


def replay(model: Path, rows: list[dict]) -> list[dict]:
    traces = {}
    for mode in ("rn", "rd", "ru", "rz"):
        selected = [r for r in rows if r["mode"] == mode]
        command = [str(model), "--batch", "--fcos-standalone", "--rc=" + mode,
                   "--dump-internals"]
        process = subprocess.run(command, input="".join(r["operand"] + "\n" for r in selected),
                                 text=True, capture_output=True, check=True)
        outputs = [":".join(line.split()[1:]) for line in process.stdout.splitlines()]
        assert outputs == [r["baseline"] for r in selected]
        current = None
        for line in process.stderr.splitlines():
            if line.startswith("DI_IN "):
                op = " ".join(line.split()[1:3])
                current = {"raw": []}
                assert (mode, op) not in traces
                traces[mode, op] = current
            if current is None:
                continue
            # A return address is nondeterministic and irrelevant to arithmetic.
            line = re.sub(r" ra=0x[0-9a-f]+", " ra=OMITTED_ASLR", line)
            current["raw"].append(line)
            if line.startswith("DI_TC "):
                current["tc"] = wide_values(line)
            elif line.startswith("DI_R59 "):
                current["r59"] = tokens(line)
            elif line.startswith("DI_CORR "):
                assert "via=r59" in line
                current["correction"] = wide_values(line)["out"]
    assert len(traces) == len(rows)
    return [dict(row, trace=traces[row["mode"], row["operand"]]) for row in rows]


def load_rows(root: Path, model: Path) -> tuple[list[dict], dict]:
    current = root / "tmp/ledger33/current"
    audit_path = current / "h1590_signed_threshold_ub_audit/report.json"
    audit = json.loads(audit_path.read_text())
    assert digest(root / "src/fsincos_skylake.c") == audit["sha256"]["source_after"]
    assert digest(model) == audit["versions"]["after_O2"]["binary_sha256"]
    evidence = {str(audit_path.relative_to(root)): digest(audit_path)}
    miss_path = current / "h1378_x67y64_attached_noledger_misses.tsv"
    assert digest(miss_path) == audit["sha256"]["evidence"][str(miss_path.relative_to(root))]
    rows = []
    for line in miss_path.read_text().splitlines():
        f = line.split()
        assert len(f) == 12 and f[1] == "cos" and f[6] == f[9] == "OK"
        rows.append(dict(source="h1378_observed_misses", mode=f[2], operand=" ".join(f[4:6]),
                         baseline=f[7] + ":" + f[8], hardware=f[10] + ":" + f[11]))
    assert len(rows) == 11 and len({r["operand"] for r in rows}) == 10
    opened_path = root / "transfer-tests/h1587/OPENED.json"
    opened = json.loads(opened_path.read_text())
    assert opened["capture_state"] == "OPENED_ONCE" and opened["repeats"] == 0
    score_path = current / "h1588_both_equality_taps_score.tsv"
    assert digest(score_path) == opened["sha256"]["score"]
    for name, h in opened["sha256"]["raw_captures"].items():
        path = root / "transfer-tests/h1587/hardware-output" / name
        assert digest(path) == h
        evidence[str(path.relative_to(root))] = h
    with score_path.open() as source:
        for r in csv.DictReader(source, delimiter="\t"):
            rows.append({**{k: r[k] for k in ("mode", "operand", "baseline", "hardware")},
                         "source": "h1587_observed", "case_id": r["case_id"],
                         "endpoint": r["endpoint"]})
    assert len(rows) == 26 and len({(r["mode"], r["operand"]) for r in rows}) == 26
    for path in (miss_path, opened_path, score_path):
        evidence[str(path.relative_to(root))] = digest(path)
    return replay(model, rows), evidence


def inverse_row(row: dict) -> tuple[dict, dict]:
    tc, r59 = row["trace"]["tc"], row["trace"]["r59"]
    signed = {k: as_fraction(v) for k, v in tc.items()}
    left, right = -signed["left"], signed["right"]
    assert left > right > 0
    payload = int(r59["payload"]) * power(tc["left"][1] - 8)
    ce = int(r59["ce"])
    U = int(r59["umag"], 16) * power(int(r59["rscale"]))
    assert U == left + payload - right
    exact_left = signed["mul"] * -signed["lf"]
    exact_right = signed["f4"] * signed["rf"]
    assert quantize(exact_left, 67, "CHOP") == left
    assert quantize(exact_right, 67, "CHOP") == right
    c_model = -as_fraction(row["trace"]["correction"])
    c_inverse = correction_inverse(*ext_value(row["hardware"]), row["mode"])
    assert c_inverse.contains(c_model) == (row["hardware"] == row["baseline"])
    retained_lo, retained_hi = c_inverse.grid(power(ce))
    assert 1 << 66 <= retained_lo <= retained_hi < 1 << 67
    # Inverse of CHOP67 over consecutive allowable retained integers.
    u_inverse = Interval(retained_lo * power(ce), (retained_hi + 1) * power(ce), True, False)
    cuts = {}
    for name, observed, fixed, sign, factor, multiplier in (
        ("left", left, right - payload, 1, "lf", "mul"),
        ("right", right, left + payload, -1, "rf", "f4"),
    ):
        permissible = u_inverse.shifted(fixed) if sign == 1 else u_inverse.minus_from(fixed)
        exponent, observed_int = tc[name][1:]
        lo, hi = permissible.grid(power(exponent))
        assert lo <= hi and 1 << 66 <= lo <= hi < 1 << 67
        product_preimage = Interval(lo * power(exponent), (hi + 1) * power(exponent), True, False)
        factor_preimage = product_preimage.divided(abs(signed[multiplier]))
        flo, fhi = factor_preimage.grid(power(tc[factor][1]))
        cuts[name] = {
            "materialized_integer_delta_interval": [lo - observed_int, hi - observed_int],
            "exact_producer_preimage": product_preimage.json(),
            "observed_exact_product_in_preimage": product_preimage.contains(exact_left if name == "left" else exact_right),
            "factor": factor,
            "factor_magnitude_integer_delta_interval": [flo - tc[factor][2], fhi - tc[factor][2]],
            "factor_has_integer_preimage": flo <= fhi,
            "factor_assumption": "other_multiplier_fixed_factor_magnitude_lattice_unchanged",
        }
        # Direct checks of both inside endpoints and the two neighboring grid points.
        for integer, expected in ((lo - 1, False), (lo, True), (hi, True), (hi + 1, False)):
            raw = integer * power(exponent) - fixed if sign == 1 else fixed - integer * power(exponent)
            assert c_inverse.contains(quantize(raw, 67, "CHOP")) == expected
    base_q = floor(U / power(ce))
    record = {**{k: v for k, v in row.items() if k != "trace"},
              "inverse_assumptions": {
                  "architectural": "positive_non_binade_edge_round64(1_minus_positive_correction)_in_observed_mode",
                  "single_cut": "plain_CHOP67_correction_other_terminal_operand_frozen_numeric_payload_frozen",
                  "product_preimage": "CHOP67_terminal_product_fixed_normalized_binade_and_lattice",
                  "factor_preimage": "one_factor_magnitude_varies_other_multiplier_frozen_factor_lattice_fixed",
                  "not_excluded": "coupled_upstream_changes_that_also_change_payload_scales_or_rounding_sequence"},
              "correction_inverse": c_inverse.json(), "correction_lattice_exponent": ce,
              "allowed_correction_integer_interval": [retained_lo, retained_hi],
              "allowed_delta_from_plain_chop67": [retained_lo - base_q, retained_hi - base_q],
              "current_correction": str(c_model), "plain_chop67_correction": str(quantize(U, 67, "CHOP")),
              "current_correction_is_admissible": c_inverse.contains(c_model),
              "plain_chop67_is_admissible": c_inverse.contains(quantize(U, 67, "CHOP")),
              "plain_chop67_preimage": u_inverse.json(), "single_cut_inverses": cuts,
              "conditional_inputs": {k: list(v) for k, v in tc.items()},
              "trace": row["trace"]["raw"]}
    experiment = dict(inverse=c_inverse, left=exact_left, right=exact_right, payload=payload)
    return record, experiment


def semantic_audit(experiments: list[dict], rows: list[dict]) -> dict:
    # Every schedule is fixed over the entire observed bank: no mode-, operand-,
    # gate-profile-, threshold-, or hardware-label-dependent choice is allowed.
    policies = ("CHOP", "RN", "RNAWAY", "AWAY", "JAM")
    choices = [(p, r) for p in range(64, 73) for r in policies] + [(None, "EXACT")]
    products = {side: [[quantize(e[side], *choice) for e in experiments] for choice in choices]
                for side in ("left", "right")}
    signature_rows = [tuple(r[k] for k in ("mode", "operand")) for r in rows]
    pairs = [
        [("rn", "3ffc f9dffffdf814cc29"), ("rn", "3ffc f9dfffffa971b4a5")],
        [("rd", "3ffc de3ffffc73d9080b"), ("rd", "3ffc e73ffffd2c52df71")],
    ]
    pair_indices = [[signature_rows.index(key) for key in pair] for pair in pairs]
    score_histogram, best, exact, best_count = Counter(), [], [], -1
    pair_counts = [0, 0]
    row_reachable = [set() for _ in rows]
    evaluated = 0
    for use_payload, li, ri in itertools.product((False, True), range(len(choices)), range(len(choices))):
        raw_values = [l - r + (e["payload"] if use_payload else 0) for l, r, e in
                      zip(products["left"][li], products["right"][ri], experiments)]
        for final_choice in choices:
            matches = [e["inverse"].contains(quantize(x, *final_choice)) for x, e in zip(raw_values, experiments)]
            count = sum(matches)
            score_histogram[count] += 1
            schedule = dict(left=choices[li], right=choices[ri], final=final_choice, payload=use_payload)
            if count > best_count:
                best_count, best = count, []
            if count == best_count and len(best) < 12:
                best.append(dict(schedule, missed_rows=[i for i, match in enumerate(matches) if not match]))
            if count == len(rows):
                exact.append(schedule)
            for n, indices in enumerate(pair_indices):
                pair_counts[n] += all(matches[i] for i in indices)
            for i, match in enumerate(matches):
                if match:
                    row_reachable[i].add((use_payload, choices[li][0], choices[ri][0], final_choice[0]))
            evaluated += 1
    return {"enumerated_fixed_schedules": evaluated, "choices_per_operation": len(choices),
            "precision_bits": list(range(64, 73)), "policies": policies,
            "exact_forwarding_included": True,
            "payload_variants": ["omitted", "incumbent_numeric_payload_held_fixed"],
            "correct_rows_histogram": dict(sorted(score_histogram.items())),
            "best_correct_rows": best_count, "best_examples_not_candidates": best,
            "exact_schedules": exact, "collision_pairs": pairs,
            "schedules_exact_on_individual_pairs": pair_counts,
            "each_row_reachable_in_some_fixed_schedule": [bool(s) for s in row_reachable],
            "claim_boundary": "bounded_uniform_terminal_semantics_only_upstream_values_conditioned_on_C_trace_no_control_wall"}


def upstream_audit(root: Path, rows: list[dict], experiments: list[dict]) -> dict:
    """Test fixed last-Horner semantics, not constant signed perturbations.

    These policies are conditional on each operation's exact guard/round/sticky
    bits. The same policy is applied to every row. The payload is either zero
    or numerically frozen, so this does not exclude coupled payload producers.
    """
    import h1592_independent_integer_spec as spec

    source = root / "experiments/h1592_independent_integer_spec.py"
    mapping = {"mul": "square", "f4": "fourth", "lf": "negative_factor",
               "rf": "positive_factor", "mag": "magnitude", "left": "left", "right": "right"}
    raw_negative, raw_positive, squares, fourths = [], [], [], []
    checks = 0
    for row in rows:
        stages = spec.replay(row["operand"], row["mode"])
        for key, stage in mapping.items():
            assert as_fraction(row["trace"]["tc"][key]) == stages[stage].fraction()
            checks += 1
        raw_negative.append(-spec.exact_add(spec.COEFFICIENTS[1], stages["negative_mul2"]).fraction())
        raw_positive.append(spec.exact_add(spec.COEFFICIENTS[2], stages["positive_mul2"]).fraction())
        squares.append(stages["square"].fraction())
        fourths.append(stages["fourth"].fraction())
    policies = ("CHOP", "RN", "RNAWAY", "AWAY", "JAM")
    choices = [(p, r) for p in range(64, 73) for r in policies] + [(None, "EXACT")]
    lefts = [[quantize(q * quantize(a, *choice), 67, "CHOP") for q, a in zip(squares, raw_negative)]
             for choice in choices]
    rights = [[quantize(q * quantize(a, *choice), 67, "CHOP") for q, a in zip(fourths, raw_positive)]
              for choice in choices]
    histogram, best, exact, best_count = Counter(), [], [], -1
    faithful64 = []
    # This permits arbitrary, even label-dependent, floor/ceil choices at both
    # cuts. A row with no satisfying choice excludes *every* faithful64 policy
    # at these two cuts under the explicitly held-fixed surrounding sequence.
    for i, row in enumerate(rows):
        permitted = {}
        producer_deltas = {}
        for name, raw, key in (("negative", raw_negative[i], "lf"),
                               ("positive", raw_positive[i], "rf")):
            observed = abs(as_fraction(row["trace"]["tc"][key]))
            unit = power(row["trace"]["tc"][key][1])
            producer_deltas[name] = [int((quantize(raw, 64, r) - observed) / unit)
                                    for r in ("CHOP", "AWAY")]
        for use_payload in (False, True):
            permitted[str(use_payload)] = []
            for negative, positive in itertools.product(("CHOP", "AWAY"), repeat=2):
                l = quantize(squares[i] * quantize(raw_negative[i], 64, negative), 67, "CHOP")
                r = quantize(fourths[i] * quantize(raw_positive[i], 64, positive), 67, "CHOP")
                correction = quantize(l - r + (experiments[i]["payload"] if use_payload else 0), 67, "CHOP")
                if experiments[i]["inverse"].contains(correction):
                    permitted[str(use_payload)].append([negative, positive])
        faithful64.append({"row_index": i, "operand": row["operand"], "mode": row["mode"],
                           "producer_magnitude_floor_ceil_deltas": producer_deltas,
                           "permitted_by_frozen_payload_present": permitted})
    for use_payload, li, ri in itertools.product((False, True), range(len(choices)), range(len(choices))):
        matches = [e["inverse"].contains(quantize(l - r + (e["payload"] if use_payload else 0), 67, "CHOP"))
                   for l, r, e in zip(lefts[li], rights[ri], experiments)]
        count = sum(matches)
        histogram[count] += 1
        schedule = dict(negative_last_add_magnitude=choices[li], positive_last_add_magnitude=choices[ri],
                        frozen_numeric_payload=use_payload)
        if count > best_count:
            best_count, best = count, []
        if count == best_count and len(best) < 12:
            best.append(dict(schedule, missed_rows=[i for i, match in enumerate(matches) if not match]))
        if count == len(rows):
            exact.append(schedule)
    return {"enumerated_fixed_schedules": sum(histogram.values()),
            "upstream_source_sha256": digest(source), "independent_stage_matches": checks,
            "operations_varied": "both_last_Horner_adds_precision_and_rounding_from_exact_sum",
            "earlier_operations": "independent_spec_square67_fourth67_mul67_add64_RN",
            "downstream": "CHOP67_terminal_products_plain_CHOP67_correction_then_observed_architectural_RC",
            "payload": "omitted_or_current_numeric_value_frozen_not_rederived_after_upstream_changes",
            "precision_bits": list(range(64, 73)), "policies": policies,
            "exact_forwarding_included": True, "correct_rows_histogram": dict(sorted(histogram.items())),
            "best_correct_rows": best_count, "best_examples_not_candidates": best, "exact_schedules": exact,
            "nondeterministic_faithful64_last_adds": faithful64,
            "rows_impossible_for_any_faithful64_choices_both_payload_variants": [
                r["row_index"] for r in faithful64
                if not any(r["permitted_by_frozen_payload_present"].values())],
            "claim_boundary": "only_named_frozen_payload_last_add_family_excluded_if_zero_exact_not_all_conditional_upstream_semantics"}


def selftest() -> dict:
    checks = 0
    # Architectural inverse validation uses a separately evaluated rounding
    # quantizer on a dense exact rational grid including all interval endpoints.
    for mode, sig in itertools.product(("rn", "rd", "ru", "rz"), range(9, 15)):
        exponent = -8
        inv = correction_inverse(sig, exponent, mode)
        for offset in range(-40, 41):
            y = (F(sig) + F(offset, 16)) * power(exponent)
            policy = "RN" if mode == "rn" else "AWAY" if mode == "ru" else "CHOP"
            assert inv.contains(1 - y) == (quantize(y, 4, policy) == sig * power(exponent))
            checks += 1
    for lo, hi, lc, hc in itertools.product(range(-8, 9), range(-8, 9), (False, True), (False, True)):
        if lo > hi:
            continue
        interval = Interval(F(lo, 4), F(hi, 4), lc, hc)
        a, b = interval.grid(F(1, 2))
        assert [i for i in range(-20, 21) if interval.contains(F(i, 2))] == list(range(a, b + 1))
        checks += 1
    # Tie-even and round-to-odd are deliberately distinct at retained LSBs.
    assert quantize(F(17, 16), 4, "RN") == 1
    assert quantize(F(17, 16), 4, "RNAWAY") == F(9, 8)
    assert quantize(F(33, 32), 4, "JAM") == F(9, 8)
    assert quantize(F(37, 32), 4, "JAM") == F(9, 8)
    return {"exact_inverse_and_grid_checks": checks, "tie_and_jam_checks": 4}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path)
    p.add_argument("--model", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    checked = selftest()
    if a.selftest:
        print(json.dumps(checked, sort_keys=True))
        return
    assert a.root and a.model and a.output
    if a.output.exists():
        raise SystemExit("refusing to overwrite report")
    rows, evidence = load_rows(a.root, a.model)
    derived = [inverse_row(row) for row in rows]
    intervals = [r for r, _ in derived]
    semantics = semantic_audit([e for _, e in derived], rows)
    upstream = upstream_audit(a.root, rows, [e for _, e in derived])
    report = {"experiment": "h1593_inverse_rounding_constraints", "hardware_execution": "none_cached_labels_only",
              "source_rows": len(rows), "source_operands": len({r["operand"] for r in rows}),
              "unobserved_modes_inferred": 0, "selector_promotion": "none", "selftest": checked,
              "claim_boundary": "exact_inverse_of_assumed_positive_round64(1-c)_composition_intermediate_inverses_conditional_not_physical_localization",
              "rows": intervals, "uniform_terminal_semantic_audit": semantics,
              "uniform_last_Horner_add_semantic_audit": upstream,
              "sha256": {"script": digest(Path(__file__)), "model": digest(a.model),
                         "source": digest(a.root / "src/fsincos_skylake.c"), "evidence": evidence}}
    with a.output.open("x") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"rows": len(rows), "schedules": semantics["enumerated_fixed_schedules"],
                      "exact_schedules": len(semantics["exact_schedules"]), "best_rows": semantics["best_correct_rows"],
                      "pair_exact_schedules": semantics["schedules_exact_on_individual_pairs"],
                      "last_add_schedules": upstream["enumerated_fixed_schedules"],
                      "last_add_exact": len(upstream["exact_schedules"]),
                      "last_add_best_rows": upstream["best_correct_rows"]}, sort_keys=True))


if __name__ == "__main__":
    main()
