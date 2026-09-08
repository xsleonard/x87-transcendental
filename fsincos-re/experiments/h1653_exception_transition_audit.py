#!/usr/bin/env python3
"""Retrospective masked checks and software exception-stage invariants only."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
import h1652_exception_transition as model
import h1650_score_masked_state as reader
from h1640_remaining_scope_freshness import save

LOCKS = {
    'experiments/h1645_masked_status_model.py': 'd00bbf0adf069be0e2553712c45df96eb1e457dfe74b8403e27b61f69eda0fc5',
    'transfer-tests/h1649/FREEZE.json': 'cd257a2353b8dd90a7ba06026ed715554454dbeac7462d42b46aa46f8383ec33',
    'transfer-tests/h1649/manifest.json': '00ba74c08d8f4154cfdc74e0fdd0bd876dca2b69282e6656c23d5a3f9b1c19ee',
    'transfer-tests/h1649/hardware-output/state-output.txt': '49ae75da9a8589672b5547fa82c795e10310f946199e1299317a7ab73fb89820',
    'tmp/ledger33/current/h1651_independent_masked_state/report.json': 'd042ca52458071f4b91291227cb8945b14df0254f6e2ba5726e9a53422ef8c9c',
}


def software():
    b = model.base.B63
    operands = [(0, 0), (0, 1), (0, b - 1), (0, b + 1), (1, b),
                (0x3ffc, b), (0x403e, b), (0x3fff, 1),
                (0x7fff, b), (0x7fff, b + 1), (0x7fff, b | (1 << 62))]
    count = Counter()
    for se, sig in operands:
        for sign in (0, 0x8000):
            for insn in ('fsin', 'fcos'):
                for masks in range(64):
                    for top in range(8):
                        for empty in (False, True):
                            initial = (top << 11) | 0x4700
                            tag = 0 if empty else 1 << top
                            # The numerical endpoint is a supplied token here;
                            # these checks establish control algebra, not numerics.
                            args = dict(before_status=initial, before_tag=tag,
                                        control_word=0x340 | masks,
                                        finite_output='3ffe:8000000000000000', finite_C1=1)
                            r = model.transition(se | sign, sig, insn, **args)
                            cls = model.base.classify(se, sig) if not empty else 'empty_stack'
                            invalid = cls in ('empty_stack', 'unsupported', 'infinity', 'signaling_nan')
                            denormal = cls in ('denormal', 'pseudo_denormal')
                            early = 1 if invalid and not masks & 1 else 2 if denormal and not masks & 2 else 0
                            assert r.top == top
                            if early:
                                assert r.output == f'{se | sign:04x}:{sig:016x}'
                                assert r.physical_abridged_tag == tag and r.new_exception_flags == early
                                assert r.response == 'MF_AFTER' and r.delivery == 'at_next_wait'
                                count['precomputation_priority_checks'] += 1
                            else:
                                assert r.response != 'MF_BEFORE'
                            assert bool(r.status_bits & 0x8080) == (r.response == 'MF_AFTER')
                            assert r.status_bits & 0x8080 in (0, 0x8080)
                            if r.output is None:
                                assert cls == 'denormal' and insn == 'fsin' and masks & 2 and not masks & 16
                                count['explicit_unknown_underflow_checks'] += 1
                            count['clean_initial_transition_checks'] += 1
                            unmasked = ~masks & 63
                            if unmasked:
                                pending = unmasked & -unmasked
                                before = initial | pending | 0x8080
                                # Pending delivery must not even request the
                                # numerical endpoint or manufacture empty ST0.
                                p = model.transition(se | sign, sig, insn,
                                    before_status=before, before_tag=tag, control_word=0x340 | masks)
                                assert p.response == 'MF_BEFORE' and p.delivery == 'at_instruction'
                                assert p.output == f'{se | sign:04x}:{sig:016x}'
                                assert p.status_bits == before and p.status_known_mask == 0xffff
                                assert p.physical_abridged_tag == tag and p.new_exception_flags == 0
                                count['pending_preempts_classification_checks'] += 1
    # All denormal normalization shifts are represented. This proves scaling
    # arithmetic of a candidate endpoint, not which endpoint silicon produces.
    for sig in (1 << bit for bit in range(63)):
        for sign in (0, 0x8000):
            for mode in ('rn', 'rd', 'ru', 'rz'):
                choices = model.wrapped_underflow_alternatives(sign, sig, 'fsin', mode)
                se2, sig2 = (int(w, 16) for w in choices['scale_input'].split(':'))
                exp = (se2 & 0x7fff) - 16383 - 63
                actual = Fraction(sig2) * (Fraction(2) ** exp)
                expected = Fraction(sig) * (Fraction(2) ** (-16382 - 63 + 24576))
                assert actual == expected and bool(se2 & 0x8000) == bool(sign)
                count['wrapped_scale_exact_fraction_checks'] += 1
    for cls, se, sig in (('zero', 0, 0), ('infinity', 0x7fff, b)):
        r = model.masked(se, sig, 'fsin', experimental_condition_mask=True)
        assert r.encoding_class == cls and r.status_known_mask != 0xffff
    for cw, sw in ((0x17f, 0x3800), (0x37f, 0xb880), (0x35f, 0x3820)):
        try:
            model.transition(1, b, 'fsin', control_word=cw, before_status=sw)
        except NotImplementedError:
            count['explicit_rejections'] += 1
        else:
            raise AssertionError('Unknown control/state accepted')
    return dict(count)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items():
        assert reader.digest(root / name) == sha, name
    rows = json.loads((root / 'transfer-tests/h1649/manifest.json').read_text())
    raw = (root / 'transfer-tests/h1649/hardware-output/state-output.txt').read_text().splitlines()
    assert len(rows) == len(raw) == 16128
    counts = Counter()
    for row, line in zip(rows, raw):
        fields = reader.parse(line)
        args = dict(finite_output=row['numerical']['numerical_output'],
                    finite_C1=row['numerical']['numerical_C1'], before_status=row['before_SW'],
                    before_tag=row['before_FTW'], control_word=row['before_CW'])
        se, sig = (int(w, 16) for w in row['operand'].split())
        original = model.base.masked(se, sig, row['instruction'], **args)
        disabled = model.masked(se, sig, row['instruction'], **args)
        assert disabled == original
        r = model.transition(se, sig, row['instruction'], **args, experimental_condition_mask=True)
        assert r.output == fields['A_R0'] and r.status_bits == int(fields['A_SW'], 16)
        assert r.status_known_mask == 0xffff and r.delivery == 'none'
        assert r.physical_abridged_tag == int(fields['A_FTW'], 16)
        counts['retrospective_full_SW_checks'] += 1
        counts['disabled_wrapper_identity_checks'] += 1
    sw = software()
    out.mkdir(parents=True)
    report = dict(experiment='h1653_exception_transition_audit', status='PASS_SOFTWARE_AND_RETROSPECTIVE',
        counts=dict(counts), software=sw, hardware_execution='none', private_ledger_access='none',
        production_or_paper_change='none',
        claim_boundary='H1652 optional condition mask is retrospective only. Exception staging is manual-derived software logic, not captured unmasked silicon behavior. Wrapped underflow endpoint stays unknown; incompatible ES/B/reserved PC reject.',
        sha256=dict(evidence=LOCKS, script=reader.digest(Path(__file__)),
                    model=reader.digest(root / 'experiments/h1652_exception_transition.py')))
    save(out / 'report.json', report)
    print(json.dumps(dict(status=report['status'], counts=dict(counts), software=sw), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
