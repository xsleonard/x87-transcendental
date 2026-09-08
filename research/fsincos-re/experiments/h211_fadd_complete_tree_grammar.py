#!/usr/bin/env python3
"""Close the missing four-term literal FADD program grammar.

h207 replays literal P5 FADD/FMUL carriers through seven Tang reconstruction
topologies.  Four labeled terms have fifteen commutative full binary addition
trees, however, so eight exact parenthesizations remained untested.  This pass
generates the complete grammar, proves the seven old trees are members, and
tests only the eight new programs with h207's physical controls and gates.

Each non-root addition writes a temporary in deterministic postorder and may
retain its normalized/raw carrier or materialize a physical 64-bit result.
The root addition independently enables normalization.  This is the complete
algebraically exact, unconditional three-FADD grammar; conditional controls
are intentionally deferred until the fixed programs have been excluded.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib
import itertools
from typing import Any

import h58_constraint_search as h58
import h60_round16_parity as h60
import h170_fsin_table_correction_search as h170
import h182_table_joint_terminal_edges as h182
import h206_p5_fadd_complete as h206
import h207_tang_literal_fadd as h207


Tree = Any
LEAVES = ("lead", "linear", "q", "p")


def tree_key(tree: Tree) -> str:
    if isinstance(tree, str):
        return tree
    return f"({tree_key(tree[0])}+{tree_key(tree[1])})"


def node(left: Tree, right: Tree) -> Tree:
    return (
        (left, right)
        if tree_key(left) <= tree_key(right)
        else (right, left)
    )


def trees(leaves: frozenset[str]) -> frozenset[Tree]:
    if len(leaves) == 1:
        return frozenset(leaves)
    result = set()
    ordered = sorted(leaves)
    anchor = ordered[0]
    for size in range(1, len(ordered)):
        for left_values in itertools.combinations(ordered, size):
            left_set = frozenset(left_values)
            # One side must contain the anchor, avoiding mirrored partitions.
            if anchor not in left_set:
                continue
            right_set = leaves - left_set
            for left in trees(left_set):
                for right in trees(right_set):
                    result.add(node(left, right))
    return frozenset(result)


KNOWN_TREES = {
    "correction": node("lead", node("linear", node("q", "p"))),
    "lead-linear": node(node("lead", "linear"), node("q", "p")),
    "lead-nonlinear": node(node("lead", node("q", "p")), "linear"),
    "lead-q": node(node("lead", "q"), node("linear", "p")),
    "lead-p": node(node("lead", "p"), node("linear", "q")),
    "serial-q-p": node(node(node("lead", "linear"), "q"), "p"),
    "serial-p-q": node(node(node("lead", "linear"), "p"), "q"),
}
ALL_TREES = tuple(sorted(trees(frozenset(LEAVES)), key=tree_key))
NEW_TREES = tuple(tree for tree in ALL_TREES if tree not in KNOWN_TREES.values())


@dataclasses.dataclass(frozen=True)
class Candidate:
    tree: Tree
    mode: str
    first: str
    second: str
    final_normalize: bool
    products: h207.ProductRoute

    def short(self) -> str:
        final = "norm" if self.final_normalize else "raw"
        return (
            f"tree={tree_key(self.tree)} {self.mode} "
            f"{self.first}/{self.second}/final-{final} "
            f"{self.products.short()}"
        )


def assert_grammar() -> None:
    if len(ALL_TREES) != 15:
        raise SystemExit(f"expected 15 trees, got {len(ALL_TREES)}")
    if len(set(KNOWN_TREES.values())) != 7:
        raise SystemExit("old topology map is not one-to-one")
    missing = set(KNOWN_TREES.values()) - set(ALL_TREES)
    if missing:
        raise SystemExit(f"old topology absent from grammar: {missing}")
    if len(NEW_TREES) != 8:
        raise SystemExit(f"expected 8 new trees, got {len(NEW_TREES)}")


def reconstruct(
    terms: h207.Terms, candidate: Candidate
) -> tuple[h206.Bus, tuple[h206.AddTrace, ...]]:
    values = {
        "lead": terms.lead,
        "linear": terms.linear,
        "q": terms.q_product,
        "p": terms.p_product,
    }
    actions = (candidate.first, candidate.second)
    action_index = 0
    traces = []

    def evaluate(tree: Tree, root: bool = False) -> h206.Bus:
        nonlocal action_index
        if isinstance(tree, str):
            return values[tree]
        left = evaluate(tree[0])
        right = evaluate(tree[1])
        if root:
            result, trace = h206.fadd(
                left,
                right,
                candidate.mode,
                normalize=candidate.final_normalize,
            )
        else:
            action = actions[action_index]
            action_index += 1
            result, trace = h207.add_action(
                left, right, candidate.mode, action
            )
        traces.append(trace)
        return result

    result = evaluate(candidate.tree, root=True)
    if action_index != 2 or len(traces) != 3:
        raise AssertionError((candidate.tree, action_index, len(traces)))
    return result, tuple(traces)


def local_values(point, candidate: Candidate, shared: bool):
    sine = reconstruct(
        h207.lane_terms(point, shared, False, candidate.products), candidate
    )[0].value()
    cosine = reconstruct(
        h207.lane_terms(point, shared, True, candidate.products), candidate
    )[0].value()
    if point.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate((sine, cosine), point.joint.observed.signed_n)


def hidden_values(point, candidate: Candidate):
    sine = local_values(point, candidate, False)[0]
    cosine = local_values(point, candidate, True)[1]
    return sine, cosine


def point_metric(point: h207.Point, candidate: Candidate | None):
    sine, cosine = (
        h207.current_values(point.prepared)
        if candidate is None
        else hidden_values(point.prepared, candidate)
    )
    sine_metric = h170.point_metric(point.prepared.joint.observed, sine)
    cosine_metric = (
        h182.point_metric(
            point.prepared.joint.cosine_outputs,
            point.prepared.joint.cosine_c1,
            cosine,
        )
        if point.cosine_hardware
        else (0, 0, 0)
    )
    return sine_metric, cosine_metric


def score_signature(datasets, candidate: Candidate | None):
    digest = hashlib.sha256()
    values = []
    cache = {}
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result = ((0, 0, 0), (0, 0, 0))
        for point in points:
            key = (point, candidate)
            metric = cache.get(key)
            if metric is None:
                metric = point_metric(point, candidate)
                cache[key] = metric
            digest.update(bytes((*metric[0], *metric[1])))
            result = h207.add_metric(result, metric)
        values.append(result)
    return values, digest.digest()


def gated_score(datasets, baselines, candidate: Candidate):
    digest = hashlib.sha256()
    values = []
    cache = {}
    for (name, points), baseline in zip(datasets, baselines):
        digest.update(name.encode("ascii"))
        result = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = cache.get(point)
            if metric is None:
                metric = point_metric(point, candidate)
                cache[point] = metric
            digest.update(bytes((*metric[0], *metric[1])))
            result = h207.add_metric(result, metric)
        if not h207.no_worse(result, baseline):
            return None
        values.append(result)
    return values, digest.digest()


def candidates():
    routes = tuple(
        h207.ProductRoute(linear, q_product, p_product)
        for linear in h207.PRODUCT_OUTPUTS
        for q_product in h207.PRODUCT_OUTPUTS
        for p_product in h207.PRODUCT_OUTPUTS
    )
    for products in routes:
        for tree in NEW_TREES:
            for mode in h207.MODES:
                for first in h207.ACTIONS:
                    for second in h207.ACTIONS:
                        for final_normalize in (False, True):
                            yield Candidate(
                                tree,
                                mode,
                                first,
                                second,
                                final_normalize,
                                products,
                            )


def main() -> None:
    assert_grammar()
    print("h211 complete four-term grammar:")
    for index, tree in enumerate(ALL_TREES, 1):
        old = next(
            (name for name, value in KNOWN_TREES.items() if value == tree),
            "new",
        )
        print(f"  {index:2d} {old:16s} {tree_key(tree)}")

    sweep = h207.joint_partitions("sweep")
    focused = h207.focused_datasets()
    selected = [*h207.sample(sweep), *focused]
    baselines, baseline_signature = score_signature(selected, None)
    complete_baselines = score_signature(sweep, None)[0]
    values_to_test = tuple(candidates())
    print(
        f"h211 missing-tree literal FADD: candidates={len(values_to_test)} "
        f"sample={sum(len(points) for _, points in selected)} "
        f"wide-sweep={sum(len(points) for _, points in sweep)}"
    )

    profiles = collections.defaultdict(list)
    for index, candidate in enumerate(values_to_test, 1):
        scored = gated_score(selected, baselines, candidate)
        if scored is not None:
            values, signature = scored
            if signature != baseline_signature and any(
                value != baseline
                for value, baseline in zip(values, baselines)
            ):
                profiles[signature].append(
                    (*h207.objective(values), candidate.short(), candidate)
                )
        if index % 2048 == 0:
            print(f"  progress {index}/{len(values_to_test)}", flush=True)

    representatives = sorted(min(items) for items in profiles.values())
    print(
        "h211 sample gate: "
        f"{sum(len(items) for items in profiles.values())} survivors "
        f"in {len(representatives)} profiles"
    )
    final = []
    for item in representatives:
        candidate = item[4]
        values, _ = score_signature(sweep, candidate)
        if all(
            h207.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            final.append((*h207.objective(values), candidate.short(), candidate))
    final.sort()
    print(f"h211 complete sweep: {len(final)} survivors")

    if final:
        validation = [*h207.joint_partitions("dense"), *focused]
        validation_baselines = score_signature(validation, None)[0]
        surviving = []
        for item in final:
            candidate = item[4]
            values, _ = score_signature(validation, candidate)
            if all(
                h207.no_worse(value, baseline)
                for value, baseline in zip(values, validation_baselines)
            ) and any(
                value != baseline
                for value, baseline in zip(values, validation_baselines)
            ):
                surviving.append(candidate)
        print(f"h211 dense/focused: {len(surviving)} survivors")
        for candidate in surviving:
            print(f"  {candidate.short()}")


if __name__ == "__main__":
    main()
