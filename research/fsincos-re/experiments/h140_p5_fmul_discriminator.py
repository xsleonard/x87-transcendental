#!/usr/bin/env python3
"""Measure and generate discriminators for the surviving P5 FMUL route.

h139 places the table constant on X67 and the p-state on Y64, but existing
aggregate scores leave RN64 and away64 product outputs observationally tied.
This pass compares representative route classes point-by-point.  It reports
which existing hardware observations already distinguish them and can emit
fresh direct/reduced narrow-table operands when another capture is needed.
"""

from __future__ import annotations

import argparse
import pathlib
import random

import h58_constraint_search as h58
import h80_round21_parity as h80
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h139_p5_fmul_route_search as h139


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "capture-kit" / "inputs" / "constraint_fsin_fmul_h140.txt"
)
DEFAULT_METADATA = (
    ROOT
    / "capture-kit"
    / "inputs"
    / "constraint_fsin_fmul_h140.meta.txt"
)
SEED = 0xF140C5

X_RN = h139.Route("x", "rn", "rn", "rn")
X_AWAY = h139.Route("x", "rn", "rn", "away")
X_RU = h139.Route("x", "rn", "rn", "ru")
X_RD = h139.Route("x", "rn", "rn", "rd")
X_ODD = h139.Route("x", "rn", "rn", "odd")
Y_RN = h139.Route("y", "rn", "rn", "rn")
Y_AWAY = h139.Route("y", "rn", "rn", "away")
Y_RU = h139.Route("y", "rn", "rn", "ru")
Y_RD = h139.Route("y", "rn", "rn", "rd")
Y_ODD = h139.Route("y", "rn", "rn", "odd")
ROUTES = (
    ("X67/RN64", X_RN),
    ("X67/away64", X_AWAY),
    ("X67/RU64", X_RU),
    ("X67/RD64", X_RD),
    ("X67/odd64", X_ODD),
    ("Y64/RN64", Y_RN),
    ("Y64/away64", Y_AWAY),
    ("Y64/RU64", Y_RU),
    ("Y64/RD64", Y_RD),
    ("Y64/odd64", Y_ODD),
)
PAIRS = (
    ("output-mode", X_RN, X_AWAY),
    ("RU-vs-RN", X_RU, X_RN),
    ("RU-vs-away", X_RU, X_AWAY),
    ("RN-vs-RD", X_RN, X_RD),
    ("RN-vs-odd", X_RN, X_ODD),
    ("away-vs-odd", X_AWAY, X_ODD),
    ("orientation-rn", X_RN, Y_RN),
    ("orientation-away", X_AWAY, Y_AWAY),
    ("orientation-ru", X_RU, Y_RU),
    ("orientation-rd", X_RD, Y_RD),
    ("orientation-odd", X_ODD, Y_ODD),
)


def prediction(
    point: h131.Observed, route: h139.Route
) -> tuple[tuple[int, int], ...]:
    hidden = h139.hidden_value(point, route)
    return tuple(h58.x87_round(hidden, rc) for rc in h58.RCS)


def trailing_zeros(value: int) -> int:
    return (value & -value).bit_length() - 1 if value else 0


def product_features(
    point: h131.Observed, route: h139.Route
) -> str:
    state = h136.standalone_state(
        point.point, h135.path_candidate(point)
    )
    quadrant = point.signed_n & 3
    constant = (
        point.point.sin_t if quadrant & 1 else point.point.cos_t
    )
    if route.constant_bus == "x":
        x_value, y_value = constant, state.sine_correction
    else:
        x_value, y_value = state.sine_correction, constant
    x_value = h139.quantize(x_value, 67, route.x_mode)
    y_value = h139.quantize(y_value, 64, route.y_mode)
    product = h58.mul_exact(x_value, y_value)
    width = product[1].bit_length()
    shift = max(0, width - 64)
    top = product[1] >> shift
    remainder = (
        product[1] & ((1 << shift) - 1) if shift else 0
    )
    guard = (remainder >> (shift - 1)) & 1 if shift else 0
    below = (
        remainder & ((1 << (shift - 1)) - 1)
        if shift > 1
        else 0
    )
    normalized_high = int(
        width
        == x_value[1].bit_length() + y_value[1].bit_length()
    )
    return (
        f"q={quadrant} src={point.source} cell={point.point.cell} "
        f"aSign={state.residual[0]} pSign={state.sine_correction[0]} "
        f"prodSign={product[0]} cLow3={constant[1] & 7} "
        f"norm2={normalized_high} shift={shift} "
        f"lsb={top & 1} G={guard} S={int(bool(below))} "
        f"tzX={trailing_zeros(x_value[1])} "
        f"tzY={trailing_zeros(y_value[1])} "
        f"tzSum={trailing_zeros(x_value[1]) + trailing_zeros(y_value[1])}"
    )


def analyze_partition(
    name: str, points: list[h131.Observed]
) -> None:
    points = [point for point in points if point.family == "narrow"]
    print(f"{name}: {len(points)} narrow inputs")
    predictions = {
        route: [prediction(point, route) for point in points]
        for _, route in ROUTES
    }
    for label, route in ROUTES:
        result = h139.score(points, route)
        print(
            f"  {label:12s} "
            f"{h131.describe(result, len(points))}"
        )
    for label, left_route, right_route in PAIRS:
        left = predictions[left_route]
        right = predictions[right_route]
        separators = 0
        left_wins = 0
        right_wins = 0
        neither = 0
        witnesses = []
        for point, left_values, right_values in zip(
            points, left, right
        ):
            for index in range(len(h58.RCS)):
                if left_values[index] == right_values[index]:
                    continue
                separators += 1
                expected = point.outputs[index]
                left_match = left_values[index] == expected
                right_match = right_values[index] == expected
                left_wins += left_match and not right_match
                right_wins += right_match and not left_match
                neither += not left_match and not right_match
                if len(witnesses) < 8:
                    winner = (
                        "left"
                        if left_match and not right_match
                        else "right"
                        if right_match and not left_match
                        else "neither"
                    )
                    witnesses.append(
                        (
                            point,
                            h58.RCS[index],
                            winner,
                            expected,
                            left_values[index],
                            right_values[index],
                        )
                    )
        print(
            f"  {label:16s} separators={separators} "
            f"left={left_wins} right={right_wins} neither={neither}"
        )
        for point, rc, winner, expected, left_value, right_value in witnesses:
            print(
                f"    line={point.index + 1} rc={rc} winner={winner} "
                f"hw={expected[0]:04x}:{expected[1]:016x} "
                f"L={left_value[0]:04x}:{left_value[1]:016x} "
                f"R={right_value[0]:04x}:{right_value[1]:016x} "
                f"{product_features(point, left_route)}"
            )


def observed_for_operand(
    index: int, se: int, sig: int
) -> h131.Observed | None:
    active = h80.active_table_input(se, sig)
    if active is None:
        return None
    signed_n, point, reduced = active
    if point.wide:
        return None
    return h131.Observed(
        index,
        "reduced" if reduced else "direct",
        signed_n,
        point,
        ((0, 0),) * len(h58.RCS),
        (False,) * len(h58.RCS),
    )


def generate(
    output: pathlib.Path,
    metadata: pathlib.Path,
    per_class: int,
    scan_limit: int,
) -> None:
    rng = random.Random(SEED)
    rows: list[str] = []
    labels: list[str] = []
    seen: set[tuple[int, int]] = set()
    counts = {
        (source, label): 0
        for source in ("direct", "reduced")
        for label, _, _ in PAIRS
    }
    signatures: dict[
        tuple[str, str, tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]],
        int,
    ] = {}
    scanned = 0
    while (
        any(count < per_class for count in counts.values())
        and scanned < scan_limit
    ):
        source = "direct" if scanned & 1 == 0 else "reduced"
        if source == "direct":
            se, sig = h135.direct_operand(rng, "narrow")
            scanned += 1
        else:
            operands, attempts = h135.reduced_operands(
                rng, "narrow", 1
            )
            se, sig = operands[0]
            scanned += attempts
        if (se, sig) in seen:
            continue
        point = observed_for_operand(scanned, se, sig)
        if point is None or point.source != source:
            continue
        predicted = {
            route: prediction(point, route)
            for _, route in ROUTES
        }
        selected_label = None
        for label, left, right in PAIRS:
            key = (source, label)
            if counts[key] >= per_class:
                continue
            left_values = predicted[left]
            right_values = predicted[right]
            if left_values == right_values:
                continue
            signature = (
                source, label, left_values, right_values
            )
            if signatures.get(signature, 0) >= 8:
                continue
            signatures[signature] = signatures.get(signature, 0) + 1
            selected_label = label
            break
        if selected_label is None:
            continue
        seen.add((se, sig))
        rows.append(f"{se:04x} {sig:016x}")
        labels.append(f"{source} {selected_label}")
        counts[(source, selected_label)] += 1
    output.write_text("\n".join(rows) + "\n")
    metadata.write_text("\n".join(labels) + "\n")
    print(
        f"h140 wrote {len(rows)} inputs after {scanned} scans; "
        f"seed={SEED:#x}"
    )
    for key in sorted(counts):
        print(f"  {key[0]:7s} {key[1]:16s} {counts[key]}/{per_class}")


def load_capture(
    inputs: pathlib.Path,
    capture: pathlib.Path,
) -> list[h131.Observed]:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in inputs.read_text().splitlines()
    ]
    modes = [
        (
            capture / f"constraint_fsin_fmul_{rc}_status.txt"
        ).read_text().splitlines()
        for rc in h58.RCS
    ]
    if any(len(lines) != len(operands) for lines in modes):
        raise SystemExit("h140 input/capture line counts differ")
    result = []
    for index, (se, sig) in enumerate(operands):
        point = observed_for_operand(index, se, sig)
        if point is None:
            raise SystemExit(f"h140 input {index + 1} is not narrow-table")
        outputs = []
        c1 = []
        for lines in modes:
            fields = lines[index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(lines[index])
            outputs.append((int(fields[1], 16), int(fields[2], 16)))
            c1.append(bool(int(fields[4], 16) & 0x0200))
        result.append(
            h131.Observed(
                point.index,
                point.source,
                point.signed_n,
                point.point,
                tuple(outputs),
                tuple(c1),
            )
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze-existing", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--score", type=pathlib.Path)
    parser.add_argument("--per-class", type=int, default=32)
    parser.add_argument("--scan-limit", type=int, default=10_000_000)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata", type=pathlib.Path, default=DEFAULT_METADATA
    )
    args = parser.parse_args()
    if args.analyze_existing:
        dense = h131.load_dataset(
            "dense", h131.INPUTS / "dense_qn.txt"
        )
        sweep = h131.load_dataset(
            "sweep", h131.INPUTS / "sweep_inputs.txt"
        )
        analyze_partition("dense", dense)
        analyze_partition("sweep", sweep)
    if args.generate:
        generate(
            args.output,
            args.metadata,
            args.per_class,
            args.scan_limit,
        )
    if args.score is not None:
        captured = load_capture(args.output, args.score)
        analyze_partition("h140", captured)
        for source in ("direct", "reduced"):
            analyze_partition(
                f"h140-{source}",
                [point for point in captured if point.source == source],
            )
    if (
        not args.analyze_existing
        and not args.generate
        and args.score is None
    ):
        parser.error("select --analyze-existing, --generate, and/or --score")


if __name__ == "__main__":
    main()
