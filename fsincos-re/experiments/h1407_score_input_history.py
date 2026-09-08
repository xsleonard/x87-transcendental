#!/usr/bin/env python3
"""Score an immutable FCOS input-history discriminator or control bank."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def parse_hardware(path: Path) -> list[dict[str, str]]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        fields = {}
        for token in line.split():
            key, separator, value = token.partition("=")
            if not separator:
                raise RuntimeError(f"{path}:{line_number}: bad token {token!r}")
            fields[key.lower()] = value.lower()
        expected = {
            "case", "mode", "variant", "operand", "producer_sw",
            "result", "after_sw",
        }
        if set(fields) != expected:
            raise RuntimeError(
                f"{path}:{line_number}: fields {sorted(fields)} != {sorted(expected)}"
            )
        rows.append(fields)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("hardware", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()
    score_path = args.output_prefix.with_name(args.output_prefix.name + "_score.tsv")
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.txt")
    for path in (score_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    with args.manifest.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    hardware = parse_hardware(args.hardware)
    if len(rows) != len(hardware):
        raise RuntimeError(
            f"row count mismatch: {len(rows)} != {len(hardware)}"
        )

    counts = Counter()
    results_by_leg = defaultdict(set)
    for row, observed in zip(rows, hardware):
        operand = row["operand"].replace(" ", ":").lower()
        expected_identity = (
            row["case_id"].lower(), row["target_mode"].lower(),
            row["producer"].lower(), operand,
        )
        actual_identity = (
            observed["case"], observed["mode"], observed["variant"],
            observed["operand"],
        )
        if actual_identity != expected_identity:
            raise RuntimeError(
                f"identity mismatch {actual_identity} != {expected_identity}"
            )

        producer_sw = int(observed["producer_sw"], 16)
        producer_pe = int(bool(producer_sw & 0x20))
        producer_c1 = int(bool(producer_sw & 0x0200))
        expected_pe = int(row["producer"] != "add_zero")
        expected_c1 = int(row["producer"] == "add_minus_quarter")
        producer_verdict = (
            "EXACT" if (producer_pe, producer_c1) == (expected_pe, expected_c1)
            else "FAIL"
        )

        result = observed["result"]
        direct_match = result == row["known_direct_hardware"]
        current_match = result == row["current_model"]
        if direct_match and current_match:
            endpoint = "both"
        elif direct_match:
            endpoint = "direct_load_hardware"
        elif current_match:
            endpoint = "current_model"
        else:
            endpoint = "other"
        row["producer_sw"] = observed["producer_sw"]
        row["producer_pe"] = str(producer_pe)
        row["producer_c1"] = str(producer_c1)
        row["producer_status_verdict"] = producer_verdict
        row["history_result"] = result
        row["after_sw"] = observed["after_sw"]
        row["endpoint"] = endpoint
        row["changed_from_direct_load"] = str(not direct_match).lower()
        row["matches_current_model"] = str(current_match).lower()

        counts[f"producer.{row['producer']}.status.{producer_verdict}"] += 1
        counts[f"producer.{row['producer']}.endpoint.{endpoint}"] += 1
        counts[f"mode.{row['target_mode']}.endpoint.{endpoint}"] += 1
        counts[f"all.endpoint.{endpoint}"] += 1
        results_by_leg[row["target_mode"], row["operand"]].add(result)

    variant_agreement = sum(len(values) == 1 for values in results_by_leg.values())
    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    with report_path.open("x") as target:
        target.write(f"manifest_sha256\t{sha256(args.manifest)}\n")
        target.write(f"hardware_sha256\t{sha256(args.hardware)}\n")
        target.write(f"score_sha256\t{sha256(score_path)}\n")
        target.write("capture_policy\tone_execution_per_frozen_history_context\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"frontier_legs\t{len(results_by_leg)}\n")
        target.write(f"variant_agreement_legs\t{variant_agreement}\n")
        target.write("direct_load_baseline\tfrozen_not_recaptured\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")

        target.write("\n[per-leg results]\n")
        target.write(
            "mode\toperand\tdirect_load_hardware\tcurrent_model\t"
            "arithmetic_producer_result\n"
        )
        seen = set()
        for row in rows:
            key = row["target_mode"], row["operand"]
            if key in seen:
                continue
            seen.add(key)
            values = results_by_leg[key]
            rendered = next(iter(values)) if len(values) == 1 else ",".join(sorted(values))
            target.write(
                f"{key[0]}\t{key[1]}\t{row['known_direct_hardware']}\t"
                f"{row['current_model']}\t{rendered}\n"
            )

    print(
        f"wrote {score_path} and {report_path}: rows={len(rows)} "
        f"variant_agreement={variant_agreement}/{len(results_by_leg)} "
        f"current={counts['all.endpoint.current_model']} "
        f"direct={counts['all.endpoint.direct_load_hardware']} "
        f"other={counts['all.endpoint.other']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
