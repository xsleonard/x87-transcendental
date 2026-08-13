#!/usr/bin/env python3
"""Gate the current FSIN model against the frozen binary64 residual oracle.

The fixture is intentionally separate from every historical corpus. The
default policy permits the current 3 result and 4 C1 residuals but
rejects any increase. Use --expect-baseline to verify the current
model/fixture pair, or --require-zero after implementing a proposed correction.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = ROOT / "capture-kit" / "inputs" / "fsin_binary64_misses_h377.txt"
EXPECTED = ROOT / "capture-kit" / "expected"
RCS = ("rn", "rd", "ru")
STATUS_C1 = 0x0200
BASELINE_RESULT = 1
BASELINE_C1 = 2

FIXTURE_HASHES = {
    INPUTS: "90beb327ff4eb7c59a626a223c6ce28f6489182f2947a7bb1b94eee89ad39175",
    EXPECTED / "fsin_binary64_misses_h377_rn_status.txt":
        "c49115c570c35053e34cc12467374eaaaea46b4fc165a0adc030ae99ad7cde4a",
    EXPECTED / "fsin_binary64_misses_h377_rd_status.txt":
        "63d0d78cf417bd864f63e6568509a26e01a6bd883b0292e53968fd06dc9e7257",
    EXPECTED / "fsin_binary64_misses_h377_ru_status.txt":
        "2b79c2a25ae1651ec24a0927b3f3f3f97650a5e7719adb46a5fa901f673e8155",
}

MODEL_FLAGS = (
    "--batch",
    "--round18-poly",
    "--round21-table-bias",
    "--round23-narrow-coefficient",
    "--round24-table-delta-rn67",
    "--round29-p5-fmul-route",
    "--round30-fsin-cosine-square",
    "--round31-fsin-cosine-tail",
    "--round32-fsin-cosine-horner",
    "--round33-fsin-cosine-product",
    "--round34-table-lookup-firc",
    "--round35-table-p-terminal",
    "--round36-table-fadd-microcontrol",
    "--round37-p6-four-term",
    "--round38-p6-cosine-split",
    "--round39-fcos-tiny",
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
    "--round50-fsin-operation-classes",
    "--round51-fsin-fadd-signature",
    "--round56-fsin-cosine-carrier",
    "--fsin-standalone",
)

X80 = tuple[int, int]


def verify_fixture() -> None:
    for path, expected in FIXTURE_HASHES.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(
                f"fixture hash mismatch: {path}\n"
                f"expected {expected}\n"
                f"actual   {actual}"
            )


def parse_model(line: str) -> X80 | None:
    fields = line.split()
    if fields == ["C2"]:
        return None
    if len(fields) != 3 or fields[0] != "OK":
        raise ValueError(f"invalid model line: {line}")
    return int(fields[1], 16), int(fields[2], 16)


def parse_hardware(line: str) -> tuple[X80 | None, int]:
    fields = line.split()
    if len(fields) == 3 and fields[0] == "C2" and fields[1] == "SW":
        return None, int(fields[2], 16)
    if len(fields) != 5 or fields[0] != "OK" or fields[3] != "SW":
        raise ValueError(f"invalid hardware line: {line}")
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        int(fields[4], 16),
    )


def model_c1(outputs: dict[str, X80 | None], rc: str) -> int | None:
    current = outputs[rc]
    rd = outputs["rd"]
    ru = outputs["ru"]
    if current is None:
        return 0
    if rd is None or ru is None:
        return None
    if rd == ru:
        return 0
    sign = current[0] >> 15
    away, toward = (rd, ru) if sign else (ru, rd)
    if current == away:
        return 1
    if current == toward:
        return 0
    return None


def signed_step(predicted: X80, expected: X80) -> int | str:
    predicted_se, predicted_sig = predicted
    expected_se, expected_sig = expected
    predicted_sign = predicted_se >> 15
    expected_sign = expected_se >> 15
    if predicted_sign != expected_sign:
        return "sign"
    predicted_rank = ((predicted_se & 0x7FFF) << 64) + predicted_sig
    expected_rank = ((expected_se & 0x7FFF) << 64) + expected_sig
    delta = predicted_rank - expected_rank
    return -delta if predicted_sign else delta


def load_model(
    model: pathlib.Path, input_text: str,
    extra_flags: tuple[str, ...] = (),
) -> dict[str, list[X80 | None]]:
    result = {}
    for rc in RCS:
        command = [str(model.resolve()), *MODEL_FLAGS,
                   *extra_flags]
        if rc != "rn":
            command.append(f"--rc={rc}")
        lines = subprocess.run(
            command,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()
        result[rc] = [parse_model(line) for line in lines]
    return result


def load_hardware() -> dict[str, list[tuple[X80 | None, int]]]:
    return {
        rc: [
            parse_hardware(line)
            for line in (
                EXPECTED / f"fsin_binary64_misses_h377_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        for rc in RCS
    }


def format_x80(value: X80 | None) -> str:
    if value is None:
        return "C2"
    return f"{value[0]:04x}:{value[1]:016x}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=pathlib.Path)
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument(
        "--expect-baseline",
        action="store_true",
        help="require exactly the current 1 result and 2 C1 residuals",
    )
    policy.add_argument(
        "--require-zero",
        action="store_true",
        help="require complete result/C1/C2 parity",
    )
    parser.add_argument("--show-misses", type=int, default=0)
    parser.add_argument(
        "--model-flag",
        action="append",
        default=[],
        help="extra model flag (repeatable), e.g. "
             "--model-flag=--round58-fsin-borrow-rule",
    )
    args = parser.parse_args()

    verify_fixture()
    input_text = INPUTS.read_text()
    input_lines = input_text.splitlines()
    model = load_model(args.model, input_text,
                       tuple(args.model_flag))
    hardware = load_hardware()
    all_rows = tuple(model.values()) + tuple(hardware.values())
    if any(len(rows) != len(input_lines) for rows in all_rows):
        raise SystemExit("h377 fixture/model line counts differ")

    counts: collections.Counter[object] = collections.Counter()
    affected = set()
    reports = 0
    for index, input_line in enumerate(input_lines):
        outputs = {rc: model[rc][index] for rc in RCS}
        for rc in RCS:
            predicted = outputs[rc]
            expected, status = hardware[rc][index]
            if predicted != expected:
                if predicted is None or expected is None:
                    counts["C2"] += 1
                    difference: int | str = "class"
                else:
                    counts["result"] += 1
                    counts["result", rc] += 1
                    difference = signed_step(predicted, expected)
                    counts["step", difference] += 1
                affected.add(index)
                if reports < args.show_misses:
                    print(
                        f"result index={index} "
                        f"input={input_line.replace(' ', ':')} "
                        f"rc={rc} model={format_x80(predicted)} "
                        f"hardware={format_x80(expected)} step={difference}"
                    )
                    reports += 1

            predicted_c1 = model_c1(outputs, rc)
            if predicted_c1 is None:
                counts["interval"] += 1
                affected.add(index)
            elif (
                expected is not None
                and predicted_c1 != bool(status & STATUS_C1)
            ):
                counts["C1"] += 1
                counts["C1", rc] += 1
                affected.add(index)
                if reports < args.show_misses:
                    print(
                        f"C1 index={index} "
                        f"input={input_line.replace(' ', ':')} "
                        f"rc={rc} model={predicted_c1} "
                        f"hardware={int(bool(status & STATUS_C1))}"
                    )
                    reports += 1

    result_misses = counts["result"]
    c1_misses = counts["C1"]
    hard_failures = counts["C2"] + counts["interval"]
    if args.require_zero:
        policy_name = "zero"
        passed = result_misses == c1_misses == hard_failures == 0
    elif args.expect_baseline:
        policy_name = "baseline"
        passed = (
            result_misses == BASELINE_RESULT
            and c1_misses == BASELINE_C1
            and hard_failures == 0
        )
    else:
        policy_name = "no-worse"
        passed = (
            result_misses <= BASELINE_RESULT
            and c1_misses <= BASELINE_C1
            and hard_failures == 0
        )

    print(
        f"h377 standalone FSIN residual gate: "
        f"result={result_misses}/{len(input_lines) * len(RCS)} "
        f"C1={c1_misses}/{len(input_lines) * len(RCS)} "
        f"C2={counts['C2']} interval={counts['interval']} "
        f"affected-inputs={len(affected)}/{len(input_lines)} "
        f"policy={policy_name} {'PASS' if passed else 'FAIL'}"
    )
    print(
        "  result-modes="
        + str({rc: counts["result", rc] for rc in RCS})
        + " C1-modes="
        + str({rc: counts["C1", rc] for rc in RCS})
        + " steps="
        + str({
            key[1]: value
            for key, value in counts.items()
            if isinstance(key, tuple) and key[0] == "step"
        })
    )
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
