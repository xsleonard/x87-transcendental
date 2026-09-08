#!/usr/bin/env python3
"""Verify H1621 replay results, permitting only disclosed Mach-O metadata."""
import argparse
import json
from pathlib import Path

from h1618_verify_replay import digest, macho_metadata_ranges


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("replay", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    helper = Path(__file__).with_name("h1618_verify_replay.py")
    assert digest(helper) == "639ba25c659db2987a0263ff370b730c1078f1f8bb835b1f714e3cfa9cedd6ab"
    first = json.loads((args.original / "report.json").read_text())
    second = json.loads((args.replay / "report.json").read_text())
    differences = {}
    for name, build in first["build_checks"].items():
        old_hash, new_hash = build["binary_sha256"], second["build_checks"][name]["binary_sha256"]
        if old_hash == new_hash:
            continue
        a, b = args.original / name, args.replay / name
        assert digest(a) == old_hash and digest(b) == new_hash
        left, right = a.read_bytes(), b.read_bytes()
        ranges = macho_metadata_ranges(left)
        assert len(left) == len(right) and ranges == macho_metadata_ranges(right)
        changed = [i for i, (x, y) in enumerate(zip(left, right)) if x != y]
        assert changed and all(any(start <= i < end for start, end in ranges) for i in changed)
        differences[name] = {"original_sha256": old_hash, "replay_sha256": new_hash,
                             "differing_bytes": len(changed), "allowed_metadata_ranges": ranges,
                             "all_other_bytes_identical": True}
        second["build_checks"][name]["binary_sha256"] = old_hash
    assert first == second
    report = {"experiment": "h1621_verify_replay", "status": "PASS",
              "all_non_binary_hash_report_fields_identical": True,
              "metadata_only_executable_variants": differences,
              "sha256": {"script": digest(Path(__file__)), "helper": digest(helper),
                         "original_report": digest(args.original / "report.json"),
                         "replay_report": digest(args.replay / "report.json")}}
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
