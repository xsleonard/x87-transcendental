"""Format/lattice checks for the model-independent mathematical generator."""
from fractions import Fraction
import unittest

import d0065_independent_inputs as independent


class LatticeTests(unittest.TestCase):
    def test_neighbors_cross_normal_and_subnormal_boundaries(self):
        top = independent.INTEGER_BIT
        for a, b in (((0, top - 1), (1, top)),
                     ((1, 2 * top - 1), (2, top)),
                     ((16382, 2 * top - 1), (16383, top))):
            self.assertEqual(independent.neighbor(a, 1), b)
            self.assertEqual(independent.neighbor(b, -1), a)
            midpoint = (independent.decode(a) + independent.decode(b)) / 2
            self.assertEqual(independent.floor_raw(midpoint), a)
            self.assertEqual(independent.floor_raw(independent.decode(b)), b)

    def test_floor_around_every_test_exponent(self):
        for field in (0, 1, 2, 8191, 16382, 16383, 32766):
            for fraction in (1, 127, (1 << 62) - 1):
                sig = fraction if field == 0 else (1 << 63) | fraction
                raw = field, sig
                following = independent.neighbor(raw, 1)
                a, b = independent.decode(raw), independent.decode(following)
                for weight in (Fraction(0), Fraction(1, 17), Fraction(16, 17)):
                    self.assertEqual(independent.floor_raw(a + weight * (b - a)), raw)

    def test_exact_scaling_never_silently_truncates(self):
        pair = 1, (1 << 63) + 1, 16383, 1 << 63
        self.assertIsNone(independent.exact_scale(pair, -1))
        scaled = independent.exact_scale(pair, 1)
        self.assertEqual(independent.decode(scaled[:2]), 2 * independent.decode(pair[:2]))

    def test_orbits_and_target_bounds(self):
        self.assertEqual(len(set(independent.orbits((16383, 1 << 63, 16384, 1 << 63)))), 8)
        rows = independent.targets()
        self.assertEqual(len(rows), 138)
        for row in rows:
            angle = int(row['numerator'], 16) * independent.two(row['step'])
            self.assertTrue(0 < angle < 1)


if __name__ == '__main__':
    unittest.main()
