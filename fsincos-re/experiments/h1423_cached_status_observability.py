#!/usr/bin/env python3
"""Audit every cached h1406/h1408/h1410/h1412 FCOS status word.

The early residual plan listed the x87 precision exception and remaining
status bits as possible observables.  The later history/provenance campaigns
already captured a full post-FCOS status word for every execution, but h1414
scored only their result endpoints.  This script reconciles those immutable
raw rows with h1414 and inventories all status bits without executing x87.

The status word is architectural, so this is an observability audit rather
than a selector fit.  C1 is reported separately because h1419 already proves
that it cannot distinguish the two R59 carries on any result-neutral row.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


CAMPAIGNS = ("h1406", "h1408", "h1410", "h1412")
STATUS_BITS = {
    0: "IE",
    1: "DE",
    2: "ZE",
    3: "OE",
    4: "UE",
    5: "PE",
    6: "SF",
    7: "ES",
    8: "C0",
    9: "C1",
    10: "C2",
    14: "C3",
    15: "B",
}
TOP_MASK = 0x3800
PE_MASK = 0x0020
C1_MASK = 0x0200


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_score(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError(f"empty corrected score: {path}")
    campaigns = {row["campaign"] for row in rows}
    if campaigns != set(CAMPAIGNS):
        raise RuntimeError(f"unexpected campaigns: {sorted(campaigns)}")
    return rows


def parse_raw(path: Path) -> dict[str, dict[str, str]]:
    rows = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        fields = {}
        for token in line.split():
            key, separator, value = token.partition("=")
            if not separator:
                raise RuntimeError(f"{path}:{line_number}: bad token {token!r}")
            fields[key.lower()] = value.lower()
        required = {"case", "mode", "operand", "result", "after_sw"}
        missing = required - set(fields)
        if missing:
            raise RuntimeError(f"{path}:{line_number}: missing {sorted(missing)}")
        case_id = fields["case"]
        if case_id in rows:
            raise RuntimeError(f"{path}: duplicate case {case_id}")
        rows[case_id] = fields
    return rows


def read_branches(path: Path) -> dict[str, str]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    branches = {row["op"]: row["branch"] for row in rows}
    # h1386 intentionally excludes this separately tracked R1270/R59 row.
    branches["3ffc d0d000000cc0b3f8"] = "tie"
    return branches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    for campaign in CAMPAIGNS:
        parser.add_argument(f"--{campaign}", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    score = read_score(args.score)
    branches = read_branches(args.features)
    raw_paths = {campaign: getattr(args, campaign) for campaign in CAMPAIGNS}
    raw = {campaign: parse_raw(path) for campaign, path in raw_paths.items()}
    expected_counts = Counter(row["campaign"] for row in score)
    actual_counts = Counter({campaign: len(rows) for campaign, rows in raw.items()})
    if expected_counts != actual_counts:
        raise RuntimeError(
            f"raw/corrected campaign counts differ: {actual_counts} != {expected_counts}"
        )

    status_counts = Counter()
    bit_counts = Counter()
    population_counts = Counter()
    groups = defaultdict(Counter)
    details = []
    for row in score:
        campaign = row["campaign"]
        case_id = row["case_id"].lower()
        observed = raw[campaign].get(case_id)
        if observed is None:
            raise RuntimeError(f"missing raw identity {campaign}/{case_id}")
        expected_operand = row["operand"].replace(" ", ":").lower()
        identity = (observed["mode"], observed["operand"], observed["result"])
        expected_identity = (
            row["mode"].lower(), expected_operand, row["observed"].replace(" ", ":").lower()
        )
        if identity != expected_identity:
            raise RuntimeError(
                f"identity mismatch {campaign}/{case_id}: {identity} != {expected_identity}"
            )
        operand = row["operand"].lower()
        if operand not in branches:
            raise RuntimeError(f"missing R59 branch for {operand}")
        status = int(observed["after_sw"], 16)
        top = (status & TOP_MASK) >> 11
        flags = status & ~TOP_MASK
        residual_flags = flags & ~(PE_MASK | C1_MASK)
        status_counts[status] += 1
        population_counts[row["population"], flags] += 1
        for bit, name in STATUS_BITS.items():
            bit_counts[name] += (status >> bit) & 1
        label = "POS" if row["population"] == "frontier" else "NEG"
        groups[branches[operand], row["mode"], flags][label] += 1
        details.append((
            campaign, row["case_id"], row["population"], row["mode"],
            operand, branches[operand], f"{status:04x}", top,
            int(bool(status & PE_MASK)), int(bool(status & C1_MASK)),
            f"{residual_flags:04x}",
        ))

    if sum(status_counts.values()) != len(score):
        raise AssertionError("status accounting mismatch")
    mixed = [
        (key, counts) for key, counts in groups.items()
        if counts["POS"] and counts["NEG"]
    ]
    non_top_values = sorted(status & ~TOP_MASK for status in status_counts)
    residual_union = 0
    for status in status_counts:
        residual_union |= status & ~(TOP_MASK | PE_MASK | C1_MASK)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"score_sha256\t{digest(args.score)}\n")
        output.write(f"features_sha256\t{digest(args.features)}\n")
        for campaign in CAMPAIGNS:
            output.write(f"{campaign}_sha256\t{digest(raw_paths[campaign])}\n")
        output.write("hardware_policy\timmutable_cached_observations_no_x87_execution\n")
        output.write("claim_boundary\tarchitectural_x87_status_word_only\n")
        output.write(f"observations\t{len(score)}\n")
        output.write(f"frontier_observations\t{sum(row['population'] == 'frontier' for row in score)}\n")
        output.write(f"control_observations\t{sum(row['population'] != 'frontier' for row in score)}\n")
        output.write("post_top_values\t" + ",".join(
            str((status & TOP_MASK) >> 11) for status in sorted(status_counts)
        ) + "\n")
        output.write("non_top_status_values\t" + ",".join(
            f"{value:04x}" for value in non_top_values
        ) + "\n")
        output.write(f"status_bits_outside_PE_C1_union\t{residual_union:04x}\n")
        output.write("new_status_observable\tNONE\n")
        output.write("reason\tPE_constant_one_and_only_other_varying_bit_is_C1\n")

        output.write("\n[status values]\n")
        output.write("status\trows\n")
        for status, count in sorted(status_counts.items()):
            output.write(f"{status:04x}\t{count}\n")
        output.write("\n[set-bit counts]\n")
        output.write("bit\trows_set\n")
        for name in STATUS_BITS.values():
            output.write(f"{name}\t{bit_counts[name]}\n")
        output.write("\n[population by non-TOP status]\n")
        output.write("population\tflags\trows\n")
        for (population, flags), count in sorted(population_counts.items()):
            output.write(f"{population}\t{flags:04x}\t{count}\n")
        output.write("\n[branch-mode-status mixed-label collisions]\n")
        output.write("branch\tmode\tflags\tpositive\tnegative\n")
        for (branch, mode, flags), counts in sorted(mixed):
            output.write(
                f"{branch}\t{mode}\t{flags:04x}\t"
                f"{counts['POS']}\t{counts['NEG']}\n"
            )
        output.write("\n[reconciled rows]\n")
        output.write(
            "campaign\tcase\tpopulation\tmode\toperand\tbranch\t"
            "after_sw\ttop\tpe\tc1\tother_status_bits\n"
        )
        for detail in details:
            output.write("\t".join(map(str, detail)) + "\n")

    print(
        f"wrote {args.report}: rows={len(score)} statuses={len(status_counts)} "
        f"PE={bit_counts['PE']} C1={bit_counts['C1']} "
        f"other_union=0x{residual_union:04x} mixed={len(mixed)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
