#!/usr/bin/env python3
"""Validate the standalone FSIN C model over the structured full-range sweep."""

from __future__ import annotations

import argparse
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "sweep_inputs.txt"
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h110"
FSINCOS_RN = (
    ROOT / "capture-kit-captures" / "pentiumII" / "sweep_rn.txt"
)
SEGMENTS = (
    ("quick-small", 0, 4000),
    ("quick-normal", 4000, 10000),
    ("moderate", 10000, 26000),
    ("moderate-near", 26000, 34000),
    ("large", 34000, 44000),
    ("large-near", 44000, 50000),
    ("boundaries", 50000, 50038),
)


def value(line: str) -> tuple[str, ...]:
    fields = line.split()
    if fields[0] == "C2":
        return ("C2",)
    if fields[0] != "OK":
        raise ValueError(line)
    return "OK", fields[1], fields[2]


def ulp_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int | None:
    """Return the x87-significand distance when both finite values align."""
    if left[0] != "OK" or right[0] != "OK":
        return 0 if left == right else None
    left_se, right_se = int(left[1], 16), int(right[1], 16)
    left_sig, right_sig = int(left[2], 16), int(right[2], 16)
    if (left_se >> 15) != (right_se >> 15):
        return None
    left_exp, right_exp = left_se & 0x7FFF, right_se & 0x7FFF
    if left_exp == right_exp:
        return abs(left_sig - right_sig)
    if left_exp + 1 == right_exp:
        return (0xFFFFFFFFFFFFFFFF - left_sig) + (
            right_sig - 0x8000000000000000
        ) + 1
    if right_exp + 1 == left_exp:
        return (0xFFFFFFFFFFFFFFFF - right_sig) + (
            left_sig - 0x8000000000000000
        ) + 1
    return None


def fsincos_sine(line: str) -> tuple[str, ...]:
    fields = line.split()
    if fields[0] == "C2":
        return ("C2",)
    if fields[0] != "OK":
        raise ValueError(line)
    return "OK", fields[1], fields[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    parser.add_argument(
        "--shared",
        action="store_true",
        help="score the existing FSINCOS-shared sine path",
    )
    parser.add_argument(
        "--p6-four-term",
        action="store_true",
        help="enable the four-term all-cell table model",
    )
    args = parser.parse_args()
    inputs = INPUTS.read_text()
    all_mode_misses = 0
    all_input_misses: set[int] = set()
    max_ulp = 0
    model_rn: list[str] = []
    for rc in ("rn", "rd", "ru"):
        command = [
            str(args.model.resolve()),
            "--batch",
            "--fsin-shared" if args.shared else "--fsin-standalone",
            "--round18-poly",
            "--round21-table-bias",
            "--round23-narrow-coefficient",
            "--round24-table-delta-rn67",
            "--round29-p5-fmul-route",
            "--round30-fsin-cosine-square",
            "--round31-fsin-cosine-tail",
            "--round32-fsin-cosine-horner",
            "--round33-fsin-cosine-product",
            "--round34-table-lookup-firc",
            "--round35-table-p-terminal",
        ]
        if args.p6_four_term:
            command.append("--round37-p6-four-term")
        if rc != "rn":
            command.append(f"--rc={rc}")
        actual = subprocess.run(
            command,
            input=inputs,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        if rc == "rn":
            model_rn = actual
        expected = (
            CAPTURE / f"sweep_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        print(rc)
        for name, start, end in SEGMENTS:
            misses = sum(
                value(actual[index]) != value(expected[index])
                for index in range(start, end)
            )
            print(f"  {name:14s} {misses}/{end - start}")
        for index, (left, right) in enumerate(zip(actual, expected)):
            if value(left) != value(right):
                all_mode_misses += 1
                all_input_misses.add(index)
                distance = ulp_distance(value(left), value(right))
                if distance is None:
                    raise SystemExit(
                        f"non-adjacent mismatch at {rc} input {index}: "
                        f"{left!r} != {right!r}"
                    )
                max_ulp = max(max_ulp, distance)

    print(
        f"combined model: {all_mode_misses}/{3 * 50038} mode results, "
        f"{len(all_input_misses)}/50038 inputs differ; "
        f"maximum error {max_ulp} ulp"
    )

    if FSINCOS_RN.exists():
        standalone = (
            CAPTURE / "sweep_fsin_rn_status.txt"
        ).read_text().splitlines()
        sincos = FSINCOS_RN.read_text().splitlines()
        differences = 0
        model_matches_fsin = 0
        model_matches_fsincos = 0
        segment_differences = []
        for name, start, end in SEGMENTS:
            count = sum(
                value(standalone[index]) != fsincos_sine(sincos[index])
                for index in range(start, end)
            )
            differences += count
            segment_differences.append(f"{name}={count}")
        for index, (fsin_line, fsincos_line) in enumerate(
            zip(standalone, sincos)
        ):
            fsin_value = value(fsin_line)
            fsincos_value = fsincos_sine(fsincos_line)
            if fsin_value == fsincos_value:
                continue
            model_value = value(model_rn[index])
            model_matches_fsin += model_value == fsin_value
            model_matches_fsincos += model_value == fsincos_value
        print(
            f"standalone FSIN RN versus PII/Skylake FSINCOS sine: "
            f"{differences}/50038 differ "
            f"({', '.join(segment_differences)})"
        )
        print(
            f"  model on those instruction divergences: "
            f"FSIN={model_matches_fsin}, FSINCOS={model_matches_fsincos}, "
            f"neither={differences - model_matches_fsin - model_matches_fsincos}"
        )


if __name__ == "__main__":
    main()
