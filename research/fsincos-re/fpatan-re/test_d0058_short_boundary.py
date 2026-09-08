"""Independent forward checks of the short-odd necessary boundary filter."""
from fractions import Fraction as Q
import random
import unittest

import d0031_internal_rounding_coverage as audit
from d0049_algebraic_tie_preimages import domains, invert_target, graph, fraction
from d0058_short_odd_boundary import sqrt_bracket, parameters, block_enclosure, filtered_indices


class ShortBoundaryTests(unittest.TestCase):
    def test_square_root_brackets(self):
        rng = random.Random('d0058-independent-roots')
        for _ in range(500):
            value = Q(rng.randrange(1, 1 << 200), rng.randrange(1, 1 << 220))
            low, high = sqrt_bracket(value)
            self.assertLessEqual(low * low, value)
            self.assertLess(value, high * high)
            self.assertEqual(high - low, audit.two(-128))

    def test_full_blocks_and_product_enclosures(self):
        rng = random.Random('d0058-independent-complete-blocks')
        checked = changed = 0
        for exponent in (-13, -14):
            for domain in domains(2, exponent):
                params = parameters(domain, exponent)
                for width in (17, 512, 4096):
                    starts = (0, domain['count'] - width, rng.randrange(domain['count'] - width))
                    for start in starts:
                        envelope = block_enclosure(params, start, width)
                        selected = set(filtered_indices(params, start, width))
                        for index in range(start, start + width):
                            term = domain['first'] + index * domain['modulus']
                            offset = index - start
                            line = Q(envelope['intercept'] + offset * envelope['slope'], envelope['modulus'])
                            low = line - Q(envelope['lower'], envelope['modulus'])
                            high = line + Q(envelope['upper'], envelope['modulus'])
                            for word in invert_target(domain, term):
                                u = word * audit.two(exponent - 63)
                                target, h, _ = graph(2, (word, exponent - 63))
                                _, other, _ = graph(2, (word, exponent - 63), True)
                                target = fraction(target)
                                inner_unit = audit.two(audit.exponent(target) - 63)
                                whole = int(target / inner_unit)
                                products = [u * (whole + k) * inner_unit for k in (0, 1)]
                                for product in products:
                                    self.assertLessEqual(low, product / params['grid'])
                                    self.assertLessEqual(product / params['grid'], high)
                                if h != other:
                                    changed += 1
                                    self.assertIn(index, selected)
                                    # Directly test the independent grid lemma.
                                    a, b = [p / params['grid'] for p in products]
                                    self.assertLessEqual(-((-a.numerator) // a.denominator), b)
                                checked += 1
        self.assertGreater(checked, 1000)
        print('Complete forward products checked:', checked, 'H changes:', changed)


if __name__ == '__main__':
    unittest.main()
