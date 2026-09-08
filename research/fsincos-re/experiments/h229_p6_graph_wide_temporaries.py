#!/usr/bin/env python3
"""Search 64..72-bit temporaries on the fixed FSINCOS model graph.

Earlier 64..72-bit grids evaluated algebraically equivalent Tang trees.
h226 is the first pass over the table-reconstruction graph, but it only tried
exact, 64-bit, and a few 67-bit representatives.  Wider temporary formats
remain plausible.  This pass keeps h226's best state and constant operand
choices fixed, then searches every 64..72-bit RN/chop/away/odd writeback for
the two table products and their FSUB correction.

The search is a small coordinate beam around the h226 survivor.  Candidates
still must be componentwise non-regressing on every complete old partition;
aggregate improvement alone is not sufficient for promotion.
"""

from __future__ import annotations

import dataclasses

import h110_fsin_standalone as h110
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226


def actions(include_exact: bool = True) -> tuple[str, ...]:
    values = [
        f"{mode}{bits}"
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    ]
    return tuple((["exact"] if include_exact else []) + values)


ACTIONS = actions()


@dataclasses.dataclass(frozen=True)
class Candidate:
    q_product: str = "chop67"
    p_product: str = "exact"
    correction: str = "rn67"

    def short(self) -> str:
        return (
            f"q-product={self.q_product} "
            f"p-product={self.p_product} correction={self.correction}"
        )


CURRENT = Candidate()
FIELDS = tuple((field, ACTIONS) for field in (
    "q_product", "p_product", "correction"
))


def quantize(value, action: str):
    if action == "exact":
        return value
    for mode in ("chop", "away", "odd", "rn"):
        if action.startswith(mode):
            return h110.quantize(
                value, h110.Quant(int(action[len(mode):]), mode)
            )
    raise ValueError(action)


def as_h226(candidate: Candidate) -> h226.Candidate:
    return h226.Candidate(
        sine_state="exact",
        cosine_state="exact",
        lead_constant="rn64",
        cross_constant="exact",
        q_product=candidate.q_product,
        p_product=candidate.p_product,
        correction=candidate.correction,
    )


# h226's quantizer owns the model graph.  Extend only its materialization
# vocabulary; no arithmetic behavior is replaced.
h226.QUANTS.update({
    action: (
        None
        if action == "exact"
        else next(
            h110.Quant(int(action[len(mode):]), mode)
            for mode in ("chop", "away", "odd", "rn")
            if action.startswith(mode)
        )
    )
    for action in ACTIONS
})


def score(datasets, candidate: Candidate | None):
    return h226.score(
        datasets, None if candidate is None else as_h226(candidate)
    )


def expand(beam):
    result = set(beam)
    for candidate in beam:
        for field, field_actions in FIELDS:
            for action in field_actions:
                result.add(dataclasses.replace(
                    candidate, **{field: action}
                ))
    return result


def search(selected, baselines, width: int = 12, rounds: int = 3):
    beam = [CURRENT]
    ranked_by_candidate = {}
    for round_index in range(1, rounds + 1):
        tested = 0
        for candidate in expand(beam):
            if candidate in ranked_by_candidate:
                continue
            values = score(selected, candidate)
            ranked_by_candidate[candidate] = (
                h226.regressions(values, baselines),
                h226.objective(values),
                candidate.short(),
                candidate,
                values,
            )
            tested += 1
        ranked = sorted(ranked_by_candidate.values())
        beam = [item[3] for item in ranked[:width]]
        print(
            f"round {round_index}: new={tested} "
            f"seen={len(ranked_by_candidate)} best={ranked[0][0:3]}",
            flush=True,
        )
    return beam


def main() -> None:
    complete = h218.datasets()
    selected = [
        h226.sample_dataset(name, points, controls=48)
        for name, points in complete
    ]
    baselines = score(selected, None)
    print(
        f"h229 P6 wide temporaries: selected="
        f"{sum(len(points) for _, points in selected)} "
        f"complete={sum(len(points) for _, points in complete)}"
    )
    seed = score(selected, CURRENT)
    print(
        f"  Round36={h226.objective(baselines)} "
        f"seed={h226.objective(seed)} "
        f"regressions={h226.regressions(seed, baselines)}"
    )
    beam = search(selected, baselines)
    complete_baselines = score(complete, None)
    finalists = []
    for candidate in beam:
        selected_values = score(selected, candidate)
        if not h226.no_worse(selected_values, baselines):
            continue
        complete_values = score(complete, candidate)
        if h226.no_worse(complete_values, complete_baselines):
            finalists.append((
                h226.objective(complete_values),
                candidate.short(),
                complete_values,
            ))
    finalists.sort()
    print(f"h229 complete survivors={len(finalists)}")
    for item in finalists[:20]:
        print(f"  {item[0]} {item[1]}")


if __name__ == "__main__":
    main()
