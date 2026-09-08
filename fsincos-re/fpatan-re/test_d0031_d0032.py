"""Independent local checks of coverage coordinates and exact preimages."""
from fractions import Fraction as Q
from math import isqrt
import random
import unittest

import d0031_internal_rounding_coverage as audit
from d0032_square_tie_preimages import construct, exact_raw
from prepare_d0033 import neighbor


class RoundingCoverageTests(unittest.TestCase):
    def test_external_neighbors_across_binades(self):
        self.assertEqual(neighbor(16383, 1 << 63, -1), (16382, (1 << 64) - 1))
        self.assertEqual(neighbor(16382, (1 << 64) - 1, 1), (16383, 1 << 63))
        self.assertEqual(neighbor(16383, 1 << 63, -2), (16382, (1 << 64) - 2))
        self.assertEqual(neighbor(16382, (1 << 64) - 1, 2), (16383, (1 << 63) + 1))

    def test_remainder_categories(self):
        for v, relation, parity in ((Q(8), 'exact', 0), (Q(33, 4), 'below', 0),
                                    (Q(17, 2), 'tie', 0), (Q(35, 4), 'above', 0),
                                    (Q(19, 2), 'tie', 1)):
            event = audit.event(v, 4)
            self.assertEqual((event['relation'], event['parity']), (relation, parity))
            self.assertEqual(audit.event(-v, 4), event)

    def test_exact_normalization(self):
        self.assertEqual(audit.normalized(audit.Raw80(0, 1 << 63)),
                         audit.normalized(audit.Raw80(1, 1 << 63)))
        for raw in (audit.Raw80(0, 1), audit.Raw80(0, 3),
                    audit.Raw80(0, (1 << 63) - 1), audit.Raw80(32766, (1 << 64) - 1)):
            e, m = audit.normalized(raw)
            self.assertEqual(m * audit.two(e - 16383 - 63), audit.SPEC['decode'](raw))

    def test_trace_matches_published_finite_graph(self):
        rng = random.Random('d0031-trace-crosscheck')
        pairs = []
        for _ in range(256):
            y = audit.Raw80(rng.randrange(16320, 16400), rng.getrandbits(63) | 1 << 63)
            x = audit.Raw80(rng.randrange(16375, 16400), rng.getrandbits(63) | 1 << 63)
            pairs.append((y, x))
        pairs.extend((audit.Raw80(0, v), audit.Raw80(1, (1 << 64) - 1))
                     for v in (1, 3, (1 << 63) - 1, 1 << 63))
        for y, x in pairs:
            for swapped in (False, True):
                yy, xx = (x, y) if swapped else (y, x)
                values = audit.angles(audit.reduction(audit.core_key(yy, xx)))
                for sy in (0, 32768):
                    for sx in (0, 32768):
                        signed_y = audit.Raw80(yy.se | sy, yy.sig)
                        signed_x = audit.Raw80(xx.se | sx, xx.sig)
                        which = 2 * int(audit.normalized(yy) > audit.normalized(xx)) + bool(sx)
                        expected = (-1 if sy else 1) * values[which]
                        self.assertEqual(expected, audit.SPEC['finite_angle'](signed_y, signed_x))

    def test_constructive_square_ties_all_cells(self):
        values = [(1 << 32) + 1, (1 << 32) + 12345, isqrt((1 << 65) - 1) | 1]
        values[-1] -= 2 * int(values[-1] ** 2 >= 1 << 65)
        for v in values:
            for cell in range(2, 33):
                for sign in (-1, 1):
                    made = construct(v, -8, cell, sign)
                    if cell == 32 and sign == 1:
                        self.assertIsNone(made)
                        continue
                    y, x, state, (a, b) = made
                    limit = ((1 << 64) - 1) // max(a, b)
                    limit -= int(not (limit & 1))
                    my, mx, variant, _ = construct(v, -8, cell, sign, limit)
                    self.assertEqual(state['z'], variant['z'])
                    self.assertEqual(audit.SPEC['decode'](my), limit * audit.SPEC['decode'](y))
                    self.assertEqual(audit.SPEC['decode'](mx), limit * audit.SPEC['decode'](x))
            for e in (-5, -6, -40):
                self.assertIsNotNone(construct(v, e))

    def test_exact_encoding_rejects_unrepresentable_integer(self):
        with self.assertRaises(AssertionError):
            exact_raw((1 << 64) + 1)


if __name__ == '__main__':
    unittest.main()
