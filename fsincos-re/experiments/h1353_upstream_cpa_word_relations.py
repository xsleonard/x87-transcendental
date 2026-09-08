#!/usr/bin/env python3
"""Search physical four-bit word/comparator views of the high-q selector.

The h1351 blind bank falsifies the h1350 Boolean mux and proves that cut 63
is not a universal enable.  A carry-select tree is naturally observed as a
four-bit word and a comparator/carry response, however, rather than as one or
two isolated wires.  This audit therefore assembles fixed four-bit words at
the documented P5 block origin, ordinary nibble origin, and each producer's
cut-relative block from every reconstructed square/fourth redundant bus.
It adds the corresponding current-product CPA words and literal per-stage
rounding words, then compares each word to fixed encodings of q.

This is a bounded representation search, not a promoted selector.  A low
error or exact relation still needs a physical routing argument and another
frozen challenge.  Hardware labels are immutable inputs; no x87 instruction
is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import cut_fields
from h1296_faddword_deeper_tree import event
from h1322_attached_history_field_audit import NATIVE
from h1329_highq_cpa_word_relations import q_encodings, relations, words
from h1346_highq_power_tree_wire_audit import power_features


BIT_NAME = re.compile(r"^(.*)\.b([0-9]+)$")
WIDTH = 4


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_labels(paths: list[Path]) -> tuple[dict[str, int], dict[str, int]]:
    labels: dict[str, int] = {}
    banks: dict[str, int] = {}
    for bank, path in enumerate(paths):
        with path.open(newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                verdict = row.get("actual_verdict", row.get("verdict", ""))
                if verdict not in ("wide", "predecessor"):
                    raise RuntimeError(f"non-binary direct label: {row}")
                operand = row["op"].lower()
                wanted = int(verdict == "wide")
                previous = labels.setdefault(operand, wanted)
                if previous != wanted:
                    raise RuntimeError(f"factor-label conflict for {operand}")
                prior_bank = banks.setdefault(operand, bank)
                if prior_bank != bank:
                    raise RuntimeError(f"operand appears in two banks: {operand}")
    return labels, banks


def word(bits: dict[int, int], start: int) -> int:
    return sum(bits.get(start + offset, 0) << offset
               for offset in range(WIDTH))


def bus_words(values: dict[str, int], cuts: dict[str, int]) -> dict[str, int]:
    buses: dict[str, dict[int, int]] = defaultdict(dict)
    for name, value in values.items():
        match = BIT_NAME.match(name)
        if match:
            buses[match.group(1)][int(match.group(2))] = int(value)

    result = {}
    for stem, bits in buses.items():
        if stem.startswith("square."):
            local_cut = cuts["square"]
        elif stem.startswith("fourth."):
            local_cut = cuts["fourth"]
        else:
            local_cut = cuts["current"]
        starts = set(range(0, 136 - WIDTH + 1, WIDTH))
        starts.update(range(2, 136 - WIDTH + 1, WIDTH))
        for origin in (0, 2):
            base = origin + ((local_cut - origin) // WIDTH) * WIDTH
            starts.update(base + relative * WIDTH for relative in range(-4, 5))
        starts = {start for start in starts if 0 <= start <= 136 - WIDTH}
        for start in sorted(starts):
            result[f"{stem}.w04.abs{start:03d}"] = word(bits, start)
    return result


def rounding_words(row: dict[str, str]) -> dict[str, int]:
    result = {}
    for stage, (bits, nearest) in NATIVE.items():
        fields = cut_fields(schedule(row)[stage], bits)
        shift = int(fields["shift"])
        remainder = int(fields["remainder"])
        retained = int(fields["retained"])
        top = (remainder >> (shift - WIDTH)
               if shift >= WIDTH else remainder << (WIDTH - shift))
        result[f"round.{stage}.discarded.top4"] = top & 15
        result[f"round.{stage}.discarded.bottom4"] = remainder & 15
        result[f"round.{stage}.retained.bottom4"] = retained & 15
    return result


def enable_masks(records: list[dict[str, object]]) -> dict[str, int]:
    masks = {"all": (1 << len(records)) - 1}
    for cut in (63, 64):
        masks[f"cut{cut}"] = sum(
            (int(record["cut"]) == cut) << index
            for index, record in enumerate(records))
    return masks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels, banks = load_labels(args.direct_label)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    records = []
    schema = None
    for index, row in enumerate(rows):
        operations = schedule(row)
        item = event(row, "negative.add2")
        q = int(item["q"])
        product = int(item["product"])
        cut = product.bit_length() - 67
        if not (
            5 <= q <= 7
            and int(item["increments"])
            and ((product >> 65) & 1) == ((q >> 2) & 1)
        ):
            raise RuntimeError(f"not a high-q separator: {row['op']}")
        square_cut = operations["square"].magnitude.bit_length() - 67
        fourth_cut = operations["fourth"].magnitude.bit_length() - 67
        values = power_features(row)
        assembled = bus_words(values, {
            "square": square_cut, "fourth": fourth_cut, "current": cut})
        assembled.update({f"current.{name}": value
                          for name, value in words(item).items()})
        assembled.update(rounding_words(row))
        names = tuple(sorted(assembled))
        if schema is None:
            schema = names
        elif names != schema:
            raise RuntimeError("word schema changed")
        records.append({
            "op": row["op"], "wanted": labels[row["op"]],
            "bank": banks[row["op"]], "q": q, "cut": cut,
            "words": assembled,
        })
        if (index + 1) % 32 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)
    if schema is None:
        raise SystemExit("empty label set")

    signature_names: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for name in schema:
        signature_names[tuple(
            int(record["words"][name]) for record in records)].append(name)

    target = sum(int(record["wanted"]) << index
                 for index, record in enumerate(records))
    mask = (1 << len(records)) - 1
    enables = enable_masks(records)
    best = []
    exact_count = 0
    candidate_count = 0
    relation_names = tuple(relations(0, 0))
    encoding_names = tuple(q_encodings(5))
    for word_signature, aliases in signature_names.items():
        for encoding_name in encoding_names:
            references = tuple(q_encodings(int(record["q"]))[encoding_name]
                               for record in records)
            for relation_name in relation_names:
                predicate = sum(
                    relations(left, right)[relation_name] << index
                    for index, (left, right) in enumerate(
                        zip(word_signature, references)))
                for enable_name, enable in enables.items():
                    for invert in (0, 1):
                        predicted = ((predicate ^ (mask if invert else 0))
                                     & enable)
                        errors = (predicted ^ target).bit_count()
                        false_negatives = (target & ~predicted & mask).bit_count()
                        false_positives = (predicted & ~target & mask).bit_count()
                        item_score = (
                            errors, false_negatives, false_positives,
                            predicted.bit_count(), enable_name,
                            relation_name, invert, encoding_name,
                            len(aliases), aliases[0],
                        )
                        candidate_count += 1
                        exact_count += errors == 0
                        if len(best) < 2048 or item_score < best[-1]:
                            best.append(item_score)
                            best.sort()
                            del best[2048:]

    best_item = best[0]
    best_name = best_item[-1]
    best_signature = next(
        signature for signature, aliases in signature_names.items()
        if best_name in aliases)
    best_reference = tuple(q_encodings(int(record["q"]))[best_item[7]]
                           for record in records)
    best_predicate = tuple(
        relations(left, right)[best_item[5]] ^ best_item[6]
        for left, right in zip(best_signature, best_reference))
    best_enable = enables[best_item[4]]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tfixed_four_bit_tree_words_compared_to_q\n")
        output.write(f"operands\t{len(records)}\n")
        output.write(f"positive_operands\t{target.bit_count()}\n")
        output.write(f"word_sources\t{len(schema)}\n")
        output.write(f"distinct_word_signatures\t{len(signature_names)}\n")
        output.write(f"candidates\t{candidate_count}\n")
        output.write(f"exact_candidates\t{exact_count}\n")
        output.write("enable_grammar\tall,cut63,cut64\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\tfalse_negatives\tfalse_positives\t"
            "predicted_positives\tenable\trelation\tinvert\tq_encoding\t"
            "word_aliases\tword\n")
        for item_score in best:
            output.write("\t".join(map(str, item_score)) + "\n")
        output.write("\n[best diagnostics]\n")
        output.write(
            "op\twanted_wide\tbank\tq\tcut\tword\treference\t"
            "relation_after_invert\tpredicted_wide\n")
        for index, (record, word_value, reference, predicate) in enumerate(
                zip(records, best_signature, best_reference, best_predicate)):
            predicted = predicate & ((best_enable >> index) & 1)
            output.write("\t".join(map(str, (
                record["op"], record["wanted"], record["bank"],
                record["q"], record["cut"], f"{word_value:x}",
                f"{reference:x}", predicate, predicted,
            ))) + "\n")
        output.write("\n[counts]\n")
        counts = Counter((record["bank"], record["q"], record["cut"],
                          record["wanted"]) for record in records)
        for key, count in sorted(counts.items()):
            output.write(
                f"bank{key[0]}.q{key[1]}.cut{key[2]}.label{key[3]}\t"
                f"{count}\n")

    print(
        f"wrote {args.report}: operands={len(records)} words={len(schema)} "
        f"signatures={len(signature_names)} candidates={candidate_count} "
        f"exact={exact_count} best={best_item[:8]} {best_name}",
        flush=True,
    )


if __name__ == "__main__":
    main()
