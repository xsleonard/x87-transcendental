#!/usr/bin/env python3
"""Generate dense x87 neighborhoods around all structured Round-49 misses.

Every affected structured operand is surrounded by adjacent significands and
logarithmically spaced controls.  Sign mirrors test whether the hidden
carry/borrow choice follows magnitude state, while the original operands are
retained as positive controls.  Selection uses only the frozen model and
already-captured structured corpus; no new processor outputs are consulted.
"""

from __future__ import annotations

import argparse
import collections
import pathlib

import h171_fsin_table_correction_discriminator as h171
import h346_round49_residual_inventory as h346


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" /
    "constraint_round49_residual_neighbors_h347.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")


def seeds():
    _, records = h346.inventory("sweep")
    grouped = collections.defaultdict(list)
    for record in records:
        grouped[record.se, record.sig].append(record)
    return tuple(sorted(grouped.items()))


def offsets(radius: int, log_bits: int):
    result = set(range(-radius, radius + 1))
    for bit in range(log_bits):
        value = 1 << bit
        result.add(-value)
        result.add(value)
    return tuple(sorted(result))


def generated(radius: int, log_bits: int, sign_mirror: bool):
    result = set()
    for (se, sig), _ in seeds():
        signs = (se, se ^ 0x8000) if sign_mirror else (se,)
        for candidate_se in signs:
            for delta in offsets(radius, log_bits):
                candidate_sig = sig + delta
                if not (1 << 63) <= candidate_sig < (1 << 64):
                    continue
                observed = h171.observed_from_input(
                    len(result), candidate_se, candidate_sig
                )
                if observed is None:
                    continue
                result.add((candidate_se, candidate_sig))
    return tuple(sorted(result))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    parser.add_argument("--radius", type=int, default=4096)
    parser.add_argument("--log-bits", type=int, default=32)
    parser.add_argument(
        "--no-sign-mirror", action="store_true",
        help="capture only the original operand signs",
    )
    args = parser.parse_args()
    if args.radius < 0 or args.log_bits < 0 or args.log_bits > 63:
        raise SystemExit("radius/log-bits outside supported range")

    selected_seeds = seeds()
    rows = generated(args.radius, args.log_bits, not args.no_sign_mirror)
    args.output.write_text(
        "".join(f"{se:04x} {sig:016x}\n" for se, sig in rows)
    )
    metadata = [
        "# hardware-blind Round-49 residual neighborhoods",
        f"# radius={args.radius} log_bits={args.log_bits} "
        f"sign_mirror={int(not args.no_sign_mirror)}",
        f"# seeds={len(selected_seeds)} rows={len(rows)}",
        "# seed columns: input result-observations c1-observations",
    ]
    for (se, sig), records in selected_seeds:
        metadata.append(
            f"{se:04x} {sig:016x} "
            f"result={sum(bool(record.direction) for record in records)} "
            f"c1={sum(record.c1_mismatch for record in records)}"
        )
    args.metadata.write_text("\n".join(metadata) + "\n")
    print(
        f"h347 wrote {len(rows)} inputs around {len(selected_seeds)} seeds "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
