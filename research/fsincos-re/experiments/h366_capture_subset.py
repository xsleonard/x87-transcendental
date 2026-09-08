#!/usr/bin/env python3
"""Extract aligned input and RN/RD/RU capture rows for focused scoring."""

from __future__ import annotations

import argparse
import pathlib


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("output_inputs", type=pathlib.Path)
    parser.add_argument("output_directory", type=pathlib.Path)
    parser.add_argument("output_stem")
    parser.add_argument("--index", action="append", type=int, required=True)
    args = parser.parse_args()

    input_lines = args.inputs.read_text().splitlines()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    args.output_inputs.write_text(
        "\n".join(input_lines[index] for index in args.index) + "\n"
    )
    for mode in ("rn", "rd", "ru"):
        capture_lines = (
            args.capture_directory / f"{args.capture_stem}_{mode}_status.txt"
        ).read_text().splitlines()
        (
            args.output_directory / f"{args.output_stem}_{mode}_status.txt"
        ).write_text(
            "\n".join(capture_lines[index] for index in args.index) + "\n"
        )
    print(f"wrote {len(args.index)} aligned rows")


if __name__ == "__main__":
    main()
