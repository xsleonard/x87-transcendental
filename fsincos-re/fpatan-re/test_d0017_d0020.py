"""Tests for the new state/factor representations and certified diagnostics."""
import itertools
import json
import unittest
from fractions import Fraction as F
from d0010_causal_intervals import BASE, Interval
from d0017_residual_state_audit import selftest as residual_identity
from d0019_certified_atan_diagnostic import atan_bounds, relation, rounded_observation
from d0020_factored_lead_audit import kernel as factored_kernel
from model import ROM, cut
from verify_d0017_d0020 import quantize, kernel as independent_kernel


class RepresentationTests(unittest.TestCase):
    def test_independent_signed_rounder(self):
        for sign, n, bits, mode in itertools.product((-1, 1), range(250, 521), (3, 4, 7),
                                                    ('rn', 'chop', 'away', 'rd', 'ru')):
            v = sign * F(n, 256)
            self.assertEqual(quantize(v, mode + str(bits)), cut(v, mode + str(bits)))

    def test_complete_residual_identity(self):
        residual_identity()
        for z, order in itertools.product((F(1, 73), F(17, 512)), range(3)):
            recipe = dict(square_format='rn64', residual_format='exact', square_residual=True,
                          product_residual=True, add_residual=True, first_residual=True,
                          last_residual=True, zread='chop64', read_residual=True,
                          tail_order=order, merge='exact')
            expected = z + sum(ROM[k] * z ** (2 * (k - 118) + 3) for k in range(118, 124))
            self.assertEqual(independent_kernel(z, 'residual', recipe), expected)

    def test_factored_identity(self):
        for z in (F(1, 73), F(3, 128), F(17, 512)):
            expected = z + sum(ROM[k] * z ** (2 * (k - 118) + 3) for k in range(118, 124))
            self.assertEqual(factored_kernel(z, *(['exact'] * 7)), expected)

    def test_taylor_bounds_nesting_and_reduction_identity(self):
        for z in (F(0), F(1, 4096), F(3, 128), F(3, 64)):
            lo, hi = atan_bounds(z)
            tight_lo, tight_hi = atan_bounds(z, 40)
            self.assertLessEqual(lo, tight_lo)
            self.assertLessEqual(tight_hi, hi)
            # atan(a)+atan(b)=atan(z), for a=z/2 and b=(z-a)/(1+z*a).
            a = z / 2
            b = (z - a) / (1 + z * a)
            al, ah = atan_bounds(a, 40)
            bl, bh = atan_bounds(b, 40)
            self.assertLessEqual(lo, al + bl)
            self.assertLessEqual(ah + bh, hi)

    def test_interval_and_rounding_uncertainty_preserved(self):
        self.assertEqual(relation((F(1), F(1)), Interval(F(1), F(2), False, False)), 'DISJOINT')
        self.assertEqual(relation((F(1), F(2)), Interval(F(1), F(2), True, True)), 'CONTAINED')
        self.assertEqual(relation((F(1), F(2)), Interval(F(1), F(2), False, False)), 'UNKNOWN')
        self.assertIsNone(rounded_observation((F(1), F(2)), False, 'rn'))
        self.assertIsNone(rounded_observation((F(1) - F(1, 1 << 66), F(1)), False, 'rn'))

    def test_diagnostic_scores_recomputed(self):
        report = json.loads((BASE / 'd0019-certified-atan-diagnostic.json').read_text())
        self.assertEqual(report['groups'], len(report['results']))
        for name, expected in report['counts'].items():
            outputs = c1 = union = certified = 0
            for point in report['results']:
                variant = point['variants'][name]
                bounds = tuple(F(v) for v in variant['bounds'])
                for row in variant['observations']:
                    tokens = row['input'].split()
                    got = rounded_observation(bounds, bool(int(tokens[3], 16) & 32768), tokens[1])
                    self.assertEqual(got, row['predicted'])
                    self.assertIsNotNone(got)
                    outputs += got[:2] != row['observed'][:2]
                    c1 += got[2] != row['observed'][2]
                    union += got != row['observed']
                    certified += 1
            self.assertEqual((outputs, c1, union, certified),
                             tuple(expected[k] for k in ('output_misses', 'C1_misses', 'union_misses', 'certified_rows')))


if __name__ == '__main__':
    unittest.main()
