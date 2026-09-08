#!/usr/bin/env python3
"""Correct the h1406-h1413 model/hardware column inversion.

The h1378 suite miss format is:

    corpus instruction mode index operand MODEL HARDWARE

h1406 accidentally assigned those final two triples in the opposite order.
The opened manifests and raw hardware files remain immutable; this script
joins their identities back to h1378 and emits a corrected derived score.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_frontier(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    result = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        fields = line.split()
        if (
            len(fields) != 12
            or fields[1] != "cos"
            or fields[6] != "OK"
            or fields[9] != "OK"
        ):
            raise RuntimeError(f"{path}:{line_number}: unexpected miss row")
        key = fields[2].lower(), f"{fields[4].lower()} {fields[5].lower()}"
        if key in result:
            raise RuntimeError(f"{path}:{line_number}: duplicate frontier key")
        result[key] = {
            "model": f"{fields[7].lower()}:{fields[8].lower()}",
            "hardware": f"{fields[10].lower()}:{fields[11].lower()}",
        }
    if len(result) != 11:
        raise RuntimeError(f"expected 11 frontier legs, found {len(result)}")
    return result


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError(f"{path}: empty manifest")
    return rows


def read_hardware(path: Path) -> list[dict[str, str]]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        fields = {}
        for token in line.split():
            key, separator, value = token.partition("=")
            if not separator:
                raise RuntimeError(f"{path}:{line_number}: bad token {token!r}")
            fields[key.lower()] = value.lower()
        required = {"case", "mode", "variant", "operand", "result"}
        if not required.issubset(fields):
            raise RuntimeError(f"{path}:{line_number}: missing fields")
        rows.append(fields)
    return rows


def score_campaign(
    name: str,
    manifest_path: Path,
    hardware_path: Path,
    frontier: dict[tuple[str, str], dict[str, str]],
) -> tuple[list[dict[str, str]], Counter]:
    manifest = read_manifest(manifest_path)
    hardware = read_hardware(hardware_path)
    if len(manifest) != len(hardware):
        raise RuntimeError(f"{name}: row count mismatch")

    scored = []
    counts = Counter()
    for row, observed in zip(manifest, hardware):
        mode = row["target_mode"].lower()
        operand = row["operand"].lower()
        variant = row.get("producer", row.get("prelude", "")).lower()
        expected_identity = (
            row["case_id"].lower(), mode, variant, operand.replace(" ", ":"),
        )
        actual_identity = (
            observed["case"], observed["mode"], observed["variant"],
            observed["operand"],
        )
        if actual_identity != expected_identity:
            raise RuntimeError(
                f"{name}: identity mismatch {actual_identity} != {expected_identity}"
            )

        key = mode, operand
        if key in frontier:
            population = "frontier"
            corrected_model = frontier[key]["model"]
            corrected_hardware = frontier[key]["hardware"]
            manifest_inversion = (
                row["known_direct_hardware"].lower() == corrected_model
                and row["current_model"].lower() == corrected_hardware
            )
            if not manifest_inversion:
                raise RuntimeError(f"{name}: expected historical inversion for {key}")
            counts["frontier.manifest_labels_inverted"] += 1
        else:
            population = "same_carry_control"
            corrected_model = row["current_model"].lower()
            corrected_hardware = row["known_direct_hardware"].lower()
            if corrected_model != corrected_hardware:
                raise RuntimeError(f"{name}: unrecognized non-frontier row {key}")

        result = observed["result"]
        hardware_match = result == corrected_hardware
        model_match = result == corrected_model
        if hardware_match and model_match:
            endpoint = "both"
        elif hardware_match:
            endpoint = "hardware"
        elif model_match:
            endpoint = "model"
        else:
            endpoint = "other"
        counts[f"{population}.endpoint.{endpoint}"] += 1
        counts[f"variant.{variant}.{population}.endpoint.{endpoint}"] += 1
        scored.append({
            "campaign": name,
            "case_id": row["case_id"],
            "population": population,
            "mode": mode,
            "operand": operand,
            "variant": variant,
            "corrected_model": corrected_model,
            "corrected_hardware": corrected_hardware,
            "observed": result,
            "endpoint": endpoint,
        })
    return scored, counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontier_misses", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument(
        "campaign",
        nargs="+",
        help="NAME:MANIFEST:HARDWARE (paths must not contain colons)",
    )
    args = parser.parse_args()
    score_path = args.output_prefix.with_name(args.output_prefix.name + "_score.tsv")
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.txt")
    for path in (score_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    frontier = read_frontier(args.frontier_misses)
    campaign_specs = []
    for text in args.campaign:
        parts = text.split(":")
        if len(parts) != 3:
            raise SystemExit(f"bad campaign specification: {text}")
        campaign_specs.append((parts[0], Path(parts[1]), Path(parts[2])))

    all_rows = []
    all_counts = Counter()
    per_campaign = []
    for name, manifest, hardware in campaign_specs:
        rows, counts = score_campaign(name, manifest, hardware, frontier)
        all_rows.extend(rows)
        all_counts.update(counts)
        per_campaign.append((name, manifest, hardware, counts, len(rows)))

    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(all_rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(all_rows)

    with report_path.open("x") as target:
        target.write(f"frontier_misses_sha256\t{sha256(args.frontier_misses)}\n")
        target.write(f"score_sha256\t{sha256(score_path)}\n")
        target.write("correction\th1406_swapped_model_and_hardware_columns\n")
        target.write("capture_policy\timmutable_raw_files_rescored_no_hardware_execution\n")
        target.write(f"rows\t{len(all_rows)}\n")
        target.write("\n[campaigns]\n")
        target.write(
            "campaign\trows\tmanifest_sha256\thardware_sha256\t"
            "frontier_hardware\tfrontier_model\tfrontier_other\tcontrols_both\n"
        )
        for name, manifest, hardware, counts, row_count in per_campaign:
            target.write(
                f"{name}\t{row_count}\t{sha256(manifest)}\t{sha256(hardware)}\t"
                f"{counts['frontier.endpoint.hardware']}\t"
                f"{counts['frontier.endpoint.model']}\t"
                f"{counts['frontier.endpoint.other']}\t"
                f"{counts['same_carry_control.endpoint.both']}\n"
            )
        target.write("\n[totals]\n")
        for key, value in sorted(all_counts.items()):
            target.write(f"{key}\t{value}\n")

    print(
        f"wrote {score_path} and {report_path}: rows={len(all_rows)} "
        f"frontier-hardware={all_counts['frontier.endpoint.hardware']} "
        f"frontier-model={all_counts['frontier.endpoint.model']} "
        f"frontier-other={all_counts['frontier.endpoint.other']} "
        f"controls-both={all_counts['same_carry_control.endpoint.both']}",
        flush=True,
    )


if __name__ == "__main__":
    main()

