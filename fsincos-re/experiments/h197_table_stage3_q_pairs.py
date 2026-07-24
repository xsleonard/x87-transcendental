#!/usr/bin/env python3
"""Apply h192's latent-pair gate to wide-Q Horner stage 3.

The standalone terminal-Q coefficient remains away64 while paired FSINCOS
retains native RN67.  The wrapper reuses h192's joint-lane gates after
moving both its target-stage global and h191's shared override label to 3.
"""

from __future__ import annotations

import h191_table_penultimate_p_pairs as h191

h191.STAGE = 3

import h192_table_penultimate_q_pairs as h192


def main() -> None:
    h192.STAGE = 3
    h192.main()


if __name__ == "__main__":
    main()
