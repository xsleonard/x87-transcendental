#!/usr/bin/env python3
"""Reconstruct cached frontier FSINCOS rows in the paired producer frame.

Direct FCOS/FSINCOS output equality is not an internal-state isomorphism: the
paired cosine lane uses its own recovered polynomial schedule.  This script
parses h1417's already-existing one-shot observations, reconstructs the paired
terminal T with h624, and asks whether ordinary architectural rounding of
``1-T`` already explains the three-mode FSINCOS vector.

No candidate selector is fitted and no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from h437_gate_extraction import ROUNDING_MODES
from h624_paired_replica import paired_cos_T, refsp


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def parse_capture(path: Path) -> list[tuple[str, dict[str, int]]]:
    cases: list[tuple[str, dict[str, int]]] = []
    operand: str | None = None
    outputs: dict[str, int] = {}
    for raw in path.read_text().splitlines():
        if not raw or raw.startswith("["):
            continue
        key, _, value = raw.partition("\t")
        if key == "operand":
            if operand is not None and outputs:
                cases.append((operand, outputs))
            operand = value.replace(":", " ")
            outputs = {}
        elif key.startswith("fsincos_") and operand is not None:
            mode = key.removeprefix("fsincos_")
            fields = value.split()
            if len(fields) < 5 or fields[0] != "OK":
                raise RuntimeError(f"bad cached FSINCOS row: {value!r}")
            outputs[mode] = int(fields[4], 16)
    if operand is not None and outputs:
        cases.append((operand, outputs))
    for operand, outputs in cases:
        if set(outputs) != set(ROUNDING_MODES):
            raise RuntimeError(f"incomplete mode vector for {operand}: {outputs}")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    cases = parse_capture(args.capture)
    rows = []
    for operand, outputs in cases:
        exponent, significand = operand.split()
        terminal, correction_exponent, shift, discarded, sign = paired_cos_T(
            int(significand, 16)
        )
        predicted = {
            mode: refsp(terminal, correction_exponent, mode)
            for mode in ROUNDING_MODES
        }
        matches = predicted == outputs
        rows.append(
            (
                exponent,
                significand,
                terminal,
                correction_exponent,
                shift,
                discarded,
                (discarded << 8) >> shift,
                int(matches),
                outputs,
                predicted,
            )
        )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"capture_sha256\t{digest(args.capture)}\n")
        output.write("hardware_policy\tcached_one_shot_rows_only_no_x87_execution\n")
        output.write("candidate_policy\tpaired_producer_reconstruction_no_selector\n")
        output.write(f"cases\t{len(rows)}\n")
        output.write(f"ordinary_paired_matches\t{sum(row[7] for row in rows)}\n")
        output.write("\n[rows]\n")
        output.write(
            "operand\tpaired_T\tce\tshift\tdiscarded\tdiscard_top8\t"
            "z0_matches\thardware_rn_rd_ru\tpredicted_rn_rd_ru\n"
        )
        for (
            exponent,
            significand,
            terminal,
            correction_exponent,
            shift,
            discarded,
            top8,
            matches,
            outputs,
            predicted,
        ) in rows:
            hardware_vector = ",".join(
                f"{outputs[mode]:016x}" for mode in ROUNDING_MODES
            )
            predicted_vector = ",".join(
                f"{predicted[mode]:016x}" for mode in ROUNDING_MODES
            )
            output.write(
                f"{exponent} {significand}\t{terminal:x}\t"
                f"{correction_exponent}\t{shift}\t{discarded:x}\t{top8}\t"
                f"{matches}\t{hardware_vector}\t{predicted_vector}\n"
            )
        output.write("\n[bounded conclusion]\n")
        if all(row[7] for row in rows):
            output.write(
                "All covered FSINCOS vectors are ordinary z=0 results of the "
                "distinct paired producer.  Their equality or difference from "
                "FCOS does not expose the missing standalone R59 carry.\n"
            )
        else:
            output.write(
                "At least one covered FSINCOS vector is not explained by the "
                "ordinary paired producer and requires further localization.\n"
            )

    print(
        f"wrote {args.report}: cases={len(rows)} "
        f"ordinary_matches={sum(row[7] for row in rows)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
