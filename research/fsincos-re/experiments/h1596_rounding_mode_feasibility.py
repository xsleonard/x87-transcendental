#!/usr/bin/env python3
"""Intersect exact final-rounding inverses of authenticated cached labels.

No C model is executed; model predictions and literal operand ledgers are
never ground truth. A nonempty interval means only that a mode-independent
pre-rounded value is possible under ordinary final binary80 rounding.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path

from h1582_equality_frontier_reconciliation import checked_score


MODES = ("rn", "rd", "ru", "rz")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def power(e: int) -> F:
    return F(1 << e) if e >= 0 else F(1, 1 << -e)


def floor(x: F) -> int:
    return x.numerator // x.denominator


def ceil(x: F) -> int:
    return -floor(-x)


@dataclass(frozen=True)
class Interval:
    lo: F
    hi: F
    lc: bool
    hc: bool

    def nonempty(self) -> bool:
        return self.lo < self.hi or self.lo == self.hi and self.lc and self.hc

    def contains(self, x: F) -> bool:
        return (x > self.lo or x == self.lo and self.lc) and (x < self.hi or x == self.hi and self.hc)

    def intersect(self, other: Interval) -> Interval:
        lo, hi = max(self.lo, other.lo), min(self.hi, other.hi)
        lc = (lo != self.lo or self.lc) and (lo != other.lo or other.lc)
        hc = (hi != self.hi or self.hc) and (hi != other.hi or other.hc)
        return Interval(lo, hi, lc, hc)

    def negated(self) -> Interval:
        return Interval(-self.hi, -self.lo, self.hc, self.lc)

    def json(self) -> dict:
        return {"lower": str(self.lo), "upper": str(self.hi), "lower_closed": self.lc,
                "upper_closed": self.hc, "nonempty": self.nonempty()}


def inverse_components(sig: int, e: int, negative: bool, mode: str, precision: int = 64) -> Interval:
    """Exact neighbors include the asymmetric gap at a power-of-two binade."""
    assert 1 << (precision - 1) <= sig < 1 << precision
    unit = power(e)
    y = sig * unit
    previous = y - unit / 2 if sig == 1 << (precision - 1) else y - unit
    following = y + unit
    if negative:
        previous, y, following = -following, -y, -previous
    if mode == "rn":
        return Interval((previous + y) / 2, (y + following) / 2, sig % 2 == 0, sig % 2 == 0)
    if mode == "rd" or mode == "rz" and not negative:
        return Interval(y, following, True, False)
    assert mode == "ru" or mode == "rz" and negative
    return Interval(previous, y, False, True)


def inverse(hardware: str, mode: str) -> Interval:
    se, sig = (int(x, 16) for x in hardware.split(":"))
    exponent = se & 0x7FFF
    assert 0 < exponent < 0x7FFF, "this audit admits only finite normal outputs"
    return inverse_components(sig, exponent - 16383 - 63, bool(se >> 15), mode)


def minimal_witness(interval: Interval, sample_hardware: str) -> tuple[int, F]:
    """Find the least normalized precision >=64 with an interval member."""
    assert interval.nonempty()
    se, _ = (int(x, 16) for x in sample_hardware.split(":"))
    top = (se & 0x7FFF) - 16383
    for precision in range(64, 129):
        for exponent in range(top - precision, top - precision + 3):
            unit = power(exponent)
            lo = ceil(interval.lo / unit) if interval.lc else floor(interval.lo / unit) + 1
            hi = floor(interval.hi / unit) if interval.hc else ceil(interval.hi / unit) - 1
            candidates = (lo, hi, 1 << (precision - 1), -(1 << (precision - 1)),
                          (1 << precision) - 1, -((1 << precision) - 1))
            for q in candidates:
                if lo <= q <= hi and abs(q).bit_length() == precision:
                    value = q * unit
                    assert interval.contains(value)
                    return precision, value
    raise AssertionError("no <=128-bit dyadic witness in a supposedly nonempty local interval")


def key(row: dict) -> tuple[str, str, str]:
    return row["instruction"], row["mode"], row["operand"]


def dedup(rows: list[dict]) -> list[dict]:
    result = {}
    for r in rows:
        k = key(r)
        if k in result:
            assert result[k]["hardware"] == r["hardware"], ("conflicting observed labels", k)
            result[k]["sources"] = sorted(set(result[k]["sources"] + r["sources"]))
        else:
            result[k] = dict(r, sources=list(r["sources"]))
    return [result[k] for k in sorted(result)]


def row(instruction: str, mode: str, operand: str, hardware: str, source: str) -> dict:
    assert mode in MODES and instruction in ("fcos", "fsin")
    return dict(instruction=instruction, mode=mode, operand=operand.lower(), hardware=hardware.lower(), sources=[source])


def audit(rows: list[dict], detail: bool = True) -> dict:
    rows = dedup(rows)
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["instruction"], r["operand"]].append(r)
    details, conflicts = [], []
    mode_count, mode_patterns, precision_count = Counter(), Counter(), Counter()
    for (instruction, operand), group in sorted(grouped.items()):
        current = inverse(group[0]["hardware"], group[0]["mode"])
        for r in group[1:]:
            current = current.intersect(inverse(r["hardware"], r["mode"]))
        modes = sorted({r["mode"] for r in group}, key=MODES.index)
        mode_count[len(modes)] += 1
        mode_patterns[",".join(modes)] += 1
        record = {"instruction": instruction, "operand": operand, "modes": modes,
                  "observed_outputs": {r["mode"]: r["hardware"] for r in group},
                  "sources_by_mode": {r["mode"]: r["sources"] for r in group},
                  "intersection": current.json()}
        if current.nonempty():
            precision, witness = minimal_witness(current, group[0]["hardware"])
            assert all(inverse(r["hardware"], r["mode"]).contains(witness) for r in group)
            precision_count[precision] += 1
            record.update(minimum_precision_at_least64=precision, feasible_prevalue=str(witness))
        else:
            conflicts.append(record)
        if detail:
            details.append(record)
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {"unique_observed_rows": len(rows), "instruction_operand_groups": len(grouped),
            "groups_by_observed_mode_count": dict(sorted(mode_count.items())),
            "groups_by_mode_pattern": dict(sorted(mode_patterns.items())),
            "groups_by_minimum_feasible_precision_at_least64": dict(sorted(precision_count.items())),
            "empty_intersections": len(conflicts), "conflicts": conflicts,
            "canonical_observed_rows_sha256": hashlib.sha256(canonical).hexdigest(), "groups": details}


def tsv(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load(root: Path) -> tuple[dict, dict]:
    c = root / "tmp/ledger33/current"
    audit_path = c / "h1590_signed_threshold_ub_audit/report.json"
    provenance = json.loads(audit_path.read_text())
    evidence = dict(provenance["sha256"]["evidence"])
    for name, h in evidence.items():
        assert digest(root / name) == h, name
    evidence[str(audit_path.relative_to(root))] = digest(audit_path)
    named = []
    for name in ("h1575_current_rule_ablation.json", "h1582_equality_frontier_reconciliation.json",
                 "h1589_equality_gate_collision_audit.json"):
        path = c / name
        assert digest(path) == evidence[str(path.relative_to(root))]
        d = json.loads(path.read_text())
        for r in d["rows" if name.startswith("h1575") else "new_rows"]:
            named.append(row("fcos", r["mode"], r["operand"], r["hardware"], r["source"] + ":" + r["case_id"]))
        if name.startswith("h1575"):
            wall = c / "h1531_shared_tree_topology_audit.json"
            assert digest(wall) == d["sha256"]["defining_wall"]
            evidence[str(wall.relative_to(root))] = digest(wall)
    assert len(named) == len(dedup(named)) == 82
    aliases, projected = [], []
    existing = {(r["mode"], r["operand"]): r for r in named}
    projection_details = []
    for campaign, stem in (("h1570", "h1571_exact_preimage_transfer"), ("h1573", "h1574_signed_preimage_transfer")):
        for r in checked_score(root, campaign, stem, evidence):
            source = campaign + ":" + r["case_id"]
            aliases.append(row(r["instruction"], r["mode"], r["operand"], r["hardware"], source))
            anchor_mode = r.get("anchor_mode", r["mode"])
            anchor = existing[anchor_mode, r["anchor"]]
            se, sig = r["hardware"].split(":")
            negative = int(se, 16) >> 15
            canonical = f"{int(se,16)&0x7fff:04x}:{sig}"
            assert canonical == anchor["hardware"]
            canonical_interval = inverse(r["hardware"], r["mode"])
            if negative:
                canonical_interval = canonical_interval.negated()
            assert canonical_interval == inverse(canonical, anchor_mode)
            projected.append(row("fcos", anchor_mode, r["anchor"], canonical, source + ":assumed_signed_residual_projection"))
            projection_details.append(dict(source=source, instruction=r["instruction"], operand=r["operand"],
                                           mode=r["mode"], output_negative=negative, anchor=r["anchor"],
                                           canonical_mode=anchor_mode, inverse_equals_existing_anchor_inverse=True))
    assert len(aliases) == 52
    raw_history_path = c / "h1091_r59_allmodes.tsv"
    history_score_path = c / "h1092_r59_allmode_score.tsv"
    cache_audit_path = c / "h1291_faddword_valid_cache_audit.txt"
    cache_pins = dict(line.split("\t", 1) for line in cache_audit_path.read_text().splitlines() if "\t" in line)
    for path in (raw_history_path, history_score_path):
        assert digest(path) == cache_pins["score_sha256." + path.name]
        evidence[str(path.relative_to(root))] = digest(path)
    assert digest(history_score_path) == "fdaec8e810bfb3e5220abc636abef5153b524cf3d9d02dcdaae753f2ddf9ed6c"
    history = [row("fcos", r["mode"], r["op"], r["hw"], "h1091:" + r["corpus"] + ":" + r["index"]) for r in tsv(raw_history_path)]
    scored_hw = {(r["mode"], r["op"]): r["hw"] for r in tsv(history_score_path)}
    assert all(scored_hw[r["mode"], r["operand"]] == r["hardware"] for r in history)
    assert len(history) == 116
    controls_path = c / "h1107_controls_allmodes.tsv"
    assert digest(controls_path) == evidence[str(controls_path.relative_to(root))]
    controls = [row("fcos", r["mode"], r["op"], r["hw"], "h1107:" + r["corpus"] + ":" + r["index"]) for r in tsv(controls_path)]
    # H1210 explicitly substitutes baseline for missing hardware modes and
    # sets RZ=RD. Inspect and preserve it, but do not count those as captures.
    derived_path = c / "h1210_stagea_residual_allmodes.tsv"
    derived = tsv(derived_path)
    for path in (cache_audit_path, derived_path, root / "experiments/h1210_stagea_residual_reframe.py",
                 root / "experiments/h1091_r59_allmodes_cached.py", root / "experiments/h1107_cached_controls_allmodes.py"):
        evidence[str(path.relative_to(root))] = digest(path)
    return {"named": named, "aliases": aliases, "projected": projected, "history": history, "controls": controls,
            "projection_details": projection_details, "derived_h1210_rows_not_admitted": len(derived)}, evidence


def selftest() -> dict:
    # Independent enumerated-neighbor oracle includes both signs and binades.
    checks = 0
    for precision in range(2, 7):
        representables = sorted({sign * sig * power(e) for sign in (-1, 1)
                                 for e in range(-10, 5) for sig in range(1 << (precision-1), 1 << precision)})
        for sign, sig, mode in itertools.product((-1, 1), range(1 << (precision-1), 1 << precision), MODES):
            y = sign * sig * power(-4)
            interval = inverse_components(sig, -4, sign < 0, mode, precision)
            at = representables.index(y)
            previous, following = representables[at-1], representables[at+1]
            probes = [previous, (previous+y)/2, y, (y+following)/2, following,
                      (3*previous+y)/4, (previous+3*y)/4, (3*y+following)/4, (y+3*following)/4]
            for x in probes:
                if mode == "rn":
                    distance = abs(x-y)
                    expected = distance < min(abs(x-previous), abs(x-following)) or (
                        distance == min(abs(x-previous), abs(x-following)) and sig % 2 == 0)
                elif mode == "rd" or mode == "rz" and sign > 0:
                    expected = y <= x < following
                else:
                    expected = previous < x <= y
                assert interval.contains(x) == expected
                checks += 1
    a, b = Interval(F(0), F(1), True, False), Interval(F(1), F(2), True, True)
    assert not a.intersect(b).nonempty()
    assert Interval(F(0), F(1), True, True).intersect(b).json()["nonempty"]
    return {"signed_neighbor_rounding_cases": checks, "intersection_endpoint_checks": 2}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    tests = selftest()
    if a.selftest:
        print(json.dumps(tests, sort_keys=True))
        return
    assert a.root and a.output
    if a.output.exists():
        raise SystemExit("refusing existing report")
    banks, evidence = load(a.root)
    named, history = banks["named"], banks["history"]
    named_ops = {r["operand"] for r in named}
    enriched = dedup(named + [r for r in history if r["operand"] in named_ops])
    reports = {
        "named_direct_82_only": audit(named),
        "named_direct_enriched_with_authenticated_historical_modes": audit(enriched),
        "named_external_with_aliases_134": audit(named + banks["aliases"]),
        "enriched_direct_plus_assumed_canonical_alias_projection": audit(enriched + banks["projected"]),
        "historical_h1091_allmode": audit(history),
        "separate_h1107_allmode_control_wall": audit(banks["controls"], detail=False),
        "union_named_historical_controls_external": audit(named + history + banks["controls"] + banks["aliases"], detail=False),
    }
    report = {"experiment": "h1596_rounding_mode_feasibility", "hardware_execution": "none_cached_only",
              "C_model_execution": "none", "unobserved_modes_inferred": 0, "literal_ledger_as_truth": False,
              "claim_boundary": "nonempty_inverse_intersection_is_feasibility_only_not_correctness_or_recovered_internal_arithmetic",
              "conditional_exclusion": "empty_intersection_excludes_only_mode_independent_prevalue_plus_ordinary_final_RC_rounding",
              "selftest": tests, "banks": reports, "alias_projection_details": banks["projection_details"],
              "alias_projection_assumptions": "same_exact_residual_common_unsigned_result_across_sign_instruction_and_reduction_paths_not_new_direct_labels",
              "derived_h1210_rows_not_admitted_as_observations": banks["derived_h1210_rows_not_admitted"],
              "sha256": {"script": digest(Path(__file__)), "evidence": evidence}}
    with a.output.open("x") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({k: {n: v[n] for n in ("unique_observed_rows", "instruction_operand_groups", "groups_by_observed_mode_count", "empty_intersections", "groups_by_minimum_feasible_precision_at_least64")} for k, v in reports.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
