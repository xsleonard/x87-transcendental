#!/usr/bin/env python3
"""Default-off exact normalization candidate for unmasked true-denormal FSIN.

H1656's unknown endpoint observations are retrospective evidence for this
completion, not retroactively successful frozen predictions. No operand ledger
or input-error boundary is used. The all-encoding theorem is about scaling,
not proof that silicon chooses the scaled endpoint everywhere.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
import h1652_exception_transition as prior
from h1650_score_masked_state import digest
from h1640_remaining_scope_freshness import save

LOCKS = {
    'experiments/h1652_exception_transition.py': '67d212535064d10b2be5e1d872d6ae7bd55a2f7bfd911c03258ddd3ccf51b1a1',
    'transfer-tests/h1656/manifest.json': 'abcb6a74b0aed0c0d41468a183f078cb7258ae622f42603e97b1ca94578901b6',
    'transfer-tests/h1656/hardware-output/state-output.txt': '1074ffca4a37a5d217247603c3d8439ef2a19238c42612b011b0d30d0dd4d555',
    'tmp/ledger33/current/h1657_score_exception_state/report.json': '0cfd3b90654563a10e2edf35d0b13b58ba8c299761edadf55b7d8fffef4fcb6f',
    'tmp/ledger33/current/h1658_independent_exception_state/report.json': '57c3d5da389ccd8b2c9a5e762e13ef2437c6ecca18e2805b08e0a345e57cfe4d',
}


def scaled_denormal(se, sig):
    assert se in (0, 0x8000) and 0 < sig < 1 << 63
    shift = 64 - sig.bit_length()
    return f'{se | (24577-shift):04x}:{sig<<shift:016x}'


def complete_underflow(result, se, sig, *, before_status, enabled=False):
    if not enabled or result.output is not None:
        return result
    assert result.encoding_class == 'denormal' and result.delivery == 'at_next_wait'
    assert result.new_exception_flags == 0x32 and result.response == 'MF_AFTER'
    # Unknown output is produced by H1652 only for true-denormal FSIN with
    # DM masked, UM unmasked and no old pending fault. No instruction retry.
    return replace(result, output=scaled_denormal(se, sig), C1=0, C2=0,
                   status_bits=result.status_bits | (before_status & 0x4100),
                   status_known_mask=0xffff)


def scaling_certificate():
    regions = []
    for k in range(63):
        lo, hi = 1 << k, (1 << (k+1))-1
        shift, exponent = 63-k, 24514+k
        assert lo << shift == 1 << 63
        assert hi << shift < 1 << 64
        assert 0 < exponent < 0x7fff
        # Every significand in this interval uses the SAME shift and exponent.
        # Equality of the powers proves equality for the entire linear interval,
        # not just its endpoints: no significand bit is rounded or discarded.
        assert shift + exponent - 16383 - 63 == 1 - 16383 - 63 + 24576
        regions.append(dict(significand_min=str(lo), significand_max=str(hi),
                            shift=shift, exponent=exponent, significand_scale_power=shift))
    assert sum(int(r['significand_max'])-int(r['significand_min'])+1 for r in regions) == (1<<63)-1
    return dict(regions=regions, signed_raw_encodings=str(2*((1<<63)-1)),
                output_exponent_min=24514, output_exponent_max=24576,
                exact_exponent_increment=24576, rounding_or_discarded_bits=0,
                scope='All nonzero true-denormal raw encodings scale exactly by2^24576 under this formula. This is NOT an all-input silicon endpoint theorem.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); root, out = a.root.resolve(), a.output_dir.resolve()
    assert not out.exists()
    for name, sha in LOCKS.items():
        assert digest(root/name) == sha, name
    rows = json.loads((root/'transfer-tests/h1656/manifest.json').read_text())
    raw = (root/'transfer-tests/h1656/hardware-output/state-output.txt').read_text().splitlines()
    counts = Counter(); stages = Counter(); shifts = Counter(); examples = []
    invalid_c0 = set(); signals = defaultdict(Counter); profiles = Counter()
    for row, line in zip(rows, raw):
        fields = dict(token.lower().split('=') for token in line.split())
        assert fields['case'] == row['case_id'].lower()
        expected = prior.Transition(**row['expected'])
        site = int(fields['fault_at'])
        selected = 'a' if int(fields['a_valid']) else 'f'
        if expected.delivery == 'at_instruction':
            stage = 'pending_before_instruction'
        elif expected.delivery == 'none':
            stage = 'completed_without_fault'
        elif expected.new_exception_flags in (1, 2):
            stage = 'precomputation_invalid' if expected.new_exception_flags == 1 else 'precomputation_denormal'
        elif expected.output is None:
            stage = 'postcomputation_underflow'
        else:
            stage = 'postcomputation_precision'
        stages[stage] += 1
        signals[stage][int(fields['si_code'])] += 1
        if stage == 'precomputation_invalid':
            invalid_c0.add((row['before_SW'] >> 8) & 1)
        se, sig = (int(w,16) for w in row['operand'].split())
        disabled = complete_underflow(expected, se, sig, before_status=row['before_SW'])
        assert disabled == expected
        counts['disabled_completion_identity_checks'] += 1
        if expected.output is None:
            assert row['instruction'] == 'fsin' and site == 2 and int(fields['a_valid']) == 1
            result = complete_underflow(expected, se, sig, before_status=row['before_SW'], enabled=True)
            assert result.output == fields[selected+'_r0']
            assert result.status_bits == int(fields[selected+'_sw'],16)
            assert int(fields['a_sw'],16) == int(fields['f_sw'],16)
            shift = 64-sig.bit_length(); shifts[shift] += 1; profiles[row['profile']] += 1
            examples.append(dict(case_id=row['case_id'], operand=row['operand'], mode=row['mode'], pc=row['pc'],
                profile=row['profile'], shift=shift, output=result.output, SW=f'{result.status_bits:04x}'))
            counts['retrospective_underflow_output_full_SW_checks'] += 1
        elif stage == 'precomputation_denormal':
            # New physical bit observation, NOT a changed frozen prediction.
            full = expected.status_bits | (row['before_SW'] & 0x4100)
            assert full == int(fields[selected+'_sw'],16)
            counts['retrospective_pre_denormal_full_SW_checks'] += 1
    assert len(rows) == len(raw) == 36864 and counts['retrospective_underflow_output_full_SW_checks'] == 96
    assert invalid_c0 == {1}
    out.mkdir(parents=True); save(out/'underflow_observations.json', examples)
    report = dict(experiment='h1659_wrapped_underflow', status='PASS_RETROSPECTIVE_AND_EXACT_SCALING_ALGEBRA',
        counts=dict(counts), observed_stages=dict(stages), underflow_shift_counts=dict(shifts),
        underflow_profiles=dict(profiles), scaling_certificate=scaling_certificate(),
        invalid_early_C0=dict(initial_values=sorted(invalid_c0), survivors=['preserve','set'],
                              unresolved='Need fresh invalid/empty unmasked inputs with initialC0=0; pending faults do not execute the invalid operand and cannot fill this gap.'),
        observed_linux_si_codes={k:dict(v) for k,v in signals.items()},
        hardware_execution='none', private_ledger_access='none', production_or_paper_change='none',
        claim_boundary='96 formerly-null endpoints support exact input scaling, not retroactive frozen passes or universal silicon equality. Formula is default-off. Pre-invalid C0 remains ambiguous; whole scaling proof is conditional numerical algebra only.',
        sha256=dict(script=digest(Path(__file__)), evidence=LOCKS, observations=digest(out/'underflow_observations.json')))
    save(out/'report.json', report)
    print(json.dumps({k:report[k] for k in ('status','counts','observed_stages','underflow_shift_counts','invalid_early_C0')},sort_keys=True),flush=True)


if __name__ == '__main__':
    main()
