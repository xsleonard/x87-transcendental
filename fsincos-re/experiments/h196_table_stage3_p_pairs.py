#!/usr/bin/env python3
"""Apply h191's latent-pair gate to wide-P Horner stage 3.

The terminal stage-5 route remains Round 35 and stage 4 remains the current
RN67/RN64 schedule rejected by h191.  This wrapper deliberately reuses the
same 3,960-schedule enumeration, deterministic samples, residual controls,
and complete joint-lane gates so only the target stage changes.
"""

from __future__ import annotations

import h191_table_penultimate_p_pairs as h191


def main() -> None:
    h191.STAGE = 3
    h191.main()


if __name__ == "__main__":
    main()
