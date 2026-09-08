#!/usr/bin/env python3
"""Generate fresh exact-lattice disagreements among H1475 hypotheses.

This is a software-only adversarial-bank generator.  It samples H1470's
exact modular-lattice preimages with a seed disjoint from H1471, keeps only
operands on which the incumbent and falsified R1382 endpoint models differ,
and evaluates all 116 H1475 two-wire fits.  A greedy partition chooses rows
that split the remaining hypothesis equivalence classes as strongly as
possible.  No hardware label is read and no manifest is frozen here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1398_branch_two_wire_gate import named_features


MODES = ("rn", "rd", "ru", "rz")
WITNESS_RE = re.compile(
    r"^PRECANDIDATE 3ffc ([0-9a-f]{16}) square ([0-9a-f]{17}) "
    r"fourth ([0-9a-f]{17}) right_low72 ([0-9a-f]{17}) "
    r"iteration ([0-9]+)$"
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def scanner_rows(scanner: Path, samples: int, seed: str, maximum: int):
    completed = subprocess.run(
        [str(scanner), str(samples), seed, f"--max-witnesses={maximum}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(
            f"scanner exited {completed.returncode}: {completed.stderr}"
        )
    if completed.stderr:
        raise RuntimeError(f"unexpected scanner stderr: {completed.stderr}")
    rows = []
    summary = None
    for line in completed.stdout.splitlines():
        match = WITNESS_RE.fullmatch(line)
        if match is not None:
            rows.append({
                "sig": match.group(1),
                "square_sig": match.group(2),
                "fourth_sig": match.group(3),
                "right_low72": match.group(4),
                "iteration": int(match.group(5)),
            })
            continue
        if line.startswith("NO_WITNESS "):
            summary = line
            continue
        raise RuntimeError(f"unrecognized scanner row: {line!r}")
    if summary is None and len(rows) != maximum:
        raise RuntimeError("scanner ended without a complete or bounded summary")
    if len(rows) > maximum:
        raise RuntimeError("scanner exceeded requested witness maximum")
    return rows, summary


def model_outputs(binary: Path, signatures: list[str]):
    outputs = {}
    payload = "".join(f"3ffc {signature}\n" for signature in signatures)
    for mode in MODES:
        completed = subprocess.run(
            [str(binary), "--batch", "--fcos-standalone", f"--rc={mode}"],
            input=payload,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        if completed.stderr:
            raise RuntimeError(f"unexpected {mode} model stderr")
        values = []
        for line in completed.stdout.splitlines():
            fields = line.lower().split()
            if len(fields) < 3 or fields[0] != "ok":
                raise RuntimeError(f"bad model output: {line!r}")
            values.append(f"{fields[1]}:{fields[2]}")
        if len(values) != len(signatures):
            raise RuntimeError(f"{mode} model row count changed")
        outputs[mode] = values
    return outputs


def literal_value(name: str, features: dict[str, int]) -> int:
    inverted = name.startswith("!")
    bare = name[1:] if inverted else name
    if bare not in features:
        raise RuntimeError(f"missing H1475 feature {bare}")
    value = int(bool(features[bare]))
    return value ^ int(inverted)


def gate_value(gate: dict[str, object], features: dict[str, int]) -> int:
    left = literal_value(str(gate["left"]), features)
    right = literal_value(str(gate["right"]), features)
    operation = gate["gate"]
    if operation == "and":
        return left & right
    if operation == "or":
        return left | right
    if operation == "xor":
        return left ^ right
    raise RuntimeError(f"unexpected gate {operation}")


def changed_mode(current: dict[str, str], r1382: dict[str, str]) -> str:
    changed = [mode for mode in MODES if current[mode] != r1382[mode]]
    if changed == ["rd", "rz"]:
        return "rd"
    if len(changed) == 1 and changed[0] in ("rn", "ru"):
        return changed[0]
    raise RuntimeError(f"unexpected endpoint visibility {changed}")


def greedy_partition(rows: list[dict[str, object]], hypotheses: int, maximum: int):
    classes = [tuple(range(hypotheses))]
    selected = []
    remaining = list(range(len(rows)))
    while remaining and len(selected) < maximum:
        best = None
        for row_index in remaining:
            predictions = rows[row_index]["hypothesis_merge"]
            gain = 0
            for group in classes:
                ones = sum(int(predictions[index]) for index in group)
                gain += ones * (len(group) - ones)
            candidate = (gain, -int(rows[row_index]["iteration"]), -row_index)
            if best is None or candidate > best[0]:
                best = candidate, row_index
        if best is None or best[0][0] == 0:
            break
        row_index = best[1]
        selected.append(row_index)
        remaining.remove(row_index)
        predictions = rows[row_index]["hypothesis_merge"]
        refined = []
        for group in classes:
            zero = tuple(index for index in group if not predictions[index])
            one = tuple(index for index in group if predictions[index])
            if zero:
                refined.append(zero)
            if one:
                refined.append(one)
        classes = refined
    return selected, classes


def excluded_signatures(path: Path) -> set[str]:
    report = json.loads(path.read_text())
    return {
        str(row["sig"]).lower()
        for row in report["pre_candidate_bank"]["candidate_rows"]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("r1382", type=Path)
    parser.add_argument("leading_candidate", type=Path)
    parser.add_argument("h1475", type=Path)
    parser.add_argument("h1471", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--samples", type=int, default=30_000_000)
    parser.add_argument("--seed", default="0xa4093822299f31d0")
    parser.add_argument("--max-pre-candidates", type=int, default=128)
    parser.add_argument("--max-selected", type=int, default=48)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    h1475 = json.loads(args.h1475.read_text())
    hypotheses = h1475["all_exact_two_wire_gates"]
    if len(hypotheses) != 116:
        raise RuntimeError("H1475 hypothesis count changed")
    if hypotheses[0] != h1475["leading_hypothesis"]:
        raise RuntimeError("H1475 leading hypothesis order changed")
    excluded = excluded_signatures(args.h1471)
    excluded.update(("d0d000000cc0b3f8", "d80000000b15da62"))

    raw_rows, scanner_summary = scanner_rows(
        args.scanner, args.samples, args.seed, args.max_pre_candidates
    )
    raw_rows = [row for row in raw_rows if row["sig"] not in excluded]
    if not raw_rows:
        raise RuntimeError("no disjoint lattice pre-candidates")
    signatures = [row["sig"] for row in raw_rows]
    if len(signatures) != len(set(signatures)):
        raise RuntimeError("duplicate scanner operands")
    current = model_outputs(args.incumbent, signatures)
    r1382 = model_outputs(args.r1382, signatures)
    leading = model_outputs(args.leading_candidate, signatures)

    operands = [f"3ffc {signature}" for signature in signatures]
    _, stderr = run(args.incumbent, "rn", operands, dump=True)
    dumps = parse_dump(stderr, operands)
    candidates = []
    rejected_nonvisible = 0
    for index, (raw, dump) in enumerate(zip(raw_rows, dumps)):
        if int(raw["sig"], 16) ** 2 >> 61 != int(raw["square_sig"], 16):
            raise RuntimeError("first-square inverse changed")
        if int(raw["square_sig"], 16) ** 2 >> 66 != int(raw["fourth_sig"], 16):
            raise RuntimeError("fourth-power inverse changed")
        if int(dump["tc_f4_sig"], 16) != int(raw["fourth_sig"], 16):
            raise RuntimeError("C replay fourth power changed")
        right_low72 = (
            int(dump["tc_f4_sig"], 16) * int(dump["tc_rf_sig"], 16)
        ) & ((1 << 72) - 1)
        if right_low72 != int(raw["right_low72"], 16):
            raise RuntimeError("C replay right-product residue changed")

        current_row = {mode: current[mode][index] for mode in MODES}
        r1382_row = {mode: r1382[mode][index] for mode in MODES}
        if current_row == r1382_row:
            rejected_nonvisible += 1
            continue
        if dump["s4"] != "66" or dump["theta"] != "0" \
                or dump["low3"] != "3":
            raise RuntimeError("visible row escaped R1382 parent state")
        features = named_features(dump)
        predictions = [gate_value(gate, features) for gate in hypotheses]
        mode = changed_mode(current_row, r1382_row)
        expected_leading = current_row[mode] if predictions[0] else r1382_row[mode]
        if leading[mode][index] != expected_leading:
            raise RuntimeError("compiled leading candidate disagrees with wire replay")
        candidates.append({
            **raw,
            "operand": f"3ffc:{raw['sig']}",
            "mode": mode,
            "incumbent": current_row[mode],
            "r1382": r1382_row[mode],
            "leading_candidate": leading[mode][index],
            "leading_merge": predictions[0],
            "hypothesis_merge": predictions,
        })

    if not candidates:
        raise RuntimeError("no endpoint-visible candidate")
    selected_indexes, classes = greedy_partition(
        candidates, len(hypotheses), args.max_selected
    )
    selected = [candidates[index] for index in selected_indexes]
    signatures_by_hypothesis = [
        "".join(str(row["hypothesis_merge"][index]) for row in selected)
        for index in range(len(hypotheses))
    ]
    class_sizes = sorted(Counter(signatures_by_hypothesis).values(), reverse=True)

    report = {
        "experiment": "h1476_r1382_split_disagreement_bank",
        "status": "SOFTWARE_ONLY_UNOPENED",
        "sampling": {
            "samples": args.samples,
            "seed": args.seed,
            "max_pre_candidates": args.max_pre_candidates,
            "scanner_summary": scanner_summary,
            "disjoint_pre_candidates": len(raw_rows),
            "rejected_nonvisible": rejected_nonvisible,
            "endpoint_visible": len(candidates),
        },
        "hypotheses": len(hypotheses),
        "selected_rows": len(selected),
        "selected_mode_counts": dict(sorted(Counter(
            row["mode"] for row in selected
        ).items())),
        "selected_leading_merge_counts": dict(sorted(Counter(
            str(row["leading_merge"]) for row in selected
        ).items())),
        "hypothesis_equivalence_classes_after_selection": len(classes),
        "hypothesis_equivalence_class_sizes": class_sizes,
        "selected": selected,
        "all_endpoint_visible": candidates,
        "claim_boundary": (
            "No hardware label was read. Selection maximizes disagreement "
            "among H1475 label-selected hypotheses and cannot validate any "
            "of them without a separately frozen one-shot capture."
        ),
        "hardware_execution": "none",
        "hardware_labels": "none",
        "capture_manifest": "none",
        "emulator_change": "analysis_only_default_off",
        "paper_change": "none",
        "sha256": {
            "scanner": digest(args.scanner),
            "incumbent": digest(args.incumbent),
            "r1382": digest(args.r1382),
            "leading_candidate": digest(args.leading_candidate),
            "h1475": digest(args.h1475),
            "h1471": digest(args.h1471),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "pre_candidates": len(raw_rows),
        "endpoint_visible": len(candidates),
        "selected": len(selected),
        "classes": len(classes),
        "largest_class": max(class_sizes),
        "mode_counts": report["selected_mode_counts"],
        "leading_merge_counts": report["selected_leading_merge_counts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
