#!/usr/bin/env python3
"""Complete latent-pair exclusion at wide P/Q Horner stages 1 and 2.

h196-h197 exclude stage 3 after generalizing h191-h192 to replay intervening
current stages.  Only stages 1 and 2 remain: stage 0 materializes the initial
coefficient and has no local product/sum triple.  This driver applies the
same 3,960-schedule and joint-lane gates to one requested chain/stage so each
result is independently reproducible.
"""

from __future__ import annotations

import argparse

import h191_table_penultimate_p_pairs as h191
import h192_table_penultimate_q_pairs as h192


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=(1, 2), required=True)
    parser.add_argument("--chain", choices=("p", "q"), required=True)
    args = parser.parse_args()
    h191.STAGE = args.stage
    h192.STAGE = args.stage
    (h191.main if args.chain == "p" else h192.main)()


if __name__ == "__main__":
    main()
