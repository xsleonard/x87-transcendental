#!/usr/bin/env python3
"""Audit resolved post-subtraction block-confirmation signals at R59.

The h662 standalone-FCOS law is an independently blind-validated structural
precedent: when an equality/propagate run from the retained cut terminates at
the top of an 8-bit physical block, the selector reads one or two bits of the
*resolved difference* at the following block start.  That operation is not in
the candidate language of h1416/h1420/h1428, which summarizes carry relations
at or below the cut.  This pass first rechecks h662 on its discovery and blind
caches, then tests the omitted resolved-result family on the complete current
R59 wall.

For each source-bounded block width and every fixed absolute phase, the first
block start at least one block above the cut is

    bs = k + width + ((phase - (rscale + k)) mod width).

The candidate observes whether the S/B equality run terminates immediately
below ``bs``, and the resolved-result bits at ``k + width`` and ``bs``.  It
does so for the exact difference and the two literal carry-select endpoint
words (plus the already-selected and opposite words as diagnostic aliases).
Only the h662 confirmation equations and their elementary circuit components
are exposed; no operand threshold, identity key, learned tree, or learned
truth table is admitted.  Each signal is composed with the incumbent carry by
one global two-input Boolean gate.

All labels are immutable cached observations.  No x87 instruction is run.
"""

from __future__ import annotations

import argparse
import hashlib
import pickle
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import h1425_p5_public_mux_signals as h1425
from h1110_carry_gate_mine import GATE_NAMES


P5_PATENT = "US5257218A"
P5_PATENT_URL = "https://patents.google.com/patent/US5257218A/en"
P6_PATENT = "US20080133895A1"
P6_PATENT_URL = "https://patents.google.com/patent/US20080133895A1/en"
BLOCK_WIDTHS = (4, 8, 16, 32, 36, 64)
VARIANTS = ("exact", "carry0", "carry1", "incumbent", "opposite")
SIGNALS = (
    "critical",
    "entry",
    "block_start",
    "entry_and_block_start",
    "entry_or_block_start",
    "entry_xor_block_start",
    "up_confirm",
    "down_confirm",
    "theta_confirm",
    "critical_up_confirm",
    "critical_down_confirm",
    "critical_theta_confirm",
    "critical_up_reject",
    "critical_down_reject",
    "critical_theta_reject",
    "h662_fire_up",
    "h662_fire_down",
    "h662_fire_theta",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_cache(path: Path) -> list[tuple]:
    with path.open("rb") as source:
        rows = pickle.load(source)
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"unexpected h662 cache: {path}")
    if any(not isinstance(row, tuple) or len(row) != 9 for row in rows):
        raise RuntimeError(f"unexpected h662 row schema: {path}")
    return rows


def h662_prediction(row: tuple) -> int:
    sign, _theta, _fire, run, cut, phase, _scale, left, right = row
    critical = (run + phase) % 8 == 7 and run in (7, 8)
    if not critical:
        return 1
    magnitude = left - right
    block_start = cut + 8 + ((8 - phase) % 8)
    entry_bit = (magnitude >> (cut + 8)) & 1
    block_bit = (magnitude >> block_start) & 1
    return block_bit if sign == "up" else entry_bit & block_bit


def calibration(rows: list[tuple]) -> tuple[int, int, int]:
    errors = 0
    critical = 0
    for row in rows:
        sign, _theta, fire, run, _cut, phase, *_ = row
        if sign not in ("up", "dn"):
            raise RuntimeError(f"unexpected h662 direction: {sign}")
        critical += int((run + phase) % 8 == 7 and run in (7, 8))
        errors += h662_prediction(row) != fire
    return len(rows), critical, errors


def below_cut_collisions(rows: list[tuple]) -> tuple[int, int, int, tuple]:
    """Condition on every materialized input bit at/below the cut.

    h1416/h1428 consume a proper subset of this lower field.  h1420 also sees
    a leading-position anchor; that anchor is fixed by the normalized 67-bit
    result on these rows.  Mixed groups therefore demonstrate why the old
    below-cut languages cannot represent the known h662 confirmation law.
    """
    groups: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    critical_rows = 0
    for sign, theta, fire, run, cut, phase, scale, left, right in rows:
        if not ((run + phase) % 8 == 7 and run in (7, 8)):
            continue
        critical_rows += 1
        mask = (1 << (cut + 1)) - 1
        key = (
            sign, theta, cut, phase, scale,
            left & mask, right & mask,
        )
        groups[key][fire] += 1
    mixed = [(key, counts) for key, counts in groups.items() if all(counts)]
    mixed_rows = sum(sum(counts) for _, counts in mixed)
    example = mixed[0] if mixed else ()
    return critical_rows, len(mixed), mixed_rows, example


def equality_run(left: int, right: int, cut: int) -> int:
    equal = ~(left ^ right)
    run = 0
    while run < 128 and (equal >> (cut + run)) & 1:
        run += 1
    return run


def endpoint_word(
    magnitude: int,
    cut: int,
    borrow: int,
    incumbent: int,
    variant: str,
) -> int:
    unit = 1 << cut
    if variant == "exact":
        return magnitude
    if variant == "carry0":
        return magnitude + (borrow - 1) * unit
    if variant == "carry1":
        return magnitude + borrow * unit
    if variant == "incumbent":
        return magnitude + (borrow - 1 + incumbent) * unit
    if variant == "opposite":
        return magnitude + (borrow - incumbent) * unit
    raise ValueError(variant)


def signal_columns(
    states: list[tuple[int, int, int, int, int, bool, int]],
    width: int,
    phase: int,
    variant: str,
) -> dict[str, np.ndarray]:
    count = len(states)
    critical = np.empty(count, dtype=np.uint8)
    entry = np.empty(count, dtype=np.uint8)
    block = np.empty(count, dtype=np.uint8)
    direction_down = np.empty(count, dtype=np.uint8)
    for index, (
        magnitude, cut, scale, borrow, run, theta_down, incumbent
    ) in enumerate(states):
        block_position = (
            cut + width + ((phase - (scale + cut)) % width)
        )
        value = endpoint_word(
            magnitude, cut, borrow, incumbent, variant
        )
        critical[index] = run == block_position - cut - 1
        entry[index] = (value >> (cut + width)) & 1
        block[index] = (value >> block_position) & 1
        direction_down[index] = theta_down

    one = np.ones(count, dtype=np.uint8)
    entry_and_block = entry & block
    up_confirm = block
    down_confirm = entry_and_block
    theta_confirm = np.where(direction_down, down_confirm, up_confirm).astype(
        np.uint8
    )
    columns = {
        "critical": critical,
        "entry": entry,
        "block_start": block,
        "entry_and_block_start": entry_and_block,
        "entry_or_block_start": entry | block,
        "entry_xor_block_start": entry ^ block,
        "up_confirm": up_confirm,
        "down_confirm": down_confirm,
        "theta_confirm": theta_confirm,
        "critical_up_confirm": critical & up_confirm,
        "critical_down_confirm": critical & down_confirm,
        "critical_theta_confirm": critical & theta_confirm,
        "critical_up_reject": critical & (one ^ up_confirm),
        "critical_down_reject": critical & (one ^ down_confirm),
        "critical_theta_reject": critical & (one ^ theta_confirm),
        "h662_fire_up": (one ^ critical) | up_confirm,
        "h662_fire_down": (one ^ critical) | down_confirm,
        "h662_fire_theta": (one ^ critical) | theta_confirm,
    }
    if tuple(columns) != SIGNALS:
        raise RuntimeError("signal schema changed")
    return columns


def gate_score(
    column: np.ndarray,
    current: np.ndarray,
    required: np.ndarray,
    target: np.ndarray,
    gate: int,
) -> tuple[int, int, int, int, int]:
    table = np.asarray([(gate >> state) & 1 for state in range(4)], dtype=np.uint8)
    output = table[2 * current + column]
    wrong = output != required
    changed = output != current
    target_bad = int(np.count_nonzero(wrong & target))
    control_bad = int(np.count_nonzero(wrong & ~target))
    target_repairs = int(np.count_nonzero((~wrong) & target))
    control_changes = int(np.count_nonzero(changed & ~target))
    return (
        target_bad + control_bad,
        target_bad,
        control_bad,
        target_repairs,
        control_changes,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("h662_discovery", type=Path)
    parser.add_argument("h662_blind", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default=h1425.EXTRA_OP)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    discovery = load_cache(args.h662_discovery)
    blind = load_cache(args.h662_blind)
    discovery_score = calibration(discovery)
    blind_score = calibration(blind)
    discovery_lower = below_cut_collisions(discovery)
    blind_lower = below_cut_collisions(blind)

    prepared, source_rows, _, _ = h1425.prepare(args)
    current = np.asarray([item.current for item in prepared], dtype=np.uint8)
    required = np.asarray([item.required for item in prepared], dtype=np.uint8)
    target = np.asarray([item.target for item in prepared], dtype=bool)
    states = []
    for item in prepared:
        row = item.row
        left = int(row["S"], 16)
        right = int(row["B"], 16)
        magnitude = left - right
        cut = int(row["k"])
        if magnitude <= 0:
            raise RuntimeError(f"nonpositive terminal difference: {row['op']}")
        if magnitude != int(row["umag"], 16):
            raise RuntimeError(f"terminal difference mismatch: {row['op']}")
        mask = (1 << cut) - 1
        borrow = int((left & mask) < (right & mask))
        states.append((
            magnitude,
            cut,
            int(row["rscale"]),
            borrow,
            equality_run(left, right, cut),
            int(row["theta"]) > 0,
            item.current,
        ))

    ranking = []
    target_count = int(target.sum())
    candidate_signals = 0
    for width in BLOCK_WIDTHS:
        for phase in range(width):
            for variant in VARIANTS:
                columns = signal_columns(states, width, phase, variant)
                for signal, column in columns.items():
                    candidate_signals += 1
                    for gate in range(16):
                        score = gate_score(
                            column, current, required, target, gate
                        )
                        ranking.append((
                            *score,
                            GATE_NAMES[gate], gate,
                            width, phase, variant, signal,
                        ))
            print(
                f"width {width} phase {phase + 1}/{width}",
                flush=True,
            )

    ranking.sort()
    nonidentity = [item for item in ranking if item[6] != 0xC]
    exact = [item for item in ranking if item[0] == 0]
    improvements = [
        item for item in nonidentity
        if item[2] == 0 and item[1] < target_count
    ]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
            ("h662_discovery", args.h662_discovery),
            ("h662_blind", args.h662_blind),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tresolved_post_subtraction_block_confirmation_"
            "fixed_global_circuit\n"
        )
        output.write(f"primary_source\t{P5_PATENT}\t{P5_PATENT_URL}\n")
        output.write(f"primary_source\t{P6_PATENT}\t{P6_PATENT_URL}\n")
        output.write(
            "coverage_correction\th1416_h1420_h1428_below_cut_carry_"
            "summaries_do_not_contain_h662_resolved_above_cut_result_bits\n"
        )
        output.write(
            f"h662_discovery_rows\t{discovery_score[0]}\n"
            f"h662_discovery_critical\t{discovery_score[1]}\n"
            f"h662_discovery_errors\t{discovery_score[2]}\n"
            f"h662_blind_rows\t{blind_score[0]}\n"
            f"h662_blind_critical\t{blind_score[1]}\n"
            f"h662_blind_errors\t{blind_score[2]}\n"
        )
        for prefix, result in (
            ("h662_discovery", discovery_lower),
            ("h662_blind", blind_lower),
        ):
            output.write(f"{prefix}_critical_lower_key_rows\t{result[0]}\n")
            output.write(f"{prefix}_mixed_lower_key_groups\t{result[1]}\n")
            output.write(f"{prefix}_rows_in_mixed_lower_groups\t{result[2]}\n")
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{len(prepared) - target_count}\n")
        output.write(
            "block_widths\t" + ",".join(map(str, BLOCK_WIDTHS)) + "\n"
        )
        output.write("endpoint_variants\t" + ",".join(VARIANTS) + "\n")
        output.write(f"signal_equations\t{len(SIGNALS)}\n")
        output.write(f"candidate_signals\t{candidate_signals}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(improvements)}\n"
        )

        output.write("\n[lower-field mixed-group examples]\n")
        output.write("corpus\tkey\tzero_rows\tone_rows\n")
        for name, result in (
            ("discovery", discovery_lower),
            ("blind", blind_lower),
        ):
            if result[3]:
                key, counts = result[3]
                output.write(
                    f"{name}\t{key!r}\t{counts[0]}\t{counts[1]}\n"
                )

        output.write("\n[best nonidentity]\n")
        output.write(
            "all_bad\ttarget_bad\tcontrol_bad\ttarget_repairs\t"
            "control_changes\tgate\tgate_mask\twidth\tphase\tvariant\t"
            "signal\n"
        )
        for item in nonidentity[:2000]:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-control-collateral improvements]\n")
        for item in improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-error programs]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[result]\n")
        if exact:
            output.write("resolved_block_confirmation\texact_candidate_found\n")
        else:
            output.write(
                "resolved_block_confirmation\tno_exact_candidate_found\n"
            )
        output.write(
            "promotion_policy\trequires_exact_complete_wall_and_independent_"
            "adversarial_validation\n"
        )

    print(
        f"wrote {args.report}: constrained={len(prepared)} "
        f"signals={candidate_signals} programs={len(ranking)} "
        f"exact={len(exact)} improvements={len(improvements)} "
        f"best={nonidentity[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
