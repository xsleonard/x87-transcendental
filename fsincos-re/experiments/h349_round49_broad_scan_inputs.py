#!/usr/bin/env python3
"""Generate a deterministic million-input table-path validation scan.

The corpus is balanced across direct/reduced and narrow/wide entry paths.
Signs, reduced quadrants, table cells, and low significand bits are otherwise
sampled independently.  It is hardware-blind and intentionally independent
of the structured and dense corpora used to derive Round 49.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import random

import h80_round21_parity as h80
import h135_fsin_table_terminal_discriminator as h135


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "round49_broad_scan_h349.txt"
)
DEFAULT_METADATA = DEFAULT_OUTPUT.with_suffix(".meta.txt")
SEED = 0xF349C4A7
CLASSES = (
    ("direct", "narrow"),
    ("direct", "wide"),
    ("reduced", "narrow"),
    ("reduced", "wide"),
)


def random_reduced(rng: random.Random, family: str):
    while True:
        exponent = rng.randrange(0, 63)
        se = (rng.getrandbits(1) << 15) | (exponent + 16383)
        sig = rng.randrange(1 << 63, 1 << 64)
        active = h80.active_table_input(se, sig)
        if active is None or not active[2]:
            continue
        actual_family = "wide" if active[1].wide else "narrow"
        if actual_family == family:
            return se, sig, active


def generated(count: int):
    rng = random.Random(SEED)
    quotas = {
        key: count // len(CLASSES) + int(index < count % len(CLASSES))
        for index, key in enumerate(CLASSES)
    }
    remaining = dict(quotas)
    seen = set()
    rows = []
    strata = collections.Counter()
    scans = collections.Counter()
    while any(remaining.values()):
        for source, family in CLASSES:
            key = source, family
            if not remaining[key]:
                continue
            scans[key] += 1
            if source == "direct":
                se, sig = h135.direct_operand(rng, family)
                active = h80.active_table_input(se, sig)
                if active is None or active[2]:
                    raise AssertionError((key, se, sig, active))
            else:
                se, sig, active = random_reduced(rng, family)
            if (se, sig) in seen:
                continue
            seen.add((se, sig))
            remaining[key] -= 1
            rows.append((se, sig))
            signed_n, point, reduced = active
            strata[
                source,
                family,
                point.cell,
                signed_n & 3,
                se >> 15,
            ] += 1
    return rows, quotas, scans, strata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args()
    if args.count < len(CLASSES):
        raise SystemExit(f"count must be at least {len(CLASSES)}")

    rows, quotas, scans, strata = generated(args.count)
    args.output.write_text(
        "".join(f"{se:04x} {sig:016x}\n" for se, sig in rows)
    )
    cell_counts = collections.Counter()
    for (source, family, cell, _, _), value in strata.items():
        cell_counts[source, family, cell] += value
    metadata = [
        "# hardware-blind Round-49 broad table scan",
        f"# seed={SEED:#x} rows={len(rows)}",
        "# path quotas/scans:",
        *(
            f"# {source}/{family} rows={quotas[source, family]} "
            f"draws={scans[source, family]}"
            for source, family in CLASSES
        ),
        "# cell counts:",
        *(
            f"# {source}/{family}/cell{cell}={value}"
            for (source, family, cell), value in sorted(cell_counts.items())
        ),
    ]
    args.metadata.write_text("\n".join(metadata) + "\n")
    print(
        f"h349 wrote {len(rows)} inputs; "
        + " ".join(
            f"{source}/{family}={quotas[source, family]}"
            for source, family in CLASSES
        )
    )


if __name__ == "__main__":
    main()
