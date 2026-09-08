"""Certify why the first short-odd kernel-cut change is endpoint-masked.

This is a dyadic alignment argument for the saved witness, not an empirical
gate or a new rounding selector. The numerical algorithm remains unchanged.
"""
import json
from pathlib import Path

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored
from d0045_tie_observability import replay_z
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def main():
    output = BASE / 'd0054-cut-grid-proof.json'
    assert not output.exists()
    directory = BASE / 'd0049-node2-expanded'
    report = json.loads((directory / 'REPORT.json').read_text())
    assert digest(directory / 'targets.tsv') == report['target_sha256']
    assert report['counts']['pre_anchor_cut_changed'] == 1
    barriers = BASE / 'd0052-expanded-masking.json'
    barrier = json.loads(barriers.read_text())
    for path, sha in barrier['artifact_sha256'].items():
        assert digest(Path(path)) == sha
    z, value, other, parity = replay_z(2, int('72303091d4576d17f', 16), -73)
    unit = audit.two(-73)
    first, second = audit.T(value, 67), audit.T(other, 67)
    k, l = first / unit, second / unit
    assert k.denominator == l.denominator == 1
    k, l = int(k), int(l)
    assert (l - k, k % 4, l % 4) == (1, 2, 3)
    cells = []
    for sign in (1, -1):
        for cell in range(2, 33):
            c = audit.Q(cell, 32)
            ratio = (c + sign * z) / (1 - c * sign * z)
            if not audit.Q(3, 64) < ratio <= 1:
                continue
            q = 32 * ratio - audit.Q(1, 2)
            if -((-q.numerator) // q.denominator) != cell:
                continue
            anchor = audit.ROM[124 + cell]
            anchor_units = anchor / unit
            assert anchor_units.denominator == 1 and int(anchor_units) % 4 == 0
            a, b = anchor + sign * first, anchor + sign * second
            assert 0 < min(a, b) and audit.exponent(a) == audit.exponent(b)
            cut_units = audit.two(audit.exponent(a) - 66) / unit
            final_half_units = audit.two(audit.exponent(a) - 64) / unit
            assert cut_units.denominator == final_half_units.denominator == 1
            assert int(cut_units) % 4 == int(final_half_units) % 4 == 0
            # The interval has residues 2..3 (positive residual) or 1..2
            # (negative residual), so it contains no multiple of four.
            lo, hi = sorted((int(a / unit), int(b / unit)))
            assert lo // 4 == hi // 4 and lo % 4 != 0 and hi % 4 != 0
            assert audit.T(a, 67) == audit.T(b, 67)
            baseline = restored(dict(path='table', cell=cell), sign * value)
            altered = restored(dict(path='table', cell=cell), sign * other)
            # The three pi restorations consume the identical 67-bit cut.
            assert baseline[1:] == altered[1:]
            # Direct t has no intervening 67-bit cut, but its RN64 half and
            # directed-rounding boundaries are all multiples of four too.
            assert audit.endpoint_vector(baseline) == audit.endpoint_vector(altered)
            cells.append(dict(sign=sign, cell=cell, kernel_cut_units=int(cut_units),
                              final_half_units=int(final_half_units), endpoint_difference=False))
    assert len(cells) == report['counts']['cell_proposals'] == 19
    previous = BASE / 'd0048-d0053-verification.json'
    assert json.loads(previous.read_text())['status'] == 'PASS_SEARCH_AND_LOCAL_BOX_AUDIT'
    save(output, dict(status='PASS_EXACT_CUT_GRID_MASKING_PROOF', node='table:odd_sum',
        square_sig='cbbbd15084120294', square_exponent=-13,
        z_sig='72303091d4576d17f', z_step=-73, retained_parity=parity,
        baseline_cut_sig=f'{k:x}', alternate_cut_sig=f'{l:x}',
        common_unit='2^-73', low_residue_transition=[2, 3], cells=cells,
        proof='Every admissible anchor is a multiple of four common units. The changed interval crosses no multiple of four. All subsequent 67-bit cut and RN64 half/integer boundaries are multiples of four or a coarser grid; the pi restorations consume an unchanged cut.',
        report_sha256=digest(directory / 'REPORT.json'), target_sha256=report['target_sha256'],
        propagation_audit_sha256=digest(barriers), previous_verification_sha256=digest(previous),
        source_sha256={name: digest(HERE / name) for name in
            ('d0054_cut_grid_proof.py', 'd0045_tie_observability.py', 'd0037_polynomial_node_census.py',
             'd0031_internal_rounding_coverage.py', 'fpatan_candidate.c', 'PSEUDOCODE.md')},
        hardware_executed=False, numerical_model_changed=False, goal_complete=False,
        limits='Proof of masking for this saved cut transition and all its admissible cells. Not a global masking proof, not evidence for an internal tie rule, and not an external preimage claim.'))
    print('PASS_EXACT_CUT_GRID_MASKING_PROOF: 19 cell/sign cases; no new tie rule identified.', flush=True)


if __name__ == '__main__':
    main()
