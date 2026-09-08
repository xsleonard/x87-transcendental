#!/usr/bin/env python3
"""Prove the fixed R1382 product-cut-45 target cell is endpoint-invariant.

The H1470/H1496 lattice fixes right-product shift 64, so its H1495 selector
column is necessarily 46.  This audit derives the distinct shift-63
comparator interval exactly, proves its reduced form and the recovered
floor-division invariance in QF_BV, replays the existing cached shift-63
population, and runs H1497's targeted modular inverse scanner.  The scanner
retains a strongest adversary that changes the internal comparator bit while
also satisfying the formerly proposed Mreg and endpoint-residue conditions.
Independent source replay must show that its endpoint remains unchanged.

No x87 instruction is executed and no hardware label is opened.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

try:
    import z3
except ImportError as error:
    raise SystemExit("z3-solver 4.15.3.0 is required") from error

from h1210_stagea_residual_reframe import parse_dump, run
from h1463_r1382_modular_square import prove_endpoint_residues


MODES = ("rn", "rd", "ru", "rz")
DISCARD_LOW = 0x2AAAAAAAAAAAAAAB
DISCARD_HIGH = 0x2AAABFFFFFFFFFFF
RIGHT_LOW72 = (4 << 63) | DISCARD_LOW
RIGHT_HIGH72 = (4 << 63) | DISCARD_HIGH
ENDPOINT_RESIDUES = (0x000, 0x100, 0x001, 0x101, 0x081, 0x180)
NEAR_RE = re.compile(
    r"^NEARCANDIDATE45 3ffc ([0-9a-f]{16}) "
    r"square ([0-9a-f]{17}) fourth ([0-9a-f]{17}) "
    r"right_low72 ([0-9a-f]+) base_low9 ([0-9a-f]{3}) "
    r"iteration ([0-9]+)$"
)
WITNESS_RE = re.compile(
    r"^INERTCANDIDATE45 3ffc ([0-9a-f]{16}) "
    r"square ([0-9a-f]{17}) fourth ([0-9a-f]{17}) "
    r"right_low72 ([0-9a-f]+) iteration ([0-9]+)$"
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bv(value: int, width: int):
    return z3.BitVecVal(value & ((1 << width) - 1), width)


def prove_equivalence(name: str, left, right) -> dict[str, str]:
    solver = z3.SolverFor("QF_BV")
    solver.add(left != right)
    status = solver.check()
    result = {"status": str(status)}
    if status == z3.unknown:
        result["reason_unknown"] = solver.reason_unknown()
    if status != z3.unsat:
        raise RuntimeError(f"{name} equivalence is {status}")
    return result


def prove_column45_reductions() -> dict[str, object]:
    rd63 = z3.BitVec("h1497_rd63", 63)
    rd = z3.ZeroExt(2, rd63)
    mask = bv((1 << 47) - 1, 65)
    triple = bv(3, 65) * rd
    merged = triple - (triple & mask)
    plain = triple - ((bv(2, 65) * rd) & mask) - (rd & mask)
    threshold = bv(1 << 63, 65)
    original_transition = z3.And(
        z3.UGE(merged, threshold), z3.ULT(plain, threshold)
    )
    reduced_transition = z3.And(
        z3.UGE(rd63, bv(DISCARD_LOW, 63)),
        z3.ULE(rd63, bv(DISCARD_HIGH, 63)),
    )

    product72 = z3.BitVec("h1497_right_product_low72", 72)
    original_terminal = z3.And(
        z3.Extract(71, 63, product72) == bv(4, 9),
        z3.UGE(z3.Extract(62, 0, product72), bv(DISCARD_LOW, 63)),
        z3.ULE(z3.Extract(62, 0, product72), bv(DISCARD_HIGH, 63)),
    )
    reduced_terminal = z3.And(
        z3.UGE(product72, bv(RIGHT_LOW72, 72)),
        z3.ULE(product72, bv(RIGHT_HIGH72, 72)),
    )

    b1 = z3.BitVec("h1497_b1", 1)
    b2 = z3.BitVec("h1497_b2", 1)
    base0 = bv(-4, 3) + (z3.ZeroExt(2, b1) << 1) + z3.ZeroExt(2, b2)
    u0 = base0 >> 2
    floor_solver = z3.SolverFor("QF_BV")
    floor_solver.add(u0 != bv(-1, 3))
    floor_status = floor_solver.check()
    if floor_status != z3.unsat:
        raise RuntimeError(f"column-45 u0 invariance is {floor_status}")

    u0_table = []
    for b1 in (0, 1):
        for b2 in (0, 1):
            base = -4 + 2 * b1 + b2
            u0_table.append({
                "b1": b1,
                "b2": b2,
                "base0": base,
                "u0": base // 4,
            })
    if [row["u0"] for row in u0_table] != [-1, -1, -1, -1]:
        raise RuntimeError("column-45 u0 truth table changed")

    return {
        "comparator_transition": {
            **prove_equivalence(
                "comparator transition", original_transition, reduced_transition
            ),
            "discard_interval": [
                f"{DISCARD_LOW:016x}", f"{DISCARD_HIGH:016x}"
            ],
            "meaning": "incumbent b1=1 while no-merge b1=0",
        },
        "terminal_fusion": {
            **prove_equivalence(
                "terminal fusion", original_terminal, reduced_terminal
            ),
            "right_product_low72_interval": [
                f"{RIGHT_LOW72:018x}", f"{RIGHT_HIGH72:018x}"
            ],
            "meaning": (
                "right-significand low nine equals payload four and the "
                "discarded 63-bit product crosses the comparator"
            ),
        },
        "tie_floor_invariance": {
            "status": str(floor_status),
            "base0_formula": "-4 + 2*b1 + b2",
            "domain": "b1,b2 in {0,1}",
            "u0": -1,
            "meaning": (
                "all four comparator states have the same floor-divided "
                "tie threshold, so the R1382 merge cannot change this cell's "
                "architectural correction"
            ),
        },
        "endpoint_residues": {
            **prove_endpoint_residues(),
            "residues": [f"{item:03x}" for item in ENDPOINT_RESIDUES],
        },
        "u0_truth_table": u0_table,
    }


def model_outputs(binary: Path, signatures: list[str]):
    outputs = {}
    payload = "".join(f"3ffc {signature}\n" for signature in signatures)
    for mode in MODES:
        completed = subprocess.run(
            [str(binary), "--batch", "--fcos-standalone", f"--rc={mode}"],
            input=payload,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        if completed.stderr:
            raise RuntimeError(f"unexpected {mode} model stderr")
        rows = []
        for line in completed.stdout.splitlines():
            fields = line.lower().split()
            if len(fields) < 3 or fields[0] != "ok":
                raise RuntimeError(f"bad model output: {line!r}")
            rows.append(f"{fields[1]}:{fields[2]}")
        if len(rows) != len(signatures):
            raise RuntimeError(f"{mode} model row count changed")
        outputs[mode] = rows
    return outputs


def cached_column45_audit(path: Path, incumbent: Path, r1382: Path):
    rows = []
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["theta"] == "0" and row["s4"] == "66" \
                    and row["low3"] == "3" and row["rsh"] == "63":
                rows.append(row)
    signatures = [row["op"].split()[1].lower() for row in rows]
    if len(signatures) != len(set(signatures)):
        raise RuntimeError("cached column-45 operand duplication changed")
    current = model_outputs(incumbent, signatures)
    alternate = model_outputs(r1382, signatures)
    endpoint_changes = sum(
        any(current[mode][index] != alternate[mode][index] for mode in MODES)
        for index in range(len(signatures))
    )

    operands = [f"3ffc {signature}" for signature in signatures]
    _, current_stderr = run(incumbent, "rn", operands, dump=True)
    _, alternate_stderr = run(r1382, "rn", operands, dump=True)
    current_dump = parse_dump(current_stderr, operands)
    alternate_dump = parse_dump(alternate_stderr, operands)
    internal_counts = Counter()
    nearest = []
    for operand, left, right in zip(operands, current_dump, alternate_dump):
        changed = tuple(
            key for key in ("rd3", "b1", "b2", "br_tfire", "br_r")
            if left.get(key) != right.get(key)
        )
        internal_counts[",".join(changed) if changed else "none"] += 1
        discard = int(left["tc_rdisc"], 16)
        distance = min(abs(discard - DISCARD_LOW), abs(discard - DISCARD_HIGH))
        nearest.append({
            "operand": operand.replace(" ", ":"),
            "right_discard": f"{discard:016x}",
            "distance_to_comparator_interval": f"{distance:x}",
        })
    nearest.sort(key=lambda row: int(row["distance_to_comparator_interval"], 16))
    if endpoint_changes != 0:
        raise RuntimeError("cached column-45 audit gained an endpoint separator")
    return {
        "rows": len(rows),
        "unique_operands": len(signatures),
        "endpoint_changes": endpoint_changes,
        "internal_change_classes": dict(sorted(internal_counts.items())),
        "nearest_comparator_rows": nearest[:8],
    }


def run_scanner(scanner: Path, samples: int, seed: str, maximum: int):
    selftest = subprocess.run(
        [str(scanner), "--selftest"], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    if selftest.stdout != "SELFTEST: ok\n" or selftest.stderr:
        raise RuntimeError("column-45 scanner selftest failed")
    completed = subprocess.run(
        [str(scanner), str(samples), seed, f"--max-witnesses={maximum}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in (0, 1) or completed.stderr:
        raise RuntimeError(
            f"scanner failed rc={completed.returncode}: {completed.stderr}"
        )
    near = []
    inert_adversaries = []
    summary = None
    for line in completed.stdout.splitlines():
        match = NEAR_RE.fullmatch(line)
        if match is not None:
            near.append({
                "sig": match.group(1),
                "operand": f"3ffc:{match.group(1)}",
                "square_sig": match.group(2),
                "fourth_sig": match.group(3),
                "right_low72": match.group(4),
                "base_low9": match.group(5),
                "iteration": int(match.group(6)),
            })
            continue
        match = WITNESS_RE.fullmatch(line)
        if match is not None:
            inert_adversaries.append({
                "sig": match.group(1),
                "operand": f"3ffc:{match.group(1)}",
                "square_sig": match.group(2),
                "fourth_sig": match.group(3),
                "right_low72": match.group(4),
                "iteration": int(match.group(5)),
            })
            continue
        if line.startswith("NO_INERT_WITNESS "):
            summary = {
                field.split("=", 1)[0]: int(field.split("=", 1)[1], 0)
                for field in line.split()[1:]
            }
            continue
        raise RuntimeError(f"unexpected scanner line: {line!r}")
    if summary is None and len(inert_adversaries) != maximum:
        raise RuntimeError("scanner stopped without summary or adversary limit")
    return near, inert_adversaries, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scanner", required=True, type=Path)
    parser.add_argument("--incumbent", required=True, type=Path)
    parser.add_argument("--r1382", required=True, type=Path)
    parser.add_argument("--h1386", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=30_000_000)
    parser.add_argument("--seed", default="0xbb67ae8584caa73b")
    parser.add_argument("--max-witnesses", type=int, default=128)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")

    reductions = prove_column45_reductions()
    cached = cached_column45_audit(args.h1386, args.incumbent, args.r1382)
    near, inert_adversaries, summary = run_scanner(
        args.scanner, args.samples, args.seed, args.max_witnesses
    )
    if len({row["sig"] for row in near + inert_adversaries}) \
            != len(near) + len(inert_adversaries):
        raise RuntimeError("column-45 scanner emitted duplicate operands")

    signatures = [row["sig"] for row in near + inert_adversaries]
    current = model_outputs(args.incumbent, signatures) if signatures else {}
    alternate = model_outputs(args.r1382, signatures) if signatures else {}
    operands = [f"3ffc {signature}" for signature in signatures]
    if operands:
        _, current_stderr = run(args.incumbent, "rn", operands, dump=True)
        _, alternate_stderr = run(args.r1382, "rn", operands, dump=True)
        current_dumps = parse_dump(current_stderr, operands)
        alternate_dumps = parse_dump(alternate_stderr, operands)
    else:
        current_dumps = []
        alternate_dumps = []
    replay = []
    for index, row in enumerate(near + inert_adversaries):
        changed = [
            mode for mode in MODES
            if current[mode][index] != alternate[mode][index]
        ]
        left = current_dumps[index]
        right = alternate_dumps[index]
        internal_changes = [
            key for key in ("rd3", "b1", "b2", "br_u0", "br_tfire", "br_r")
            if left.get(key) != right.get(key)
        ]
        replay.append({
            "operand": row["operand"],
            "kind": "near" if index < len(near) else "inert_adversary",
            "changed_modes": changed,
            "internal_changes": internal_changes,
            "incumbent_state": {
                key: left.get(key)
                for key in ("theta", "rd3", "b1", "b2", "br_u0",
                            "br_tfire", "br_r")
            },
            "r1382_state": {
                key: right.get(key)
                for key in ("theta", "rd3", "b1", "b2", "br_u0",
                            "br_tfire", "br_r")
            },
        })
    near_changes = sum(bool(row["changed_modes"]) for row in replay if row["kind"] == "near")
    adversary_changes = sum(
        bool(row["changed_modes"])
        for row in replay if row["kind"] == "inert_adversary"
    )
    if near_changes or adversary_changes:
        raise RuntimeError("the proved-invariant column-45 cell changed an endpoint")
    for row in replay:
        if row["kind"] != "inert_adversary":
            continue
        incumbent_state = row["incumbent_state"]
        r1382_state = row["r1382_state"]
        if row["internal_changes"] != ["rd3", "b1"] \
                or incumbent_state["theta"] != "0" \
                or incumbent_state["b1"] != "1" \
                or r1382_state["b1"] != "0" \
                or incumbent_state["b2"] != "0" \
                or r1382_state["b2"] != "0" \
                or incumbent_state["br_u0"] != "-1" \
                or r1382_state["br_u0"] != "-1" \
                or incumbent_state["br_tfire"] != "0" \
                or r1382_state["br_tfire"] != "0":
            raise RuntimeError("inert adversary lost its exact causal signature")

    residues = Counter(row["base_low9"] for row in near)
    nearest_distance = None
    if near:
        nearest_distance = min(
            min((int(row["base_low9"], 16) - target) % 512,
                (target - int(row["base_low9"], 16)) % 512)
            for row in near for target in ENDPOINT_RESIDUES
        )
    report = {
        "experiment": "h1497_r1382_column45_lattice",
        "status": "PROVED_FIXED_CELL_ENDPOINT_INVARIANT",
        "z3_version": z3.get_version_string(),
        "exact_reductions": reductions,
        "causal_scope": {
            "r1382_effect_requires": [
                "s4=66", "low3=3", "theta=0", "R1272 merge gate enabled"
            ],
            "reason": (
                "the current source materializes the hard-3x merge only in "
                "the theta-zero arm; nonzero-theta threshold differences are "
                "counterfactual and cannot be driven by R1382"
            ),
        },
        "cached_column45_population": cached,
        "sampling": {
            "samples": args.samples,
            "seed": args.seed,
            "max_witnesses": args.max_witnesses,
            "summary": summary,
            "near_witnesses": len(near),
            "inert_adversaries": len(inert_adversaries),
            "current_source_endpoint_separators": adversary_changes,
            "near_witness_endpoint_changes": near_changes,
            "nearest_endpoint_residue_distance_mod512": nearest_distance,
            "near_residue_counts": dict(sorted(residues.items())),
        },
        "near_witnesses": near,
        "inert_adversaries": inert_adversaries,
        "model_replay": replay,
        "claim_boundary": (
            "The comparator reduction and tie-floor invariance are exact for "
            "the fixed theta=0, s4=66, side=1, low3=3, distance=9, rsh=63 "
            "cell. The sampling result only demonstrates external reachability "
            "of a strongest inert adversary. It is not a proof about other "
            "column-45 cells and does not validate either H1487 physical pair."
        ),
        "hardware_execution": "none",
        "hardware_labels": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "scanner": digest(args.scanner),
            "scanner_source": digest(
                Path(__file__).with_name("h1497_r1382_column45_lattice.c")
            ),
            "incumbent": digest(args.incumbent),
            "r1382": digest(args.r1382),
            "h1386": digest(args.h1386),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text)
    print(json.dumps({
        "output": str(args.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": report["status"],
        "cached_rows": cached["rows"],
        "cached_rd3_only_changes": cached["internal_change_classes"].get("rd3", 0),
        "near_witnesses": len(near),
        "inert_adversaries": len(inert_adversaries),
        "endpoint_separators": adversary_changes,
        "nearest_endpoint_residue_distance_mod512": nearest_distance,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
