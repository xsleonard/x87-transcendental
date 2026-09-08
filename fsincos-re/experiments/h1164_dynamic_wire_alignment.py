#!/usr/bin/env python3
"""Search compact phase-indexed circuit wires for the upper R59 residual.

The earlier h1110/h1120 searches gave every row the same named bit offset.
That can miss a fixed physical mux whose selected bit moves with normalization
or radix phase.  This experiment permits only the small affine index laws

    index = constant + x
    index = constant - x
    index = constant +/- x +/- y

where x and y are already reconstructed pipeline state.  It then tests all
sixteen Boolean gates of the incumbent carry and the selected wire.  No
operand bits, operand identities, learned thresholds, or branch labels enter
the index law.
"""

import argparse
import csv
import hashlib
import os
import re
from collections import defaultdict

import numpy as np

from h1101_p5_tree_mine import row_features as product_features
from h1106_terminal_prefix_mine import terminal_features
from h1110_carry_gate_mine import allmode_allowed, extract_carry_state


INDEX_AT_END = re.compile(r"^(.*)\.([+-][0-9]+|[0-9]{2})$")
INDEX_INSIDE = (
    re.compile(r"^(.*\.rel\.)([+-][0-9]+)(\..*)$"),
    re.compile(r"^(.*\.end)([+-][0-9]+)(\..*)$"),
    re.compile(r"^(.*\.rel)([+-][0-9]+)(\..*)$"),
    re.compile(r"^(.*\.abs\.)([0-9]{2})(\..*)$"),
)
GATE_NAMES = {
    0x0: "0",
    0x1: "nor(c,f)",
    0x2: "not(c)&f",
    0x3: "not(c)",
    0x4: "c&not(f)",
    0x5: "not(f)",
    0x6: "c xor f",
    0x7: "nand(c,f)",
    0x8: "c&f",
    0x9: "c xnor f",
    0xA: "f",
    0xB: "not(c)|f",
    0xC: "c",
    0xD: "c|not(f)",
    0xE: "c|f",
    0xF: "1",
}


def read_tsv(path):
    with open(path) as source:
        return list(csv.DictReader(source, delimiter="\t"))


def source_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def indexed_name(name):
    """Return a family template and the one movable bit/block index."""
    match = INDEX_AT_END.match(name)
    if match:
        return match.group(1), int(match.group(2))
    for pattern in INDEX_INSIDE:
        match = pattern.match(name)
        if match:
            return match.group(1) + "*" + match.group(3), int(match.group(2))
    return None


def normalized_state(row):
    """Small signed coordinates already present in the reconstructed pipe."""
    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    cut = int(row["k"])
    equal = ~(s_value ^ b_value)
    run_up = 0
    while run_up < 32 and ((equal >> (cut + run_up)) & 1):
        run_up += 1
    run_down = 0
    while run_down < 32 and cut - 1 - run_down >= 0 \
            and ((equal >> (cut - 1 - run_down)) & 1):
        run_down += 1
    phase = int(row["ce"]) % 8
    return {
        "theta": int(row["theta"]),
        "e": -int(row["ce"]) - 72,
        "a": int(row["s4"]) - 66,
        "h": 64 - int(row["rsh"]),
        "side": int(row["side"]),
        "b1": int(row["b1"]),
        "b2": int(row["b2"]),
        "low3": int(row["low3"]) - 4,
        "dist": int(row["dist"]) - 8,
        "payload": int(row["payload"]) - 4,
        "rscale": -int(row["rscale"]) - 80,
        "k": int(row["k"]) - 8,
        "f4exp": int(row["tc_f4_exp"]) + 76,
        "leftexp": int(row["tc_left_exp"]) + 72,
        "rightexp": int(row["tc_right_exp"]) + 80,
        "mulexp": int(row["tc_mul_exp"]) + 72,
        # The shipped block-start law already demonstrates that the selector
        # consumes propagate-run state.  h1164's first pass omitted it from
        # the movable-index grammar; expose the exact recurrence coordinates.
        "runup": run_up,
        "rundown": run_down,
        "blockphase": (run_up + phase) % 8,
        "phase8": phase,
        "bsrel": 8 + ((8 - phase) % 8),
    }


def expression_bank(state_vectors):
    """Return unique constant/single/two-coordinate affine phase laws."""
    names = sorted(state_vectors[0])
    columns = {name: tuple(state[name] for state in state_vectors)
               for name in names}
    candidates = [("0", (0,) * len(state_vectors), 0)]
    for name in names:
        for sign in (-1, 1):
            values = tuple(sign * value for value in columns[name])
            text = ("-" if sign < 0 else "+") + name
            candidates.append((text, values, 1))
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            for left_sign in (-1, 1):
                for right_sign in (-1, 1):
                    values = tuple(left_sign * x + right_sign * y
                                   for x, y in zip(columns[left],
                                                   columns[right]))
                    text = "%s%s%s%s" % (
                        "-" if left_sign < 0 else "+", left,
                        "-" if right_sign < 0 else "+", right)
                    candidates.append((text, values, 2))
    # Several state coordinates are algebraically identical on this scope.
    # Keep the shortest, then lexical, spelling for each actual phase law.
    unique = {}
    for text, values, complexity in candidates:
        rank = (complexity, len(text), text)
        if values not in unique or rank < unique[values][0]:
            unique[values] = (rank, text, complexity)
    result = [(text, values, complexity)
              for values, (_, text, complexity) in unique.items()]
    result.sort(key=lambda item: (item[2], item[0]))
    return result


def bits_from_vector(vector):
    packed = np.packbits(np.asarray(vector, dtype=np.uint8),
                         bitorder="little")
    return int.from_bytes(packed.tobytes(), "little")


def gate_output_bits(carry_bits, feature_bits, universe, gate):
    not_carry = universe ^ carry_bits
    not_feature = universe ^ feature_bits
    states = (
        not_carry & not_feature,
        not_carry & feature_bits,
        carry_bits & not_feature,
        carry_bits & feature_bits,
    )
    output = 0
    for state, state_bits in enumerate(states):
        if (gate >> state) & 1:
            output |= state_bits
    return output


def format_index(constant, expression):
    if expression == "0":
        return str(constant)
    if not constant:
        return expression[1:] if expression.startswith("+") else expression
    return "%d%s" % (constant, expression)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("positive_allmode")
    parser.add_argument("control_allmode")
    parser.add_argument("output")
    parser.add_argument("--roots", default="Q,QX",
                        help="comma-separated product signal roots")
    parser.add_argument("--provider", choices=("product", "terminal"),
                        default="product")
    parser.add_argument("--cache",
                        help="optional validated npz feature-matrix cache")
    parser.add_argument("--per-positive", type=int, default=160)
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)

    positive_delta = allmode_allowed(args.positive_allmode)
    control_delta = allmode_allowed(args.control_allmode)
    all_rows = read_tsv(args.features)
    rows = []
    states = []
    required_flags = []
    for row in all_rows:
        bank = positive_delta if row["label"] == "POS" else control_delta
        state = extract_carry_state(row, bank[row["op"]])
        current, allowed = state[2], state[3]
        if not allowed or len(allowed) != 1:
            continue
        rows.append(row)
        states.append(state)
        required_flags.append(current not in allowed)

    roots = tuple(root for root in args.roots.split(",") if root)
    digest = source_digest(args.features)
    matrix = None
    feature_names = None
    if args.cache and os.path.exists(args.cache):
        cached = np.load(args.cache, allow_pickle=False)
        cached_digest = str(cached["source_sha256"].item())
        cached_roots_text = str(cached["roots"].item())
        cached_roots = tuple(cached_roots_text.split(",")) \
            if cached_roots_text else ()
        cached_provider = (str(cached["provider"].item())
                           if "provider" in cached else "product")
        if (cached_digest != digest or cached_roots != roots
                or cached_provider != args.provider):
            raise AssertionError(
                "feature cache does not match input/roots/provider")
        matrix = cached["matrix"]
        feature_names = [str(name) for name in cached["names"]]
        if matrix.shape[0] != len(rows):
            raise AssertionError("feature cache row count changed")
        print("loaded cache", args.cache, matrix.shape, flush=True)
    else:
        provider = (product_features if args.provider == "product"
                    else terminal_features)
        first = provider(rows[0])
        feature_names = sorted(
            name for name in first
            if (not roots or any(name == root or name.startswith(root + ".")
                                 for root in roots))
            and indexed_name(name) is not None)
        matrix = np.empty((len(rows), len(feature_names)), dtype=np.uint8)
        for index, row in enumerate(rows):
            values = first if index == 0 else provider(row)
            matrix[index] = [values[name] for name in feature_names]
            if (index + 1) % 5000 == 0:
                print("features", index + 1, "/", len(rows), flush=True)
        if args.cache:
            if os.path.exists(args.cache):
                raise AssertionError("cache appeared during generation")
            np.savez_compressed(
                args.cache, matrix=matrix,
                names=np.asarray(feature_names),
                source_sha256=np.asarray(digest),
                roots=np.asarray(",".join(roots)),
                provider=np.asarray(args.provider))
            print("wrote cache", args.cache, flush=True)

    families = defaultdict(dict)
    for column, name in enumerate(feature_names):
        family, index = indexed_name(name)
        families[family][index] = column
    families = {
        name: members for name, members in families.items()
        if sorted(members) == list(range(min(members), max(members) + 1))
    }
    static_bits = {
        (family, index): bits_from_vector(matrix[:, column])
        for family, members in families.items()
        for index, column in members.items()
    }

    row_state = [normalized_state(row) for row in rows]
    unique_states = sorted(set(tuple(state.items()) for state in row_state))
    state_number = {state: index for index, state in enumerate(unique_states)}
    row_state_ids = [state_number[tuple(state.items())] for state in row_state]
    state_vectors = [dict(items) for items in unique_states]
    state_masks = [0] * len(unique_states)
    for row_index, state_id in enumerate(row_state_ids):
        state_masks[state_id] |= 1 << row_index
    expressions = expression_bank(state_vectors)

    row_count = len(rows)
    universe = (1 << row_count) - 1
    required = sum((1 << index) for index, flag
                   in enumerate(required_flags) if flag)
    forbidden = universe ^ required
    current_bits = sum((state[2] << index)
                       for index, state in enumerate(states))
    predictor_scores = []
    literals_by_pattern = {}
    candidate_count = 0

    for family_index, (family, members) in enumerate(sorted(families.items())):
        low = min(members)
        high = max(members)
        for expression, state_values, complexity in expressions:
            groups = defaultdict(int)
            for state_id, value in enumerate(state_values):
                groups[value] |= state_masks[state_id]
            minimum = min(groups)
            maximum = max(groups)
            for constant in range(low - minimum, high - maximum + 1):
                feature_bits = 0
                for value, group_mask in groups.items():
                    feature_bits |= (group_mask
                                     & static_bits[family, constant + value])
                candidate_count += 1
                formula = "%s[%s]" % (
                    family, format_index(constant, expression))
                rank = (complexity, abs(constant), formula)
                for literal_value, literal_bits in (
                        (1, feature_bits), (0, universe ^ feature_bits)):
                    positive_bits = literal_bits & required
                    if not positive_bits:
                        continue
                    negative_bits = literal_bits & forbidden
                    pattern = (positive_bits, negative_bits)
                    literal = (rank, formula, literal_value,
                               positive_bits, negative_bits)
                    if pattern not in literals_by_pattern \
                            or literal[:3] < literals_by_pattern[pattern][:3]:
                        literals_by_pattern[pattern] = literal
                for gate in range(16):
                    output = gate_output_bits(
                        current_bits, feature_bits, universe, gate)
                    flip = output ^ current_bits
                    positive_bad = (required & ~flip).bit_count()
                    negative_bad = (forbidden & flip).bit_count()
                    score = (positive_bad + negative_bad,
                             positive_bad, negative_bad,
                             complexity, abs(constant), family,
                             expression, constant, gate, formula)
                    if len(predictor_scores) < 500:
                        predictor_scores.append(score)
                        if len(predictor_scores) == 500:
                            predictor_scores.sort()
                    elif score < predictor_scores[-1]:
                        predictor_scores[-1] = score
                        predictor_scores.sort()
        print("searched", family_index + 1, "/", len(families), family,
              "candidates", candidate_count, flush=True)

    predictor_scores.sort()
    literals = list(literals_by_pattern.values())
    selected = set()
    required_count = required.bit_count()
    for positive in range(row_count):
        if not ((required >> positive) & 1):
            continue
        choices = [
            (literal[4].bit_count(), -literal[3].bit_count(),
             literal[0], index)
            for index, literal in enumerate(literals)
            if (literal[3] >> positive) & 1
        ]
        choices.sort()
        selected.update(choice[3] for choice
                        in choices[:args.per_positive])
    selected_literals = [literals[index] for index in sorted(selected)]

    terms_by_coverage = {}
    for literal in selected_literals:
        if not literal[4]:
            coverage = literal[3]
            term = (coverage, (literal,))
            terms_by_coverage.setdefault(coverage, term)
    for left_index, left in enumerate(selected_literals):
        for right in selected_literals[left_index + 1:]:
            coverage = left[3] & right[3]
            if not coverage or left[4] & right[4]:
                continue
            term = (coverage, (left, right))
            old = terms_by_coverage.get(coverage)
            signature = tuple((item[0], item[1], item[2]) for item in term[1])
            if old is None or signature < tuple(
                    (item[0], item[1], item[2]) for item in old[1]):
                terms_by_coverage[coverage] = term
    terms = sorted(terms_by_coverage.values(),
                   key=lambda term: (-term[0].bit_count(), len(term[1]),
                                     tuple(item[1] for item in term[1])))
    uncovered = required
    cover = []
    while uncovered:
        choices = [term for term in terms if term[0] & uncovered]
        if not choices:
            break
        term = max(choices, key=lambda item: (
            (item[0] & uncovered).bit_count(), item[0].bit_count(),
            -len(item[1])))
        cover.append(term)
        uncovered &= ~term[0]

    with open(args.output, "x") as target:
        target.write("source_sha256\t%s\nrows_total\t%d\n"
                     "rows_constraining\t%d\nrequired_flip\t%d\n"
                     "forbidden_flip\t%d\nprovider\t%s\nroots\t%s\n"
                     "features\t%d\n"
                     "families\t%d\nstates\t%d\nexpressions\t%d\n"
                     "dynamic_candidates\t%d\nunique_literals\t%d\n"
                     "selected_literals\t%d\nzero_forbidden_terms\t%d\n" % (
                         digest, len(all_rows), row_count, required_count,
                         forbidden.bit_count(), args.provider,
                         ",".join(roots),
                         len(feature_names), len(families), len(unique_states),
                         len(expressions), candidate_count, len(literals),
                         len(selected_literals), len(terms)))
        target.write("\n[best carry gates]\n")
        target.write("all_bad\tpositive_bad\tnegative_bad\tcomplexity\t"
                     "abs_constant\tfamily\texpression\tconstant\tgate\t"
                     "formula\n")
        for score in predictor_scores[:200]:
            rendered = list(score)
            rendered[8] = "%s/%x" % (GATE_NAMES[score[8]], score[8])
            target.write("\t".join(map(str, rendered)) + "\n")
        target.write("\n[best zero-forbidden terms]\n")
        target.write("coverage_count\tpositive_rows\tterm\n")
        required_indices = [index for index in range(row_count)
                            if (required >> index) & 1]
        required_ord = {row_index: number
                        for number, row_index in enumerate(required_indices)}
        for coverage, term_literals in terms[:500]:
            positives = [str(required_ord[index]) for index in required_indices
                         if (coverage >> index) & 1]
            text = " & ".join("%s=%d" % (item[1], item[2])
                              for item in term_literals)
            target.write("%d\t%s\t%s\n" % (
                coverage.bit_count(), ",".join(positives), text))
        target.write("\n[greedy zero-forbidden cover]\n")
        target.write("terms\t%d\nuncovered\t%d\n" %
                     (len(cover), uncovered.bit_count()))
        for coverage, term_literals in cover:
            positives = [str(required_ord[index]) for index in required_indices
                         if (coverage >> index) & 1]
            text = " & ".join("%s=%d" % (item[1], item[2])
                              for item in term_literals)
            target.write("%d\t%s\t%s\n" % (
                coverage.bit_count(), ",".join(positives), text))
        target.write("\n[required row numbering]\n")
        for number, row_index in enumerate(required_indices):
            target.write("%d\t%s\t%s\n" % (
                number, rows[row_index]["op"], rows[row_index]["branch"]))

    print("wrote", args.output, "candidates", candidate_count,
          "best", predictor_scores[0][:10], "terms", len(terms),
          "cover", len(cover), "uncovered", uncovered.bit_count())


if __name__ == "__main__":
    main()
