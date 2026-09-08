"""D0059 regression: enclose truncated products, including equality cases."""
from fractions import Fraction as Q
import random
import unittest

import d0031_internal_rounding_coverage as audit
from d0049_algebraic_tie_preimages import domains, invert_target, graph, fraction
import d0058_short_odd_boundary as previous
from d0059_short_odd_boundary import parameters, block_enclosure, filtered_indices


class CorrectedShortBoundaryTests(unittest.TestCase):
    def test_frozen_false_negative_regression(self):
        word, exponent = int('fb05b105f1817315', 16), -13
        target, h, _ = graph(2, (word, exponent - 63))
        _, alternate, _ = graph(2, (word, exponent - 63), True)
        self.assertNotEqual(h, alternate)
        recovered = False
        for domain in domains(2, exponent):
            term = (fraction(target) - audit.ROM[115]) / audit.two(domain['unit'])
            index, remainder = divmod(int(term) - domain['first'], domain['modulus'])
            if remainder or not 0 <= index < domain['count'] or word not in invert_target(domain, int(term)):
                continue
            start = index // 128 * 128
            self.assertNotIn(index, previous.filtered_indices(previous.parameters(domain, exponent), start, 128))
            self.assertIn(index, filtered_indices(parameters(domain, exponent), start, 128))
            recovered = True
        self.assertTrue(recovered)

    def test_full_blocks_and_truncated_product_enclosures(self):
        rng = random.Random('d0059-independent-complete-blocks')
        checked = changed = 0
        for exponent in (-13, -14):
            for domain in domains(2, exponent):
                params = parameters(domain, exponent)
                for width in (17, 512, 4096):
                    starts = [0, domain['count'] - width]
                    starts.extend(rng.randrange(domain['count'] - width) for _ in range(8))
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
                                products = [audit.T(u * (whole + k) * inner_unit, 67) for k in (0, 1)]
                                for product in products:
                                    self.assertLessEqual(low, product / params['grid'])
                                    self.assertLessEqual(product / params['grid'], high)
                                if h != other:
                                    changed += 1
                                    self.assertIn(index, selected)
                                    a, b = [p / params['grid'] for p in products]
                                    self.assertLessEqual(-((-a.numerator) // a.denominator), b)
                                checked += 1
        self.assertGreater(checked, 5000)
        print('Complete forward truncated products checked:', checked, 'H changes:', changed)


if __name__ == '__main__':
    unittest.main()
