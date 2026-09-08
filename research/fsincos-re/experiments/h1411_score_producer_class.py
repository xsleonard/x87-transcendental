#!/usr/bin/env python3
"""Score the immutable h1410 FCOS producer-class matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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
        raise RuntimeError(f"row count mismatch: {len(rows)} != {len(hardware)}")

    counts = Counter()
    values_by_variant_population = defaultdict(set)
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
        status_verdict = "EXACT" if (producer_pe, producer_c1) == (0, 0) else "FAIL"

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
        row["producer_status_verdict"] = status_verdict
        row["history_result"] = result
        row["after_sw"] = observed["after_sw"]
        row["endpoint"] = endpoint
        row["changed_from_direct_load"] = str(not direct_match).lower()
        row["matches_current_model"] = str(current_match).lower()

        prefix = f"{row['population']}.{row['producer']}"
        counts[f"{prefix}.status.{status_verdict}"] += 1
        counts[f"{prefix}.endpoint.{endpoint}"] += 1
        counts[f"{row['population']}.all.endpoint.{endpoint}"] += 1
        counts[f"producer.{row['producer']}.endpoint.{endpoint}"] += 1
        values_by_variant_population[row["producer"], row["population"]].add(endpoint)

    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    with report_path.open("x") as target:
        target.write(f"manifest_sha256\t{sha256(args.manifest)}\n")
        target.write(f"hardware_sha256\t{sha256(args.hardware)}\n")
        target.write(f"score_sha256\t{sha256(score_path)}\n")
        target.write("capture_policy\tone_execution_per_frozen_producer_context\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write("direct_load_and_fadd_only_baselines\tfrozen_not_recaptured\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")

        target.write("\n[uniformity]\n")
        for key in sorted(values_by_variant_population):
            endpoints = ",".join(sorted(values_by_variant_population[key]))
            target.write(f"{key[0]}\t{key[1]}\t{endpoints}\n")

        target.write("\n[per-row]\n")
        target.write(
            "population\tmode\toperand\tproducer\tdirect_load_hardware\t"
            "current_model\tresult\tendpoint\n"
        )
        for row in rows:
            target.write(
                f"{row['population']}\t{row['target_mode']}\t{row['operand']}\t"
                f"{row['producer']}\t{row['known_direct_hardware']}\t"
                f"{row['current_model']}\t{row['history_result']}\t"
                f"{row['endpoint']}\n"
            )

    print(
        f"wrote {score_path} and {report_path}: rows={len(rows)} "
        f"frontier-current={counts['frontier.all.endpoint.current_model']} "
        f"frontier-direct={counts['frontier.all.endpoint.direct_load_hardware']} "
        f"frontier-other={counts['frontier.all.endpoint.other']}",
        flush=True,
    )


if __name__ == "__main__":
    main()

