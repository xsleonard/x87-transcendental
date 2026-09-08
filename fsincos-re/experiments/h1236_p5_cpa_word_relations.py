#!/usr/bin/env python3
"""Audit word-level interpretations of the R1231 CPA/FADD candidate.

R1231 was discovered as equality between bit 2 of the final-FADD half
distance and one conditional-sum bit in the second Horner FMUL's P5-aligned
four-bit carry-select block.  A one-bit equality is structurally suggestive,
but it is not yet an explanation.  This pass reconstructs the complete
conditional four-bit words and tests a fixed family of ordinary unsigned,
signed, carry, borrow, and modular relations with the FADD distance.

The labels are the cached causal R1200 classifications.  Rules are ranked
first by whether they include both carry-impossible targets, then by whether
they ever fire on a known regression.  No processor instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from h1172_p5_cpa_predictor_mine import add_cpa_features, product_state
from h1184_upstream_halfway_audit import quantize, schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import scalar_schedule
from h1224_r1200_named_wire_audit import TARGETS, read_classifications


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed4(value: int) -> int:
    return value - 16 if value & 8 else value


def word(values: dict[str, int], stem: str, assumed: int) -> int:
    return sum(values[f"{stem}.sum{assumed}.b{bit}"] << bit
               for bit in range(4))


def relations(q: int, value: int) -> dict[str, int]:
    """Return fixed arithmetic relations; there are no learned constants."""
    q4 = q & 15
    qneg = (-q) & 15
    complement = value ^ 15
    return {
        "word.eq.q": int(value == q4),
        "word.lt.q": int(value < q4),
        "word.le.q": int(value <= q4),
        "word.gt.q": int(value > q4),
        "word.ge.q": int(value >= q4),
        "word.eq.-q.mod16": int(value == qneg),
        "word.lt.-q.mod16": int(value < qneg),
        "word.ge.-q.mod16": int(value >= qneg),
        "notword.eq.q": int(complement == q4),
        "notword.lt.q": int(complement < q4),
        "notword.ge.q": int(complement >= q4),
        "carry.word+q": int(value + q4 >= 16),
        "carry.word-q": int(value >= q4),
        "carry.word+(-q)": int(value + qneg >= 16),
        "carry.notword+q": int(complement + q4 >= 16),
        "carry.notword+(-q)": int(complement + qneg >= 16),
        "signed.same_sign.q-4": int((signed4(value) < 0) == (q < 4)),
        "msb.eq.qbit2": int(((value >> 3) & 1) == ((q >> 2) & 1)),
        "parity.eq.qparity": int((value & 1) == (q & 1)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("changes", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    classifications = read_classifications(args.changes)
    operands = sorted(classifications)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    records = []
    for row in rows:
        operations = schedule(row)
        _, adds = scalar_schedule(row, True)
        firing = [stage for stage, fields in adds.items() if fields["fires"]]
        if len(firing) != 1:
            raise RuntimeError(f"expected one R1200 event for {row['op']}: {firing}")
        stage = firing[0]
        chain = stage.split(".", 1)[0]
        fourth = quantize(operations["fourth"], 67, False)
        first_add = quantize(operations[f"{chain}.add1"], 64, True)
        sum_vector, carry_vector, cut = product_state(
            fourth.significand, first_add.significand)
        values: dict[str, int] = {}
        add_cpa_features(values, "P", sum_vector, carry_vector, cut)
        values = {name[2:]: int(value) for name, value in values.items()}
        words = {}
        for alignment in ("p5", "abs", "cut"):
            for relative in range(-4, 5):
                stem = f"{alignment}.w04.rel{relative:+d}"
                for assumed in (0, 1):
                    words[f"{stem}.sum{assumed}"] = word(
                        values, stem, assumed)
                cin = values[f"{stem}.cin"]
                words[f"{stem}.selected"] = words[
                    f"{stem}.sum{cin}"]
        records.append({
            "op": row["op"],
            "classification": classifications[row["op"]],
            "target": int(row["op"] in TARGETS),
            "stage": stage,
            "q": int(adds[stage]["half_delta"]),
            "words": words,
        })

    scores = []
    for word_name in sorted(records[0]["words"]):
        relation_names = relations(
            records[0]["q"], records[0]["words"][word_name]).keys()
        for relation_name in relation_names:
            for invert in (0, 1):
                target_miss = regression_fires = optional_fix_miss = 0
                total_errors = 0
                for record in records:
                    prediction = relations(
                        record["q"], record["words"][word_name]
                    )[relation_name] ^ invert
                    wanted = int(record["classification"] == "fix")
                    wrong = prediction != wanted
                    total_errors += wrong
                    target_miss += bool(record["target"] and not prediction)
                    regression_fires += bool(
                        record["classification"] == "regression" and prediction)
                    optional_fix_miss += bool(
                        record["classification"] == "fix"
                        and not record["target"] and not prediction)
                scores.append((
                    target_miss, regression_fires, optional_fix_miss,
                    total_errors, invert, relation_name, word_name,
                ))
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(records)}\n")
        target.write(f"word_forms\t{len(records[0]['words'])}\n")
        target.write(f"relations\t{len(relations(1, 0))}\n")
        target.write("\n[ranking]\n")
        target.write(
            "target_miss\tregression_fires\toptional_fix_miss\t"
            "total_errors\tinvert\trelation\tword\n")
        for score in scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[primary-block diagnostics]\n")
        target.write(
            "op\tclassification\ttarget\tstage\tq\t"
            "sum0\tsum1\tcin\tselected\tcurrent_rule\n")
        stem = "p5.w04.rel+0"
        for record in records:
            sum0 = record["words"][f"{stem}.sum0"]
            sum1 = record["words"][f"{stem}.sum1"]
            # Conditional words always differ by one modulo 16.  The selected
            # word reveals whether the candidate's assumed carry is physical.
            selected = record["words"][f"{stem}.selected"]
            cin = int(selected == sum1 and sum0 != sum1)
            current = int(((sum0 >> 3) & 1) == ((record["q"] >> 2) & 1))
            target.write("\t".join(map(str, (
                record["op"], record["classification"], record["target"],
                record["stage"], record["q"], sum0, sum1, cin, selected,
                current,
            ))) + "\n")

    print(
        f"wrote {args.report} operands={len(records)} "
        f"words={len(records[0]['words'])} best={scores[0]}", flush=True)


if __name__ == "__main__":
    main()
