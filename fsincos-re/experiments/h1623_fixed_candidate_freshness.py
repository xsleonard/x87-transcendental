#!/usr/bin/env python3
"""Conservative public/private freshness audit of the fixed H1622 proposals.

Reject any matching 16-hex input significand, irrespective of instruction,
RC, exponent or host: stricter than full-tuple reuse. Search compressed text
too. Exclude only declared software-generation directories and this audit's
own files. Private file identities, hashes and contents are never published.
No manifest freeze, remote action or hardware execution occurs here.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from pathlib import Path

from h1622_fixed_candidate_challenge_bank_v2 import digest


BANK = "tmp/ledger33/current/h1622_fixed_candidate_challenge_bank_v2/bank.json"
BANK_SHA = "d9f2e5ec5668dc50efb8f50fd230ffe8e76a31c36e608310ab2dd70cdf303fce"
SOFTWARE_DIRECTORIES = (
    "tmp/ledger33/current/h1622_fixed_candidate_challenge_bank",
    "tmp/ledger33/current/h1622_fixed_candidate_challenge_bank_v2",
    "tmp/ledger33/current/h1579_equality_bank",
    "tmp/ledger33/current/h1586_stream_control_plateaus",
)


def matches(root: Path, patterns: Path, excluded: list[Path]) -> set[str]:
    command = ["rg", "--hidden", "--no-ignore", "--search-zip", "--text", "--only-matching",
               "--no-filename", "--ignore-case", "--fixed-strings", "--glob", "!**/.git/**",
               "--file", str(patterns)]
    for path in excluded:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        command.extend(("--glob", "!**/" + relative + "/**"))
    command.append(str(root))
    search = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert search.stdout is not None
    # Sorting keeps repeated occurrences out of Python memory. Results are
    # only the submitted candidate signatures, not paths or ledger contents.
    unique = subprocess.run(["sort", "-fu"], stdin=search.stdout, capture_output=True,
                            env=dict(os.environ, LC_ALL="C"), check=True)
    search.stdout.close()
    errors = search.stderr.read() if search.stderr else b""
    code = search.wait()
    if code not in (0, 1) or errors:
        # Do not expose private paths through diagnostic text. Fail closed.
        raise RuntimeError(f"freshness scan incomplete (exit={code}, diagnostic_bytes={len(errors)}); no eligibility result")
    found = {line.strip().lower() for line in unique.stdout.decode().splitlines()}
    assert all(len(word) == 16 and int(word, 16) >= 0 for word in found)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--private-ledger-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, private, output = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and not output.exists()
    assert digest(root / BANK) == BANK_SHA
    bank = json.loads((root / BANK).read_text())
    assert bank["capture_state"] == "SOFTWARE_ONLY_NOT_FROZEN" and bank["candidate_changed"] is False
    for relative, expected in bank["sha256"]["evidence"].items():
        assert digest(root / relative) == expected, relative
    for name in SOFTWARE_DIRECTORIES[2:]:
        report = json.loads((root / name / "bank.json").read_text())
        assert report["capture_state"] == "SOFTWARE_ONLY_NOT_FROZEN" and report["new_hardware_labels"] == "none"
        # Generated bank directories may be excluded only if they have no
        # capture output or opened/frozen campaign sidecar.
        assert not any(p.name in {"OPENED.json", "FREEZE.json", "hardware-output"} for p in (root / name).rglob("*"))
    proposals = bank["events"]
    signatures = {row["operand"].split()[1] for row in proposals}
    assert len(signatures) == len(proposals)
    output.mkdir(parents=True)
    patterns = output / "candidate_signatures.txt"
    with patterns.open("x") as target:
        target.write("".join(word + "\n" for word in sorted(signatures)))
    excluded = [root / p for p in SOFTWARE_DIRECTORIES] + [output]
    if private.is_relative_to(root):
        excluded.append(private)
    print("Public capture/history audit started; software proposals excluded, compressed files included.", flush=True)
    public_hits = matches(root, patterns, excluded)
    assert public_hits <= signatures
    print("Public audit complete; checking private local history without publishing its identity.", flush=True)
    private_hits = matches(private, patterns, [])
    assert private_hits <= signatures
    rejected = public_hits | private_hits
    eligible = [row for row in proposals if row["operand"].split()[1] not in rejected]
    report = {"experiment": "h1623_fixed_candidate_freshness", "state": "AUDITED_PROPOSALS_NOT_FROZEN",
              "proposed_operands": len(proposals), "eligible_operands": len(eligible),
              "proposed_kinds": dict(Counter(row["kind"] for row in proposals)),
              "eligible_kinds": dict(Counter(row["kind"] for row in eligible)), "eligible": eligible,
              "freshness": {"rejected_public_significands": len(public_hits), "rejected_private_significands": len(private_hits),
                            "rejected_union_significands": len(rejected), "selected_public_collisions": 0,
                            "selected_private_collisions": 0, "compressed_files_searched": True,
                            "private_files_examined": sum(p.is_file() for p in private.rglob("*")),
                            "private_identity_or_contents_published": False,
                            "software_only_public_directory_exceptions": list(SOFTWARE_DIRECTORIES)},
              "hardware_execution": "none", "manifest_frozen": False,
              "claim_boundary": "Conservative repository/private visible-signature freshness, not proof that every prior capture in the world is available locally. Revalidate before execution; one observation per fresh tuple only.",
              "sha256": {"script": digest(Path(__file__)), "source_bank": BANK_SHA, "patterns": digest(patterns)}}
    with (output / "report.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True); target.write("\n")
    print(json.dumps({"eligible": report["eligible_kinds"], "freshness": report["freshness"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
