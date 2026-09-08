"""Closed-form divided-difference representation of the seven-input wall.

For seven distinct square values u_i, weights 1/prod_{j!=i}(u_i-u_j)
annihilate every polynomial of degree at most five. The independently
verified hardware/error intervals force that weighted sum away from zero.
This is a structural impossibility certificate for the specified graph and
error envelope, not a numerical FPATAN solution or operand selector.
"""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
from prepare import save

BASE = Path(__file__).resolve().parents[1] / 'tmp/fpatan-re'


def main():
    path = BASE / 'd0014-continuous-b60-certificate.json'
    verification = BASE / 'd0014-independent-b60-certificate.json'
    certificate = json.loads(path.read_text())
    checked = json.loads(verification.read_text())
    assert checked['status'] == 'INDEPENDENT_SOLVER_FREE_CERTIFICATE_PASS'
    assert checked['certificate_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    rows = certificate['certificate']['inequalities']
    assert len(rows) == 7 and all(r['kind'] == 'observation' for r in rows)
    points = sorted((r['point'] for r in rows), key=lambda p: F(p['u']))
    x = [F(p['u']) for p in points]
    assert len(set(x)) == 7
    weights = []
    for i in range(7):
        product = F(1)
        for j in range(7):
            if i != j:
                product *= x[i] - x[j]
        weights.append(1 / product)
    scale = sum(abs(w) for w in weights)
    weights = [w / scale for w in weights]
    moments = [sum(w * u ** k for w, u in zip(weights, x)) for k in range(6)]
    assert moments == [0] * 6
    low = sum(w * F(p['polynomial_lo'] if w > 0 else p['polynomial_hi']) for w, p in zip(weights, points))
    high = sum(w * F(p['polynomial_hi'] if w > 0 else p['polynomial_lo']) for w, p in zip(weights, points))
    assert low > 0 or high < 0
    gap = min(abs(low), abs(high))
    report = dict(status='EXACT_DEGREE_FIVE_INTERPOLATION_OBSTRUCTION',
                  certificate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  verification_sha256=hashlib.sha256(verification.read_bytes()).hexdigest(),
                  formula='w_i = 1 / product_{j!=i}(u_i-u_j), normalized by sum(abs(w_i))',
                  points=[dict(input=p['input'], u=p['u'], polynomial_lo=p['polynomial_lo'],
                               polynomial_hi=p['polynomial_hi'], weight=str(w)) for p, w in zip(points, weights)],
                  moments_degree_zero_through_five=[str(v) for v in moments],
                  normalized_weighted_interval=dict(lo=str(low), hi=str(high)),
                  separation_from_zero=str(gap), separation_in_h118_ULPs=str(gap * (1 << 65)),
                  coefficient_bound_in_69bit_grid_ULPs=1 << 60,
                  limits='Coefficient bounds are used to justify rounding-error envelopes; the interpolation identity itself is coefficient-independent.',
                  hardware_executed=False, numerical_model_promoted=False)
    save(BASE / 'd0014-interpolation-certificate.json', report)
    print('PASS seven-point degree-five obstruction;',
          'normalized separation', float(gap * (1 << 65)), 'h118 ULPs', flush=True)


if __name__ == '__main__':
    main()
