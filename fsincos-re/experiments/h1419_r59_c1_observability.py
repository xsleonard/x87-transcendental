#!/usr/bin/env python3
"""Ask whether cached x87 C1 can disambiguate the two R59 endpoints.

The current R59 response bank uses architectural significands from all four
rounding modes.  A row remains neutral when carry=0 and carry=1 round to the
same four significands.  Existing status captures also contain x87 C1, which
reports whether the final significand was incremented.  This script checks
whether that already-cached observable could split any such neutral pair.

For each feature row the two hidden cosine values are reconstructed directly
from the exact subtractor identity

    retained = floor((S-B)/2^k) + borrow - 1 + carry
    hidden   = 1 - retained * 2^(rscale+k).

The reconstructed architectural results are first required to equal the
existing force-response columns for all four modes.  C1 is then computed by
exact integer comparison of each rounded result with its hidden value.  No
hardware is executed and no selector or predicate is fitted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

import h58_constraint_search as h58
from h110_fsin_standalone import compare_magnitude


MODES = ("rn", "rd", "ru", "rz")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError(f"empty input: {path}")
    return rows


def response_rows(paths: tuple[Path, ...]) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for path in paths:
        for row in read_rows(path):
            key = row["op"], row["mode"]
            if key in result:
                raise RuntimeError(f"duplicate response row {key}")
            result[key] = row
    return result


def hidden_for_carry(row: dict[str, str], carry: int) -> tuple[h58.FP, int, int]:
    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    cut = int(row["k"])
    mask = (1 << cut) - 1
    borrow = int((s_value & mask) < (b_value & mask))
    retained = (
        (int(row["umag"], 16) >> cut) + borrow - 1 + carry
    )
    exponent = int(row["rscale"]) + cut
    scale = min(0, exponent)
    magnitude = (
        (1 << -scale) - (retained << (exponent - scale))
    )
    if magnitude <= 0:
        raise RuntimeError(f"nonpositive hidden cosine for {row['op']}")
    return (0, magnitude, scale), borrow, retained


def rounded(hidden: h58.FP, mode: str) -> tuple[tuple[int, int], bool]:
    effective_mode = "rd" if mode == "rz" else mode
    output = h58.x87_round(hidden, effective_mode)
    c1 = compare_magnitude(output, hidden) > 0
    return output, c1


def render_output(output: tuple[int, int]) -> str:
    return f"{output[0]:04x}:{output[1]:016x}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_responses", type=Path)
    parser.add_argument("control_responses", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    features = read_rows(args.features)
    responses = response_rows(
        (args.positive_responses, args.control_responses)
    )
    if len({row["op"] for row in features}) != len(features):
        raise RuntimeError("feature bank must contain one row per operand")

    counts = Counter()
    neutral_signatures = Counter()
    separators = []
    for row in features:
        endpoint_vectors = []
        for carry in (0, 1):
            hidden, borrow, _ = hidden_for_carry(row, carry)
            vector = []
            for mode in MODES:
                key = row["op"], mode
                if key not in responses:
                    raise RuntimeError(f"missing response row {key}")
                output, c1 = rounded(hidden, mode)
                delta = borrow - 1 + carry
                force_column = f"f{delta + 3}"
                expected = responses[key][force_column].lower()
                actual = render_output(output)
                if actual != expected:
                    raise RuntimeError(
                        f"force-response mismatch {key} carry={carry}: "
                        f"{actual} != {expected}"
                    )
                counts[f"carry{carry}.c1.{int(c1)}"] += 1
                vector.append((output, c1))
            endpoint_vectors.append(tuple(vector))

        carry0, carry1 = endpoint_vectors
        output_neutral = all(
            left[0] == right[0] for left, right in zip(carry0, carry1)
        )
        c1_differs = any(
            left[1] != right[1] for left, right in zip(carry0, carry1)
        )
        counts["output_neutral" if output_neutral else "output_constraining"] += 1
        if output_neutral:
            counts["neutral_c1_separators"] += c1_differs
            signature = tuple(int(item[1]) for item in carry0)
            neutral_signatures[signature] += 1
            if c1_differs:
                separators.append((row["op"], carry0, carry1))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_responses", args.positive_responses),
            ("control_responses", args.control_responses),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tcached_response_columns_only_no_x87_execution\n")
        output.write("candidate_policy\texact_endpoint_reconstruction_no_selector\n")
        output.write("c1_definition\tfinal_rounded_magnitude_exceeds_hidden_magnitude\n")
        output.write(f"rows\t{len(features)}\n")
        output.write(f"output_constraining_rows\t{counts['output_constraining']}\n")
        output.write(f"output_neutral_rows\t{counts['output_neutral']}\n")
        output.write(
            f"neutral_rows_with_distinct_endpoint_c1\t"
            f"{counts['neutral_c1_separators']}\n"
        )
        output.write("force_response_reconstruction\tPASS\n")
        output.write("\n[neutral C1 signatures]\n")
        output.write("c1_rn_rd_ru_rz\trows\n")
        for signature, count in sorted(neutral_signatures.items()):
            output.write(",".join(map(str, signature)) + f"\t{count}\n")
        output.write("\n[endpoint C1 separators]\n")
        output.write("operand\tcarry0\tcarry1\n")
        for operand, carry0, carry1 in separators:
            output.write(
                f"{operand}\t"
                + ",".join(str(int(item[1])) for item in carry0)
                + "\t"
                + ",".join(str(int(item[1])) for item in carry1)
                + "\n"
            )
        output.write("\n[bounded conclusion]\n")
        if separators:
            output.write(
                "Cached C1 can in principle add R59 endpoint constraints on "
                "the listed output-neutral operands.\n"
            )
        else:
            output.write(
                "The two R59 endpoints have identical C1 on every operand "
                "whose four-mode architectural significands are identical. "
                "Cached standalone-FCOS C1 therefore adds no R59 carry "
                "constraint beyond the existing four-mode response bank.\n"
            )

    print(
        f"wrote {args.report}: rows={len(features)} "
        f"neutral={counts['output_neutral']} "
        f"c1_separators={counts['neutral_c1_separators']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
