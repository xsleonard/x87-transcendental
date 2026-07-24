#!/usr/bin/env python3
"""Freeze the post-Round-49 FSIN/FCOS/FSINCOS residual census."""

from __future__ import annotations

import argparse
import pathlib

import h239_round39_residual_census as h239


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    args = parser.parse_args()
    # h324 installs the complete Round-48 flag prefix only inside main, so
    # reproduce that immutable extension here and add the new arithmetic rule.
    h239.BASE_FLAGS = (
        *h239.BASE_FLAGS,
        "--round40-fsincos-tiny",
        "--round41-fsin-cosine-split",
        "--round42-p6-sine-split",
        "--round43-p6-sine-bias",
        "--round44-p6-sine-bias",
        "--round45-p6-sine-fraction",
        "--round46-p6-narrow-sine-fraction",
        "--round47-p6-narrow-sine-fraction",
        "--round48-p6-narrow-sine-fraction",
        "--round49-p6-carrier-interval",
    )
    h239.report(h239.collect(args.model))


if __name__ == "__main__":
    main()
