#!/usr/bin/env python3
"""Cached-model-only encoding sweep; no x87 execution or silicon claim.

Compare the hash-locked H1590 repaired O2 and UBSan builds on a deterministic
software input bank spanning all exponent fields and selected exceptional
encodings. This diagnoses implementation arithmetic, not new hardware truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from collections import Counter
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bank() -> tuple[list[str], dict]:
    cases: dict[tuple[int, int], set[str]] = {}

    def add(se: int, sig: int, origin: str) -> None:
        assert 0 <= se < 65536 and 0 <= sig < 1 << 64
        cases.setdefault((se, sig), set()).add(origin)

    rng = random.Random(0x1597)
    for exponent in range(32768):
        sig = (1 << 63) | rng.getrandbits(63)
        add(exponent, sig, "all_exponents_positive_normalized_significand")
        add(exponent | 0x8000, sig, "all_exponents_negative_normalized_significand")
    edge_exponents = sorted({0, 1, 2, 3, 0x3FBF, 0x3FC0, 0x3FDF, 0x3FE0,
                             0x3FFC, 0x3FFD, 0x3FFE, 0x3FFF, 0x4000, 0x4001,
                             0x403D, 0x403E, 0x403F, 0x7FFD, 0x7FFE, 0x7FFF})
    signatures = {0, 1, 2, 3, (1 << 62)-1, 1 << 62, (1 << 63)-1,
                  1 << 63, (1 << 63)+1, (1 << 63)+7, (1 << 64)-2, (1 << 64)-1,
                  0xAAAAAAAAAAAAAAAA, 0xD0D000000CC0B3F8, 0xB504F333F9DE6484,
                  0xC90FDAA22168C235, 0xE73FFFFD2C52DF71}
    for exponent in edge_exponents:
        for sign in (0, 0x8000):
            for sig in signatures:
                add(exponent | sign, sig, "encoding_and_domain_boundaries")
    for _ in range(16384):
        add(rng.getrandbits(16), rng.getrandbits(64), "unrestricted_software_bits")
    for exponent in range(0x3FF7, 0x4008):
        for _ in range(128):
            sig = (1 << 63) | rng.getrandbits(63)
            add(exponent, sig, "dense_reduction_domain")
            add(exponent | 0x8000, sig, "dense_reduction_domain")
    ordered = sorted(cases)
    return [f"{se:04x} {sig:016x}" for se, sig in ordered], {
        "seed": 0x1597, "unique_encodings": len(ordered),
        "origin_memberships": dict(Counter(t for tags in cases.values() for t in tags)),
        "exponent_fields": len({se & 0x7FFF for se, _ in ordered}),
        "hardware_labels": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit("refusing existing evidence directory")
    audit_path = args.root / "tmp/ledger33/current/h1590_signed_threshold_ub_audit/report.json"
    prior = json.loads(audit_path.read_text())
    source = args.root / "src/fsincos_skylake.c"
    assert digest(source) == prior["sha256"]["source_after"]
    models = {name: args.models / name for name in ("after_O2", "after_ubsan")}
    for name, path in models.items():
        assert digest(path) == prior["versions"][name]["binary_sha256"]
    cases, description = bank()
    args.output_dir.mkdir(parents=True)
    inputs = "".join(row + "\n" for row in cases)
    input_path = args.output_dir / "software_inputs.txt"
    with input_path.open("x") as output:
        output.write(inputs)
    runs = {}
    equal = True
    for instruction in ("fcos", "fsin"):
        for mode in ("rn", "rd", "ru", "rz"):
            baseline = None
            for name, model in models.items():
                key = f"{name}_{instruction}_{mode}"
                command = [str(model.resolve()), "--batch", "--"+instruction+"-standalone", "--rc="+mode]
                process = subprocess.run(command, input=inputs, capture_output=True, text=True, timeout=120)
                artifacts = {}
                for extension, content in (("stdout", process.stdout), ("stderr", process.stderr)):
                    path = args.output_dir / (key+"."+extension)
                    with path.open("x") as output:
                        output.write(content)
                    artifacts[path.name] = digest(path)
                lines = process.stdout.splitlines()
                if baseline is None:
                    baseline = lines
                changes = [{"row": i, "operand": cases[i], "baseline": baseline[i], "candidate": line}
                           for i, line in enumerate(lines[:len(baseline)]) if line != baseline[i]]
                same = process.returncode == 0 and len(lines) == len(cases) and lines == baseline
                equal &= same
                diagnostics = [line for line in process.stderr.splitlines() if "runtime error:" in line]
                runs[key] = {"returncode": process.returncode, "output_rows": len(lines),
                             "status_counts": dict(Counter(line.split()[0] for line in lines)),
                             "same_as_O2": same, "changes": changes,
                             "runtime_diagnostics": diagnostics, "artifacts": artifacts}
                print(key, "rows", len(lines), "changes", len(changes), "diagnostics", len(diagnostics), flush=True)
    report = {"experiment": "h1597_broad_encoding_ub_audit", "bank": description,
              "hardware_execution": "none", "new_hardware_labels": 0,
              "all_sanitized_outputs_equal_O2": equal,
              "sanitizer_clean_on_bank": not any(r["runtime_diagnostics"] for r in runs.values()),
              "runs": runs,
              "claim_boundary": "finite_software_implementation_audit_not_global_UB_freedom_or_silicon_equivalence",
              "sha256": {"source": digest(source), "script": digest(Path(__file__)),
                         "h1590": digest(audit_path), "inputs": digest(input_path),
                         "models": {name: digest(path) for name, path in models.items()}}}
    with (args.output_dir / "report.json").open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")


if __name__ == "__main__":
    main()
