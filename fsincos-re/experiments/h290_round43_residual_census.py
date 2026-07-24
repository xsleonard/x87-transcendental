#!/usr/bin/env python3
"""Freeze the post-Round-43 FSIN/FCOS/FSINCOS residual census."""

from __future__ import annotations

import argparse
import pathlib

import h239_round39_residual_census as h239


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()
    h239.BASE_FLAGS = (
        *h239.BASE_FLAGS,
        "--round40-fsincos-tiny",
        "--round41-fsin-cosine-split",
        "--round42-p6-sine-split",
        "--round43-p6-sine-bias",
    )
    h239.report(h239.collect(args.model))


if __name__ == "__main__":
    main()
