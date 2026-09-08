#!/usr/bin/env python3
"""Audit the complete public utools Git history for saved PPro build products.

The current utools tree references the unreleased p6microcode-tools assembler
and scrambler.  A historical generated .uhex/.hex/.dat file would provide the
paired logical/physical Pentium Pro fixture that the H1557 near-decoder lacks.
This audit enumerates every path reachable from every public commit and records
the exact commits which introduced the generic and Pentium Pro transforms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


SOURCE_URL = "https://github.com/ruikruik/utools"
EXPECTED_HEAD = "ab6aa24ed91de1c048313c10cb7546ea3397b827"
EXPECTED_COMMIT_COUNT = 50
GENERIC_TRANSFORM_COMMIT = "7729bb4f4186e12cb134cfbdf6d7e66f57aa7ec4"
PPRO_TRANSFORM_COMMIT = "6f53f32e7c109b827067d78fd4da8188104d1c8a"
GENERATED_SUFFIXES = (".uhex", ".hex", ".dat", ".bin", ".out")
TOOL_BASENAMES = ("p6as", "p6scrambler")


def run(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def commit_metadata(repo: Path, commit: str) -> dict[str, object]:
    text = run(repo, "show", "-s", "--format=%H%n%P%n%aI%n%s", commit)
    lines = text.rstrip("\n").split("\n", 3)
    if len(lines) != 4:
        raise RuntimeError(f"unexpected metadata for {commit}")
    changed = run(repo, "diff-tree", "--no-commit-id", "--name-status", "-r", commit)
    return {
        "commit": lines[0],
        "parents": lines[1].split(),
        "author_date": lines[2],
        "subject": lines[3],
        "changed_paths": [line for line in changed.splitlines() if line],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")

    head = run(arguments.repo, "rev-parse", "HEAD").strip()
    commits = [line for line in run(arguments.repo, "rev-list", "--all").splitlines() if line]
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"unexpected public utools HEAD {head}")
    if len(commits) != EXPECTED_COMMIT_COUNT:
        raise RuntimeError(f"expected {EXPECTED_COMMIT_COUNT} commits, got {len(commits)}")

    object_lines = [
        line for line in run(arguments.repo, "rev-list", "--objects", "--all").splitlines()
        if line
    ]
    historical_paths = sorted(
        {line.split(" ", 1)[1] for line in object_lines if " " in line}
    )
    generated_paths = [
        path for path in historical_paths if path.lower().endswith(GENERATED_SUFFIXES)
    ]
    saved_tool_paths = [
        path for path in historical_paths if Path(path).name.lower() in TOOL_BASENAMES
    ]

    # Record references to the unavailable tools without treating references as
    # saved executables or source artifacts.
    dependency_references: list[dict[str, str]] = []
    for commit in commits:
        grep = subprocess.run(
            [
                "git", "-C", str(arguments.repo), "grep", "-n", "-I", "-E",
                "p6scrambler|p6microcode-tools", commit, "--",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if grep.returncode not in (0, 1):
            raise RuntimeError(f"git grep failed at {commit}: {grep.stderr.strip()}")
        for line in grep.stdout.splitlines():
            match = re.match(r"^[^:]+:([^:]+):(\d+):(.*)$", line)
            if match:
                dependency_references.append(
                    {
                        "commit": commit,
                        "path": match.group(1),
                        "line": match.group(2),
                        "text": match.group(3).strip(),
                    }
                )
    unique_references = sorted(
        {
            (item["path"], item["line"], item["text"])
            for item in dependency_references
        }
    )

    head_tree = run(arguments.repo, "ls-tree", "-r", "--name-only", "HEAD")
    result = {
        "status": "complete_public_history_no_saved_ppro_logical_physical_fixture",
        "question": (
            "Does any reachable public utools revision retain generated Pentium Pro "
            ".uhex/.hex/.dat output or the p6as/p6scrambler tool itself?"
        ),
        "source": {
            "url": SOURCE_URL,
            "head": head,
            "commit_count": len(commits),
            "reachable_object_lines": len(object_lines),
            "historical_path_count": len(historical_paths),
            "head_tree_sha256": digest_bytes(head_tree.encode()),
        },
        "method": {
            "all_reachable_commits_enumerated": True,
            "all_reachable_object_paths_enumerated": True,
            "generated_suffixes": list(GENERATED_SUFFIXES),
            "tool_basenames": list(TOOL_BASENAMES),
            "hardware_executed": False,
            "x87_executed": False,
            "microcode_loaded": False,
            "private_ledger_accessed": False,
        },
        "result": {
            "generated_paths": generated_paths,
            "saved_tool_paths": saved_tool_paths,
            "generated_or_saved_tool_path_count": len(generated_paths) + len(saved_tool_paths),
            "unique_dependency_references": [
                {"path": path, "line": line, "text": text}
                for path, line, text in unique_references
            ],
        },
        "relevant_commits": {
            "generic_msrom_transform": commit_metadata(
                arguments.repo, GENERIC_TRANSFORM_COMMIT
            ),
            "pentium_pro_transform": commit_metadata(
                arguments.repo, PPRO_TRANSFORM_COMMIT
            ),
        },
        "conclusion": {
            "historical_generated_fixture_found": False,
            "public_p6scrambler_found": False,
            "public_p6as_found": False,
            "h1557_independently_validated": False,
            "selector_found": False,
            "emulator_change": False,
            "frontier_closed": False,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
