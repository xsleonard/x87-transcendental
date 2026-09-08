#!/usr/bin/env python3
"""Generate and score fresh separators for h184's FIRC p-constant route.

h184 leaves one changed old-data survivor: materialize the ROM lookup
constant at 64 bits, round-to-nearest, before the shared cross*p product.
This generator is hardware-blind.  It also freezes chop/away/odd alternatives
so the new two-lane capture can select the routing mode rather than merely
compare the RN survivor with the current native-67-bit model.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import random
import sys

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h171_fsin_table_correction_discriminator as h171
import h182_table_joint_terminal_edges as h182
import h184_table_lookup_firc_routes as h184


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_lookup_firc_h185.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_table_lookup_firc_h185.meta.txt"
)
SEED = 0xF185C5
CANDIDATES = tuple(
    h184.Candidate(p_product=f"{mode}64")
    for mode in ("rn", "chop", "away", "odd")
)


def profile(
    point: h184.Point, candidate: h184.Candidate
) -> tuple[tuple[tuple[tuple[int, int], bool], ...], ...]:
    return tuple(
        tuple(
            (
                output := h58.x87_round(value, rc),
                h110.compare_magnitude(output, value) > 0,
            )
            for rc in h58.RCS
        )
        for value in h184.values(point, candidate)
    )


def difference_mask(left, right) -> int:
    mask = 0
    for lane, (old_lane, new_lane) in enumerate(
        zip(left, right)
    ):
        for index, (old, new) in enumerate(
            zip(old_lane, new_lane)
        ):
            bit = lane * 6 + index
            if old[0] != new[0]:
                mask |= 1 << bit
            if old[1] != new[1]:
                mask |= 1 << (bit + 3)
    return mask


def candidate_name(candidate: h184.Candidate) -> str:
    return candidate.p_product


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    per_candidate: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    rows = []
    meta = []
    counts: collections.Counter[str] = collections.Counter()
    states = set()
    strata: collections.Counter[tuple[str, str, int]] = (
        collections.Counter()
    )
    for scan_index in range(scan_limit):
        if scan_index and scan_index % 100_000 == 0:
            print(
                f"h185 scan={scan_index} "
                f"counts={dict(sorted(counts.items()))}",
                file=sys.stderr,
            )
        # h184's only changed survivor is confined to the direct wide
        # family.  Sampling that family directly avoids spending most of
        # the hardware-blind scan on expensive inactive reductions.
        se, sig = h135.direct_operand(rng, "wide")
        observed = h171.observed_from_input(scan_index, se, sig)
        if observed is None:
            continue
        key = (
            observed.source,
            observed.signed_n & 3,
            observed.point.cell,
            observed.point.a,
        )
        if key in states:
            continue
        blank = h182.Point(
            observed,
            ((0, 0),) * len(h58.RCS),
            (False,) * len(h58.RCS),
        )
        point = h184.prepare(blank)
        baseline = profile(point, h184.CURRENT)
        separated = []
        masks = []
        for candidate in CANDIDATES:
            name = candidate_name(candidate)
            if counts[name] >= per_candidate:
                continue
            mask = difference_mask(
                baseline, profile(point, candidate)
            )
            if mask:
                separated.append(candidate)
                masks.append(mask)
        if not separated:
            continue
        states.add(key)
        rows.append(f"{se:04x} {sig:016x}")
        labels = ",".join(
            f"{candidate_name(candidate)}:{mask:03x}"
            for candidate, mask in zip(separated, masks)
        )
        meta.append(
            f"{scan_index} {observed.source} "
            f"{observed.signed_n} {observed.point.cell} {labels}"
        )
        strata[
            observed.source, observed.family, observed.point.cell
        ] += 1
        for candidate in separated:
            counts[candidate_name(candidate)] += 1
        if all(
            counts[candidate_name(candidate)] >= per_candidate
            for candidate in CANDIDATES
        ):
            break
    missing = {
        candidate_name(candidate): counts[candidate_name(candidate)]
        for candidate in CANDIDATES
        if counts[candidate_name(candidate)] < per_candidate
    }
    if missing:
        raise SystemExit(
            f"h185 stopped after {scan_limit} scans; "
            f"incomplete={missing}"
        )
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(meta) + "\n")
    print(
        f"h185: selected {len(rows)} inputs from "
        f"{scan_index + 1} scans; "
        f"per-candidate={dict(sorted(counts.items()))}; "
        f"strata={dict(sorted(strata.items()))}; seed={SEED:#x}",
        file=sys.stderr,
    )


def load_capture(
    inputs: pathlib.Path, capture: pathlib.Path
) -> list[h184.Point]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    sine_modes = [
        (
            capture
            / f"constraint_table_lookup_firc_h185_fsin_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    pair_modes = [
        (
            capture
            / f"constraint_table_lookup_firc_h185_fsincos_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(
        len(lines) != len(operands)
        for lines in (*sine_modes, *pair_modes)
    ):
        raise SystemExit("h185 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        observed = h171.observed_from_input(index, se, sig)
        if observed is None:
            raise SystemExit(
                f"h185 input {index + 1} is not table-active"
            )
        sine_outputs = []
        sine_c1 = []
        cosine_outputs = []
        cosine_c1 = []
        for sine_lines, pair_lines in zip(
            sine_modes, pair_modes
        ):
            sine_fields = sine_lines[index].split()
            pair_fields = pair_lines[index].split()
            if (
                len(sine_fields) != 5
                or sine_fields[0] != "OK"
                or sine_fields[3] != "SW"
                or len(pair_fields) != 7
                or pair_fields[0] != "OK"
                or pair_fields[5] != "SW"
            ):
                raise ValueError(
                    (sine_lines[index], pair_lines[index])
                )
            sine_outputs.append(
                (int(sine_fields[1], 16), int(sine_fields[2], 16))
            )
            sine_c1.append(bool(int(sine_fields[4], 16) & 0x0200))
            cosine_outputs.append(
                (int(pair_fields[3], 16), int(pair_fields[4], 16))
            )
            cosine_c1.append(bool(int(pair_fields[6], 16) & 0x0200))
        joint = h182.Point(
            dataclasses.replace(
                observed,
                outputs=tuple(sine_outputs),
                c1=tuple(sine_c1),
            ),
            tuple(cosine_outputs),
            tuple(cosine_c1),
        )
        result.append(h184.prepare(joint))
    return result


def componentwise(value, baseline) -> bool:
    return all(
        all(new <= old for new, old in zip(new_lane, old_lane))
        for new_lane, old_lane in zip(value, baseline)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-candidate", type=int, default=16)
    parser.add_argument(
        "--scan-limit", type=int, default=30_000_000
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=DEFAULT_OUTPUT
    )
    parser.add_argument(
        "--metadata",
        type=pathlib.Path,
        default=DEFAULT_METADATA,
    )
    args = parser.parse_args()
    if args.generate:
        generate(
            args.output,
            args.metadata,
            args.per_candidate,
            args.scan_limit,
        )
    if args.score is not None:
        points = load_capture(args.output, args.score)
        metadata = args.metadata.read_text().splitlines()
        print(f"loaded {len(points)} fresh h185 separators")
        for candidate in CANDIDATES:
            name = candidate_name(candidate)
            targeted = [
                point
                for point, line in zip(points, metadata)
                if any(
                    item.split(":", 1)[0] == name
                    for item in line.split()[-1].split(",")
                )
            ]
            baseline = h184.score(targeted, h184.CURRENT)
            value = h184.score(targeted, candidate)
            status = (
                "PASS" if componentwise(value, baseline) else "FAIL"
            )
            print(
                f"{status} {name:6s} n={len(targeted):3d} "
                f"sine {baseline[0]}->{value[0]} "
                f"cosine {baseline[1]}->{value[1]}"
            )
    if not args.generate and args.score is None:
        parser.error("select --generate and/or --score CAPTURE_DIRECTORY")


if __name__ == "__main__":
    main()
