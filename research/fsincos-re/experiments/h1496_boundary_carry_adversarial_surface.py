#!/usr/bin/env python3
"""Build a fresh software-only adversarial surface for H1495.

H1495 proves that each H1487 survivor is a canonical lower-residue boundary
carry for one exact final carry-save representation.  It does not identify
which representation exists in Skylake.  This experiment samples a disjoint
exact R1382 lattice, keeps only external operands whose incumbent and R1382
software endpoints differ, and selects equal numbers of all four pair-A/pair-B
prediction patterns.  The selected bank therefore balances both candidate
values while covering unanimous controls and pair disagreements.

No x87 instruction is executed, no hardware label is opened, and no capture
manifest is frozen by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1400_p5_representation_audit import (
    booth_digits,
    physical_inputs,
    reduce_tree,
    tree_variants,
)
from h1486_surviving_propagate_class import (
    EXPECTED_SIGNALS,
    candidate_values,
)


MODES = ("rn", "rd", "ru", "rz")
PATTERNS = ("0000", "0011", "1100", "1111")
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


def changed_mode(current: dict[str, str], r1382: dict[str, str]) -> str:
    changed = [mode for mode in MODES if current[mode] != r1382[mode]]
    if changed == ["rd", "rz"]:
        return "rd"
    if len(changed) == 1 and changed[0] in ("rn", "ru"):
        return changed[0]
    raise RuntimeError(f"unexpected endpoint visibility {changed}")


def collect_known_signatures(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "sig" and isinstance(item, str) \
                    and re.fullmatch(r"[0-9a-fA-F]{16}", item):
                found.add(item.lower())
            if key == "operand" and isinstance(item, str):
                match = re.fullmatch(
                    r"3ffc[: ]([0-9a-fA-F]{16})", item.strip())
                if match is not None:
                    found.add(match.group(1).lower())
            found.update(collect_known_signatures(item))
    elif isinstance(value, list):
        for item in value:
            found.update(collect_known_signatures(item))
    return found


def repository_collisions(
        signatures: set[str], root: Path, excluded: set[Path]
        ) -> set[str]:
    command = ["rg", "-l", "-i", "--fixed-strings"]
    for signature in sorted(signatures):
        command.extend(("-e", signature))
    command.append(str(root))
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"repository search failed: {completed.stderr}")
    found = set()
    for name in completed.stdout.splitlines():
        path = Path(name)
        if path.resolve() in excluded:
            continue
        text = path.read_text(errors="ignore").lower()
        found.update(signature for signature in signatures if signature in text)
    return found


def boundary_state(multiplicand: int, multiplier: int, config, position: int):
    inputs, _ = physical_inputs(multiplicand, multiplier, config.correction)
    pair_s, pair_c = reduce_tree(inputs, config)
    product = multiplicand * multiplier
    modulus = 1 << 131
    if ((pair_s + pair_c) % modulus) != (product % modulus):
        raise RuntimeError("candidate pair stopped reconstructing the product")
    lower_mask = (1 << position) - 1
    carry = int(
        (pair_s & lower_mask) + (pair_c & lower_mask) >= (1 << position)
    )
    product_bit = (product >> position) & 1
    selector = ((pair_s ^ pair_c) >> position) & 1
    if selector != (product_bit ^ carry):
        raise RuntimeError("H1495 boundary-carry identity failed to replay")
    return {
        "sum_low": f"{pair_s & lower_mask:x}",
        "carry_low": f"{pair_c & lower_mask:x}",
        "boundary_carry": carry,
        "selector": selector,
    }


def row_tokens(row: dict[str, object]) -> set[str]:
    pattern = str(row["candidate_pattern"])
    state = row["structural_state"]
    booth = row["booth_summary"]
    tokens = {
        f"mode:{row['mode']}",
        f"cut:{row['target_column']}",
        f"product_bit:{row['product_bit']}",
        f"pattern_mode:{pattern}:{row['mode']}",
        f"pattern_cut:{pattern}:{row['target_column']}",
        f"pattern_product:{pattern}:{row['product_bit']}",
    }
    for key in ("side", "ce", "k", "b1", "b2", "dist", "payload"):
        tokens.add(f"{key}:{state[key]}")
        tokens.add(f"pattern_{key}:{pattern}:{state[key]}")
    for key in ("negative", "zero", "abs3", "abs4", "sign_transitions"):
        bucket = int(booth[key]) // 2
        tokens.add(f"booth_{key}_bucket:{bucket}")
        tokens.add(f"pattern_booth_{key}_bucket:{pattern}:{bucket}")
    return tokens


def balanced_selection(rows: list[dict[str, object]], per_pattern: int):
    by_pattern = {
        pattern: [row for row in rows if row["candidate_pattern"] == pattern]
        for pattern in PATTERNS
    }
    count = min([per_pattern] + [len(by_pattern[p]) for p in PATTERNS])
    selected = []
    covered: set[str] = set()
    remaining = {pattern: list(values) for pattern, values in by_pattern.items()}
    for _ in range(count):
        for pattern in sorted(PATTERNS, key=lambda item: len(by_pattern[item])):
            ranked = []
            for row in remaining[pattern]:
                tokens = row_tokens(row)
                gain = len(tokens - covered)
                ranked.append((gain, -int(row["iteration"]), row, tokens))
            if not ranked:
                raise RuntimeError("balanced selection exhausted unexpectedly")
            _, _, chosen, tokens = max(ranked, key=lambda item: item[:2])
            selected.append(chosen)
            covered.update(tokens)
            remaining[pattern].remove(chosen)
    return selected, count, covered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scanner", required=True, type=Path)
    parser.add_argument("--incumbent", required=True, type=Path)
    parser.add_argument("--r1382", required=True, type=Path)
    parser.add_argument("--h1471", required=True, type=Path)
    parser.add_argument("--h1476", required=True, type=Path)
    parser.add_argument("--h1485", required=True, type=Path)
    parser.add_argument("--h1486", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--collision-exclude", action="append", default=[], type=Path,
        help="prior copy of this report to ignore during a reproducibility run",
    )
    parser.add_argument("--samples", type=int, default=30_000_000)
    parser.add_argument("--seed", default="0x4f1bbcdc676e4f35")
    parser.add_argument("--max-pre-candidates", type=int, default=256)
    parser.add_argument("--per-pattern", type=int, default=6)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    for path in (args.scanner, args.incumbent, args.r1382):
        if not path.is_file():
            raise SystemExit(f"missing executable: {path}")

    dependencies = [args.h1471, args.h1476, args.h1485, args.h1486]
    loaded = [json.loads(path.read_text()) for path in dependencies]
    known = {"d0d000000cc0b3f8", "d80000000b15da62"}
    for value in loaded:
        known.update(collect_known_signatures(value))

    h1486 = loaded[-1]
    signal_order = h1486["survivor_class"]["signal_order"]
    if set(signal_order) != EXPECTED_SIGNALS:
        raise RuntimeError("H1486 survivor class changed")
    layouts = {name: config for name, _, config in tree_variants()}
    configs = [
        layouts[signal.split(".final.")[0]] for signal in signal_order
    ]
    if len(configs) != 4:
        raise RuntimeError("H1486 configuration count changed")

    raw_rows, scanner_summary = scanner_rows(
        args.scanner, args.samples, args.seed, args.max_pre_candidates
    )
    raw_rows = [row for row in raw_rows if row["sig"] not in known]
    if not raw_rows:
        raise RuntimeError("no disjoint lattice pre-candidates")
    signatures = [row["sig"] for row in raw_rows]
    if len(signatures) != len(set(signatures)):
        raise RuntimeError("duplicate scanner operands")
    current = model_outputs(args.incumbent, signatures)
    r1382 = model_outputs(args.r1382, signatures)
    operands = [f"3ffc {signature}" for signature in signatures]
    _, stderr = run(args.incumbent, "rn", operands, dump=True)
    dumps = parse_dump(stderr, operands)
    if len(dumps) != len(raw_rows):
        raise RuntimeError("diagnostic replay row count changed")

    candidates = []
    rejected_nonvisible = 0
    for index, (raw, dump) in enumerate(zip(raw_rows, dumps)):
        if int(raw["sig"], 16) ** 2 >> 61 != int(raw["square_sig"], 16):
            raise RuntimeError("first-square inverse changed")
        if int(raw["square_sig"], 16) ** 2 >> 66 \
                != int(raw["fourth_sig"], 16):
            raise RuntimeError("fourth-power inverse changed")
        multiplicand = int(dump["tc_f4_sig"], 16)
        multiplier = int(dump["tc_rf_sig"], 16)
        if multiplicand != int(raw["fourth_sig"], 16):
            raise RuntimeError("C replay fourth power changed")
        right_low72 = (multiplicand * multiplier) & ((1 << 72) - 1)
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
        mode = changed_mode(current_row, r1382_row)
        product = multiplicand * multiplier
        cut = product.bit_length() - 67
        position = cut - 18
        if position not in (45, 46):
            raise RuntimeError(f"unexpected cut-minus-18 column {position}")
        pattern = candidate_values(multiplicand, multiplier, configs)
        if pattern not in PATTERNS or pattern[0] != pattern[1] \
                or pattern[2] != pattern[3]:
            raise RuntimeError(f"H1487 pair partition failed: {pattern}")
        pair_states = [
            boundary_state(multiplicand, multiplier, config, position)
            for config in configs
        ]
        replayed = "".join(str(item["selector"]) for item in pair_states)
        if replayed != pattern:
            raise RuntimeError("boundary-state replay disagrees with H1486")
        digits = booth_digits(multiplier)
        signs = [0 if digit == 0 else 1 if digit > 0 else -1 for digit in digits]
        nonzero_signs = [value for value in signs if value]
        transitions = sum(
            left != right for left, right in zip(nonzero_signs, nonzero_signs[1:])
        )
        candidates.append({
            **raw,
            "operand": f"3ffc:{raw['sig']}",
            "mode": mode,
            "incumbent": current_row[mode],
            "r1382": r1382_row[mode],
            "candidate_pattern": pattern,
            "pair_a_merge": int(pattern[0]),
            "pair_b_merge": int(pattern[2]),
            "target_column": position,
            "product_bit": (product >> position) & 1,
            "pair_a_boundary_carry": pair_states[0]["boundary_carry"],
            "pair_b_boundary_carry": pair_states[2]["boundary_carry"],
            "pair_a_low_residues": {
                "sum": pair_states[0]["sum_low"],
                "carry": pair_states[0]["carry_low"],
            },
            "pair_b_low_residues": {
                "sum": pair_states[2]["sum_low"],
                "carry": pair_states[2]["carry_low"],
            },
            "structural_state": {
                key: dump[key]
                for key in (
                    "s4", "theta", "low3", "side", "ce", "k", "b1",
                    "b2", "dist", "payload",
                )
            },
            "booth_summary": {
                "negative": sum(digit < 0 for digit in digits),
                "zero": sum(digit == 0 for digit in digits),
                "abs3": sum(abs(digit) == 3 for digit in digits),
                "abs4": sum(abs(digit) == 4 for digit in digits),
                "sign_transitions": transitions,
                "digits": list(digits),
            },
        })

    if not candidates:
        raise RuntimeError("no endpoint-visible candidates")
    collisions = repository_collisions(
        {str(row["sig"]) for row in candidates},
        args.repo_root,
        {path.resolve() for path in args.collision_exclude},
    )
    if collisions:
        raise RuntimeError(
            f"fresh software candidates overlap repository evidence: {len(collisions)}"
        )
    selected, selected_per_pattern, covered = balanced_selection(
        candidates, args.per_pattern
    )
    pattern_counts = Counter(str(row["candidate_pattern"]) for row in candidates)
    selected_pattern_counts = Counter(
        str(row["candidate_pattern"]) for row in selected
    )
    selected_mode_counts = Counter(str(row["mode"]) for row in selected)
    selected_cut_counts = Counter(str(row["target_column"]) for row in selected)
    selected_product_counts = Counter(str(row["product_bit"]) for row in selected)
    selected_boundary_counts = {
        pair: dict(sorted(Counter(
            str(row[f"{pair}_boundary_carry"]) for row in selected
        ).items()))
        for pair in ("pair_a", "pair_b")
    }
    report = {
        "experiment": "h1496_boundary_carry_adversarial_surface",
        "status": "SOFTWARE_ONLY_BALANCED_ADVERSARIAL_SURFACE",
        "sampling": {
            "samples": args.samples,
            "seed": args.seed,
            "max_pre_candidates": args.max_pre_candidates,
            "scanner_summary": scanner_summary,
            "known_operand_exclusions": len(known),
            "disjoint_pre_candidates": len(raw_rows),
            "rejected_nonvisible": rejected_nonvisible,
            "endpoint_visible": len(candidates),
        },
        "candidate_signal_order": signal_order,
        "all_pattern_counts": dict(sorted(pattern_counts.items())),
        "selection": {
            "requested_per_pattern": args.per_pattern,
            "selected_per_pattern": selected_per_pattern,
            "rows": len(selected),
            "pattern_counts": dict(sorted(selected_pattern_counts.items())),
            "mode_counts": dict(sorted(selected_mode_counts.items())),
            "target_column_counts": dict(sorted(selected_cut_counts.items())),
            "product_bit_counts": dict(sorted(selected_product_counts.items())),
            "boundary_carry_counts": selected_boundary_counts,
            "feature_tokens_covered": len(covered),
            "pair_a_merge_counts": dict(sorted(Counter(
                str(row["pair_a_merge"]) for row in selected
            ).items())),
            "pair_b_merge_counts": dict(sorted(Counter(
                str(row["pair_b_merge"]) for row in selected
            ).items())),
        },
        "selected": selected,
        "all_endpoint_visible": candidates,
        "claim_boundary": (
            "Every candidate value is an exact H1495 boundary-carry replay, "
            "but all endpoints and selections are software-derived. This bank "
            "can falsify either physical-pair hypothesis only after a separate "
            "freshness audit, freeze, authorization, and one-shot hardware run."
        ),
        "hardware_execution": "none",
        "hardware_labels": "none",
        "private_ledger_audit": "not_required_for_software_only_surface",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "scanner": digest(args.scanner),
            "incumbent": digest(args.incumbent),
            "r1382": digest(args.r1382),
            "h1471": digest(args.h1471),
            "h1476": digest(args.h1476),
            "h1485": digest(args.h1485),
            "h1486": digest(args.h1486),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text)
    print(json.dumps({
        "output": str(args.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "pre_candidates": len(raw_rows),
        "endpoint_visible": len(candidates),
        "all_pattern_counts": dict(sorted(pattern_counts.items())),
        "selected": len(selected),
        "selected_per_pattern": selected_per_pattern,
        "selected_mode_counts": dict(sorted(selected_mode_counts.items())),
        "selected_cut_counts": dict(sorted(selected_cut_counts.items())),
        "selected_product_counts": dict(sorted(selected_product_counts.items())),
        "selected_boundary_counts": selected_boundary_counts,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
