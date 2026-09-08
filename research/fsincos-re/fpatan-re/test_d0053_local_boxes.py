"""Compare complete local inverses with forward enumeration, including edges."""
import unittest

import d0031_internal_rounding_coverage as audit
from d0049_algebraic_tie_preimages import graph, fraction, invert_target
from d0053_exact_local_tie_boxes import local_domains


class ExactLocalBoxTests(unittest.TestCase):
    def check_box(self, node, exponent, low, high):
        inverse = set()
        for domain in local_domains(node, exponent, low, high):
            for index in range(domain['count']):
                term = domain['first'] + index * domain['modulus']
                inverse.update(invert_target(domain, term))
        forward = set()
        for um in range(low, high + 1):
            target, _, _ = graph(node, (um, exponent - 63))
            if audit.event(fraction(target), 64)['relation'] == 'tie':
                forward.add(um)
        self.assertEqual(inverse, forward)
        return inverse

    def test_known_targets_and_inclusive_endpoints(self):
        for node, exponent, center in ((0, -9, 0x8f2ede97b33447a7),
                                       (1, -9, 0x8768acc7f2f6dc43),
                                       (2, -13, 0xf2377fb01308f4eb)):
            self.assertIn(center, self.check_box(node, exponent, center - 8192, center + 8192))
            self.assertEqual(self.check_box(node, exponent, center, center), {center})
            self.check_box(node, exponent, center - 4096, center - 1)
            self.check_box(node, exponent, center + 1, center + 4096)

    def test_square_binade_split(self):
        # U near sqrt(2)*2^63 makes T67(U^2) cross its normalization binade.
        from math import isqrt
        center = isqrt(1 << 127)
        self.check_box(2, -13, center - 4096, center + 4096)


if __name__ == '__main__':
    unittest.main()
