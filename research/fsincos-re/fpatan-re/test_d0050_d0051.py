"""Exact fixtures and enclosure checks for the analysis-only LIA graph."""
import sys
import unittest

sys.path.insert(0, '/private/tmp/fsincos-smt-deps')
import z3
import d0031_internal_rounding_coverage as audit
from d0050_affine_carry_constraints import AffineGraph, Interval, build, rounded_integer
from d0051_solver_crosscheck import parse_result


class AffineConstraintTests(unittest.TestCase):
    def test_signed_product_remainder_enclosure(self):
        for alo, ahi in ((-9, -2), (-3, 5), (2, 9)):
            for blo, bhi in ((-7, -1), (-4, 3), (1, 6)):
                for a in range(alo, ahi + 1):
                    for b in range(blo, bhi + 1):
                        linear = alo * b + blo * a - alo * blo
                        self.assertEqual(a * b - linear, (a - alo) * (b - blo))
                        self.assertLessEqual(linear, a * b)
                        self.assertLessEqual(a * b, linear + (ahi - alo) * (bhi - blo))

    def test_rounding_against_fraction(self):
        for magnitude in range(128, 512):
            for sign in (1, -1):
                n = sign * magnitude
                for bits in (3, 5, 7):
                    shift = magnitude.bit_length() - bits
                    value = n * audit.two(-12)
                    actual = rounded_integer(n, shift) * audit.two(-12 + shift)
                    self.assertEqual(actual, audit.T(value, bits))
                    whole, rem = divmod(magnitude, 1 << shift)
                    half = 1 << (shift - 1)
                    expected = sign * (whole + (rem > half or (rem == half and whole & 1)))
                    self.assertEqual(rounded_integer(n, shift, True), expected)

    def test_fixed_exact_carry_fixtures(self):
        fixtures = ((0, 0x8f2ede97b33447a7, z3.unsat),
                    (1, 0x8768acc7f2f6dc43, z3.sat))
        for node, um, expected in fixtures:
            solver, _, _ = build(z3, node, -9, um, um, 5000)
            self.assertEqual(solver.check(), expected)

    def test_positive_fixture_is_in_local_enclosure(self):
        # A changed-H fixture must remain feasible when its U box is widened.
        # This tests inclusion, not exclusion of any other U or exactness of SAT.
        um = 0x8768acc7f2f6dc43
        solver, variable, _ = build(z3, 1, -9, um - 1024, um + 1024, 5000)
        solver.add(variable == um)
        self.assertEqual(solver.check(), z3.sat)

    def test_solver_reply_parsing(self):
        self.assertEqual(parse_result(['unknown (TIMEOUT)']), ('unknown', 'TIMEOUT'))
        self.assertEqual(parse_result(['unknown']), ('unknown', None))
        self.assertEqual(parse_result(['sat\n']), ('sat', None))
        self.assertEqual(parse_result(['unsat']), ('unsat', None))
        with self.assertRaises(AssertionError):
            parse_result(['(error "bad input")'])
        with self.assertRaises(AssertionError):
            parse_result(['sat', 'unsat'])


if __name__ == '__main__':
    unittest.main()
