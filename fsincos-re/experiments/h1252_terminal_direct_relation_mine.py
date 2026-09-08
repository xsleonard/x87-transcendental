#!/usr/bin/env python3
"""Mine direct structural predictors of the terminal hardware carry.

Earlier relation audits searched for a signal that was true only on model
misses.  A real alternate representation need not be sparse: it should
compute the hardware carry on every row, differing from the incumbent only
where the incumbent representation fails.  This audit therefore scores the
same fixed circuit wires and product-word relations directly against the
cached carry, including sparse three-wire XOR identities as a bounded test
of an affine carry network.

The three-wire search is mechanism discovery, not a promotion criterion.
Any identity must have an arithmetic interpretation and survive a separately
generated dense wall before it can enter the emulator.
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


def bit_rank(pattern: int, truth: int, all_mask: int, name: str):
    direct_bad = (pattern ^ truth).bit_count()
    inverse_bad = ((pattern ^ all_mask) ^ truth).bit_count()
    if direct_bad <= inverse_bad:
        return direct_bad, "direct", name
    return inverse_bad, "inverse", name


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
    if not rows:
        raise SystemExit("no constraining rows")

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
        truth |= int(row["physical_label"]) << index
        word_records.append((row, product_words(row), coordinate_words(row)))
        if (index + 1) % 50 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)

    all_mask = (1 << len(rows)) - 1
    bit_ranking = sorted(
        bit_rank(pattern, truth, all_mask, name)
        for name, pattern in columns.items()
    )

    by_pattern: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        by_pattern[pattern].append(name)
    patterns = sorted(by_pattern)
    pattern_index = {pattern: index for index, pattern in enumerate(patterns)}

    pair_matches = []
    for left_index, left_pattern in enumerate(patterns):
        for relation_name, wanted in (
            ("xor", left_pattern ^ truth),
            ("xnor", left_pattern ^ truth ^ all_mask),
        ):
            right_index = pattern_index.get(wanted)
            if right_index is None or right_index <= left_index:
                continue
            left = min(by_pattern[left_pattern], key=lambda name: (len(name), name))
            right = min(by_pattern[wanted], key=lambda name: (len(name), name))
            if family(left) == family(right):
                continue
            pair_matches.append((relation_name, left, right))

    # Use one shortest representative per unique column.  Requiring ordered
    # pattern indexes avoids permutations; requiring at least two feature
    # families avoids rendering an internal bank's aliases as a discovery.
    representatives = [
        min(by_pattern[pattern], key=lambda name: (len(name), name))
        for pattern in patterns
    ]
    triple_matches = []
    for left_index, left_pattern in enumerate(patterns):
        left = representatives[left_index]
        for middle_index in range(left_index + 1, len(patterns)):
            middle_pattern = patterns[middle_index]
            right_pattern = truth ^ left_pattern ^ middle_pattern
            right_index = pattern_index.get(right_pattern)
            if right_index is None or right_index <= middle_index:
                continue
            middle = representatives[middle_index]
            right = representatives[right_index]
            if len({family(left), family(middle), family(right)}) < 2:
                continue
            triple_matches.append((
                len(left) + len(middle) + len(right), left, middle, right,
            ))
            if len(triple_matches) >= 20000:
                break
        if len(triple_matches) >= 20000:
            break
    triple_matches.sort()

    first_words, first_coordinates = word_records[0][1:]
    word_candidates = list(compatible_pairs(first_words, first_coordinates))
    word_ranking = []
    for relation_family, left_name, right_name in word_candidates:
        for relation_name in relations(0, 0):
            target_miss = control_miss = 0
            for row, words, coordinates in word_records:
                values = {**words, **coordinates}
                prediction = relations(
                    values[left_name], values[right_name]
                )[relation_name]
                wrong = prediction != int(row["physical_label"])
                target_miss += wrong and row["label"] == "POS"
                control_miss += wrong and row["label"] != "POS"
            word_ranking.append((
                target_miss + control_miss, target_miss, control_miss,
                relation_family, relation_name, left_name, right_name,
            ))
    word_ranking.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"hardware_carry_ones\t{truth.bit_count()}\n")
        target.write(f"bit_features\t{len(columns)}\n")
        target.write(f"unique_bit_patterns\t{len(patterns)}\n")
        target.write(f"exact_pair_relations\t{len(pair_matches)}\n")
        target.write(f"exact_three_xor_relations\t{len(triple_matches)}\n")
        target.write(f"word_candidates\t{len(word_candidates)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")

        target.write("\n[direct bit ranking]\n")
        target.write("errors\torientation\tfeature\n")
        for score in bit_ranking[:1000]:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[exact two-wire affine relations]\n")
        target.write("relation\tleft\tright\n")
        for match in pair_matches[:5000]:
            target.write("\t".join(match) + "\n")

        target.write("\n[exact three-wire xor relations]\n")
        target.write("left\tmiddle\tright\n")
        for _, left, middle, right in triple_matches[:5000]:
            target.write(f"{left}\t{middle}\t{right}\n")

        target.write("\n[direct product-word relation ranking]\n")
        target.write(
            "errors\ttarget_miss\tcontrol_miss\tfamily\trelation\t"
            "left\tright\n"
        )
        for score in word_ranking[:3000]:
            target.write("\t".join(map(str, score)) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} bits={len(columns)} "
        f"pairs={len(pair_matches)} triples={len(triple_matches)} "
        f"best_bit={bit_ranking[0]} best_word={word_ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
