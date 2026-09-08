"""Exact index laws and V7/V6 dispatch equivalence away from midpoints."""
import random
import unittest
from d0023_index_hypotheses import HYPOTHESES, index
from graph_v6 import prevalue as v6
from graph_v7 import prevalue as v7
from model import F, pow2, value
from verify_d0017_d0020 import quantize


class IndexTests(unittest.TestCase):
    def test_nearest_lower_integer_identity(self):
        for n in range(1, 32):
            for delta in (F(-1, 1 << 70), F(0), F(1, 1 << 70)):
                ratio = F(2*n+1, 64) + delta
                shifted = ratio * 32 - F(1, 2)
                ceiling = -((-shifted.numerator) // shifted.denominator)
                self.assertEqual(index(ratio, F(1)), ceiling)
                self.assertEqual(index(ratio, F(1)), n + int(delta > 0))

    def test_parity_ties(self):
        for n in range(1, 32):
            ratio = F(2*n+1, 64)
            self.assertEqual(index(ratio, F(1), 'upper'), n + 1)
            self.assertEqual(index(ratio, F(1), 'even') % 2, 0)
            self.assertEqual(index(ratio, F(1), 'odd') % 2, 1)

    def test_reciprocal_rules_independent_rounding_and_scale(self):
        rng = random.Random('D0023 independent index audit')
        for n in range(1, 32):
            x = F((rng.getrandbits(63) | (1 << 63)) & ~63, 1 << 63)
            y = x * F(2*n+1, 64)
            for rule in HYPOTHESES:
                for e in (-15000, 15000):
                    self.assertEqual(index(y, x, rule), index(y*pow2(e), x*pow2(e), rule))
                if rule.startswith('reciprocal-'):
                    form = rule.split('-', 1)[1]
                    ratio = quantize(y * quantize(1 / x, form), 'chop67')
                    shifted = ratio * 32 + F(1, 2)
                    expected = shifted.numerator // shifted.denominator
                    self.assertEqual(index(y, x, rule), expected)

    def test_v6_v7_equivalence_off_exact_midpoints(self):
        rng = random.Random('D0023 unchanged off-midpoint arithmetic')
        for _ in range(512):
            ys, xs = 16383-rng.randrange(1, 60), 16383
            ym, xm = rng.getrandbits(63) | (1 << 63), rng.getrandbits(63) | (1 << 63)
            ratio = value(ys, ym) / value(xs, xm)
            self.assertNotEqual((ratio * 32).denominator, 2)
            if rng.getrandbits(1):
                ys, ym, xs, xm = xs, xm, ys, ym
            ys |= rng.getrandbits(1) << 15
            xs |= rng.getrandbits(1) << 15
            self.assertEqual(v6(ys, ym, xs, xm), v7(ys, ym, xs, xm))


if __name__ == '__main__':
    unittest.main()
