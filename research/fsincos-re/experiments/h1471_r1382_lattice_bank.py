#!/usr/bin/env python3
"""Reproduce and independently replay the H1470 R1382 lattice bank.

The C scanner samples maximal positive-Horner plateaus, solves each resulting
linear modular product inequality exactly, and inverts every retained value
through both chopped-square maps.  This wrapper freezes a deterministic bank
of pre-candidates, replays their arithmetic in the independent H1404 Python
model, classifies current-source endpoints with separately compiled incumbent
and candidate C binaries, and repeats two searches that also require d0d0's
complete internal materialization schedule.

No x87 instruction is executed.  The incumbent/candidate binaries are C-model
builds, not hardware oracles.  The output is therefore an adversarial software
bank, not a capture manifest or a selector validation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
H1404_PATH = HERE / "h1404_exact_preimage_smt.py"
H1404_SPEC = importlib.util.spec_from_file_location("h1404_h1471", H1404_PATH)
if H1404_SPEC is None or H1404_SPEC.loader is None:  # pragma: no cover
    raise SystemExit(f"cannot load {H1404_PATH}")
h1404 = importlib.util.module_from_spec(H1404_SPEC)
sys.modules[H1404_SPEC.name] = h1404
H1404_SPEC.loader.exec_module(h1404)


MODES = ("rn", "rd", "ru", "rz")
ENDPOINT_SAMPLES = 15_000_000
ENDPOINT_SEED = "0x243f6a8885a308d3"
MAX_WITNESSES = 32
TEMPLATE_SIG = 0xD0D000000CC0B3F8
FIXED_RUNS = (
    (5_000_000, "0x9e3779b97f4a7c15"),
    (20_000_000, "0xd1b54a32d192ed03"),
)
WITNESS_RE = re.compile(
    r"^PRECANDIDATE 3ffc ([0-9a-f]{16}) square ([0-9a-f]{17}) "
    r"fourth ([0-9a-f]{17}) right_low72 ([0-9a-f]{17}) "
    r"iteration ([0-9]+)$"
)
PATH_FIELDS = (
    "fourth_shift",
    "negative_mul1_shift",
    "negative_add1_shift",
    "negative_add1_round",
    "negative_mul2_shift",
    "negative_add2_shift",
    "negative_add2_round",
    "positive_mul1_shift",
    "positive_add1_shift",
    "positive_add1_round",
    "positive_mul2_shift",
    "positive_add2_shift",
    "positive_add2_round",
    "left_shift",
    "right_shift",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def run_scanner(scanner: Path, arguments: list[str], expected: set[int]) -> str:
    completed = subprocess.run(
        [str(scanner), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in expected:
        raise RuntimeError(
            f"scanner exited {completed.returncode}: {completed.stderr}"
        )
    if completed.stderr:
        raise RuntimeError(f"unexpected scanner stderr: {completed.stderr}")
    return completed.stdout


def model_outputs(binary: Path, operands: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    payload = "".join(f"3ffc {operand}\n" for operand in operands)
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
            raise RuntimeError(
                f"unexpected {mode} model stderr: {completed.stderr}"
            )
        rows = []
        for line in completed.stdout.splitlines():
            fields = line.split()
            if fields[:1] != ["OK"] or len(fields) not in (3, 5):
                raise RuntimeError(f"bad model row: {line!r}")
            offset = 1 if len(fields) == 3 else 3
            rows.append(
                f"{fields[offset].lower()}:{fields[offset + 1].lower()}"
            )
        if len(rows) != len(operands):
            raise RuntimeError(
                f"{mode} returned {len(rows)} rows for {len(operands)} operands"
            )
        result[mode] = rows
    return result


def parse_summary(output: str) -> dict[str, int]:
    lines = output.splitlines()
    if len(lines) != 1 or not lines[0].startswith("NO_WITNESS "):
        raise RuntimeError(f"bad fixed-path summary: {output!r}")
    values: dict[str, int] = {}
    for field in lines[0].split()[1:]:
        key, value = field.split("=", 1)
        values[key] = int(value, 0)
    return values


def visible_in_repository(root: Path, operand: str) -> bool:
    completed = subprocess.run(
        ["rg", "-l", "-i", "--fixed-strings", operand, str(root)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"repository search failed: {completed.stderr}")
    return completed.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scanner", required=True, type=Path)
    parser.add_argument("--incumbent", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.scanner, args.incumbent, args.candidate):
        if not path.is_file():
            raise SystemExit(f"missing executable: {path}")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    if run_scanner(args.scanner, ["--selftest"], {0}) != "SELFTEST: ok\n":
        raise RuntimeError("scanner selftest did not report success")
    endpoint_stdout = run_scanner(
        args.scanner,
        [
            str(ENDPOINT_SAMPLES),
            ENDPOINT_SEED,
            f"--max-witnesses={MAX_WITNESSES}",
        ],
        {0},
    )
    raw_witnesses = []
    for line in endpoint_stdout.splitlines():
        match = WITNESS_RE.fullmatch(line)
        if match is None:
            raise RuntimeError(f"bad witness row: {line!r}")
        raw_witnesses.append({
            "sig": match.group(1),
            "square_sig": match.group(2),
            "fourth_sig": match.group(3),
            "right_low72": match.group(4),
            "iteration": int(match.group(5)),
        })
    if len(raw_witnesses) != MAX_WITNESSES:
        raise RuntimeError(
            f"expected {MAX_WITNESSES} witnesses, got {len(raw_witnesses)}"
        )
    signatures = [row["sig"] for row in raw_witnesses]
    if len(set(signatures)) != len(signatures):
        raise RuntimeError("endpoint bank contains duplicate external operands")
    already_visible = [
        signature for signature in signatures
        if visible_in_repository(args.repo_root, signature)
    ]
    if already_visible:
        raise RuntimeError(
            f"software bank overlaps repository-visible operands: {already_visible}"
        )

    incumbent = model_outputs(args.incumbent, signatures)
    candidate = model_outputs(args.candidate, signatures)
    template = h1404.concrete_forward(TEMPLATE_SIG)
    template_path = tuple(template[field] for field in PATH_FIELDS)
    path_counts: Counter[str] = Counter()
    changed_mode_counts: Counter[str] = Counter()
    witnesses: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_witnesses):
        sig = int(raw["sig"], 16)
        square = int(raw["square_sig"], 16)
        fourth = int(raw["fourth_sig"], 16)
        right_low72 = int(raw["right_low72"], 16)
        if (sig * sig) >> 61 != square:
            raise AssertionError("external/first-square inversion mismatch")
        if (square * square) >> 66 != fourth:
            raise AssertionError("first-square/fourth inversion mismatch")

        replay = h1404.concrete_forward(sig)
        if replay["square_sig"] != square or replay["fourth_sig"] != fourth:
            raise AssertionError("independent Python replay changed square path")
        replay_right_low72 = (
            replay["fourth_sig"] * replay["positive_sig"]
        ) & ((1 << 72) - 1)
        if replay_right_low72 != right_low72:
            raise AssertionError("independent Python replay changed right residue")
        changed_modes = [
            mode for mode in MODES
            if incumbent[mode][index] != candidate[mode][index]
        ]
        python_changed = [
            mode for mode in MODES
            if replay[f"current_{mode}"] != replay[f"candidate_{mode}"]
        ]
        path = tuple(replay[field] for field in PATH_FIELDS)
        path_key = "/".join(str(value) for value in path)
        path_counts[path_key] += 1
        changed_mode_counts["/".join(changed_modes) or "none"] += 1
        witnesses.append({
            **raw,
            "operand": f"3ffc:{raw['sig']}",
            "changed_modes": changed_modes,
            "endpoint_visible": bool(changed_modes),
            "legacy_h1404_changed_modes": python_changed,
            "legacy_h1404_endpoint_agrees_with_current_source": (
                changed_modes == python_changed
            ),
            "outputs": {
                mode: {
                    "incumbent": incumbent[mode][index],
                    "candidate": candidate[mode][index],
                }
                for mode in MODES
            },
            "path_signature": {
                field: replay[field] for field in PATH_FIELDS
            },
            "matches_d0d0_arithmetic_schedule": path == template_path,
            "actual_merge_gate": int(replay["merge_gate"]),
            "independent_python_arithmetic_replay": "exact_through_prefilter",
            "current_source_c_endpoint_replay": "exact",
        })

    fixed_reports = []
    for samples, seed in FIXED_RUNS:
        output = run_scanner(
            args.scanner,
            [str(samples), seed, "--fixed-d0d0-path"],
            {1},
        )
        summary = parse_summary(output)
        if summary.get("fixed_path_hits") != 0 \
                or summary.get("witnesses") != 0:
            raise AssertionError(f"unexpected fixed-path witness: {summary}")
        fixed_reports.append({
            "samples": samples,
            "seed": seed,
            "summary": summary,
        })

    report = {
        "experiment": "h1471_r1382_lattice_bank",
        "status": "SAT_SOFTWARE_ENDPOINTS_FIXED_PATH_STILL_OPEN",
        "pre_candidate_bank": {
            "plateau_samples_limit": ENDPOINT_SAMPLES,
            "seed": ENDPOINT_SEED,
            "terminated_at_witness_limit": True,
            "last_iteration": raw_witnesses[-1]["iteration"],
            "pre_candidates": len(witnesses),
            "endpoint_visible_candidates": sum(
                row["endpoint_visible"] for row in witnesses
            ),
            "unique_external_operands": len(set(signatures)),
            "repository_visible_before_report": 0,
            "changed_mode_counts": dict(sorted(changed_mode_counts.items())),
            "materialization_path_classes": len(path_counts),
            "d0d0_arithmetic_schedule_matches": sum(
                row["matches_d0d0_arithmetic_schedule"]
                for row in witnesses
            ),
            "d0d0_schedule_endpoint_visible": sum(
                row["matches_d0d0_arithmetic_schedule"]
                and row["endpoint_visible"]
                for row in witnesses
            ),
            "legacy_h1404_endpoint_agreements": sum(
                row["legacy_h1404_endpoint_agrees_with_current_source"]
                for row in witnesses
            ),
            "candidate_rows": witnesses,
        },
        "fixed_d0d0_path_searches": fixed_reports,
        "bounded_conclusion": (
            "The lattice prefilter yields fresh exact external operands and "
            "independent replay identifies a nonempty subset as genuine "
            "R1382 software endpoint separators, so d0d0 is not unique as "
            "an endpoint phenomenon. One frozen pre-candidate shares d0d0's "
            "arithmetic schedule under the relaxed enabling gate used by "
            "H1410/H1468, resolving that relaxed query to SAT, but exact "
            "tree replay gives merge_gate=0 and identical endpoints. No "
            "fresh true separator on d0d0's complete physical path was found."
        ),
        "hardware_execution": "none",
        "hardware_labels": "none",
        "private_ledger_access": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "scanner": digest(args.scanner),
            "incumbent": digest(args.incumbent),
            "candidate": digest(args.candidate),
            "h1404_replay": digest(H1404_PATH),
            "h1470_source": digest(
                HERE / "h1470_r1382_constant_positive_lattice.c"
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "status": report["status"],
        "pre_candidates": len(witnesses),
        "endpoint_visible": report["pre_candidate_bank"][
            "endpoint_visible_candidates"
        ],
        "d0d0_schedule_matches": report["pre_candidate_bank"][
            "d0d0_arithmetic_schedule_matches"
        ],
        "fixed_searches": len(fixed_reports),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
