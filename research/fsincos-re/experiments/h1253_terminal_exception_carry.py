#!/usr/bin/env python3
"""Search for the carry that complements terminal digit bit one.

On the four post-R1237 collision cells, 219/228 hardware carries equal bit
one of the three-bit terminal digit.  The remaining nine rows comprise all
six misses plus three controls already handled by the incumbent scalar rule.
That shape suggests a base digit bit XOR a carry from the other arithmetic
terms.  This audit directly scores fixed circuit wires and product-word
relations against that nine-row exception carry.

No operand identity or input-space boundary is used.  Sparse affine results
are localization evidence only; word carries/borrows are preferred because
they have a direct arithmetic interpretation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1201_post_r1186_structural_partition import structural_features
from h1248_terminal_wire_relation_mine import coordinate_features
from h1250_terminal_product_word_relations import (
    compatible_pairs,
    coordinate_words,
    product_words,
    relations,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def family(name: str) -> str:
    return name.split(".", 1)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        rows = [
            row for row in csv.DictReader(source, delimiter="\t")
            if row["physical_status"] == "constraining"
        ]

    columns: dict[str, int] = defaultdict(int)
    truth = 0
    word_records = []
    schema = None
    for index, row in enumerate(rows):
        features = {
            **structural_features(row),
            **coordinate_features(row),
        }
        if schema is None:
            schema = set(features)
        elif set(features) != schema:
            raise RuntimeError("feature schema changed")
        for name, value in features.items():
            columns[name] |= int(bool(value)) << index
        digit_bit = (int(row["low3"]) >> 1) & 1
        exception = int(row["physical_label"]) ^ digit_bit
        truth |= exception << index
        word_records.append((row, product_words(row), coordinate_words(row)))
        if (index + 1) % 50 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)

    all_mask = (1 << len(rows)) - 1
    bit_ranking = []
    for name, pattern in columns.items():
        direct_bad = (pattern ^ truth).bit_count()
        inverse_bad = (pattern ^ truth ^ all_mask).bit_count()
        bit_ranking.append((direct_bad, "direct", name))
        bit_ranking.append((inverse_bad, "inverse", name))
    bit_ranking.sort()

    by_pattern: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        by_pattern[pattern].append(name)
    patterns = sorted(by_pattern)
    pattern_index = {pattern: index for index, pattern in enumerate(patterns)}
    representatives = [
        min(by_pattern[pattern], key=lambda name: (len(name), name))
        for pattern in patterns
    ]

    pairs = []
    for left_index, left_pattern in enumerate(patterns):
        for relation_name, right_pattern in (
            ("xor", truth ^ left_pattern),
            ("xnor", truth ^ left_pattern ^ all_mask),
        ):
            right_index = pattern_index.get(right_pattern)
            if right_index is None or right_index <= left_index:
                continue
            left = representatives[left_index]
            right = representatives[right_index]
            if family(left) == family(right):
                continue
            pairs.append((relation_name, left, right))

    triples = []
    for left_index, left_pattern in enumerate(patterns):
        left = representatives[left_index]
        for middle_index in range(left_index + 1, len(patterns)):
            right_pattern = truth ^ left_pattern ^ patterns[middle_index]
            right_index = pattern_index.get(right_pattern)
            if right_index is None or right_index <= middle_index:
                continue
            middle = representatives[middle_index]
            right = representatives[right_index]
            if len({family(left), family(middle), family(right)}) < 2:
                continue
            triples.append((
                len(left) + len(middle) + len(right), left, middle, right,
            ))
            if len(triples) >= 20000:
                break
        if len(triples) >= 20000:
            break
    triples.sort()

    first_words, first_coordinates = word_records[0][1:]
    word_candidates = list(compatible_pairs(first_words, first_coordinates))
    word_ranking = []
    for relation_family, left_name, right_name in word_candidates:
        for relation_name in relations(0, 0):
            target_miss = control_fire = target_fire = 0
            for row, words, coordinates in word_records:
                values = {**words, **coordinates}
                prediction = relations(
                    values[left_name], values[right_name]
                )[relation_name]
                expected = (int(row["physical_label"])
                            ^ ((int(row["low3"]) >> 1) & 1))
                wrong = prediction != expected
                is_exception = bool(expected)
                target_miss += wrong and is_exception
                control_fire += prediction and not is_exception
                target_fire += prediction and is_exception
            word_ranking.append((
                target_miss + control_fire, target_miss, control_fire,
                -target_fire, relation_family, relation_name,
                left_name, right_name,
            ))
    word_ranking.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"exception_carry_ones\t{truth.bit_count()}\n")
        target.write(f"bit_features\t{len(columns)}\n")
        target.write(f"unique_patterns\t{len(patterns)}\n")
        target.write(f"exact_affine_pairs\t{len(pairs)}\n")
        target.write(f"exact_affine_triples\t{len(triples)}\n")
        target.write(f"word_candidates\t{len(word_candidates)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")

        target.write("\n[bit ranking]\n")
        target.write("errors\torientation\tfeature\n")
        for score in bit_ranking[:1000]:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[exact affine pairs]\n")
        target.write("relation\tleft\tright\n")
        for match in pairs[:5000]:
            target.write("\t".join(match) + "\n")

        target.write("\n[exact affine triples]\n")
        target.write("left\tmiddle\tright\n")
        for _, left, middle, right in triples[:5000]:
            target.write(f"{left}\t{middle}\t{right}\n")

        target.write("\n[word relation ranking]\n")
        target.write(
            "errors\texception_miss\tcontrol_fire\texception_fire\t"
            "family\trelation\tleft\tright\n"
        )
        for score in word_ranking[:3000]:
            rendered = (*score[:3], -score[3], *score[4:])
            target.write("\t".join(map(str, rendered)) + "\n")

        target.write("\n[exception rows]\n")
        target.write("op\tmodel_miss\tphysical_carry\tlow3\n")
        for row in rows:
            digit_bit = (int(row["low3"]) >> 1) & 1
            if int(row["physical_label"]) ^ digit_bit:
                target.write(
                    f"{row['op']}\t{int(row['label'] == 'POS')}\t"
                    f"{row['physical_label']}\t{row['low3']}\n"
                )

    print(
        f"wrote {args.report} rows={len(rows)} exceptions={truth.bit_count()} "
        f"pairs={len(pairs)} triples={len(triples)} "
        f"best_bit={bit_ranking[0]} best_word={word_ranking[0][:8]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
