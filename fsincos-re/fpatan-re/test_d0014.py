"""Independent arithmetic checks for the centered and relaxed encodings."""
import json
import random
import unittest
import z3
from d0010_causal_intervals import BASE
from d0011_verify_role_certificate import rounded
from d0014_integer_coefficient_solve import Graph, Linear, concrete, data_points
from d0014_coefficient_relaxation import constraints, wide_envelope
from model import F, ROM


class D0014Tests(unittest.TestCase):
    def test_centered_quantizer_both_signs_and_ties(self):
        for sign in (-1, 1):
            for mode in ('rn', 'chop'):
                graph = Graph([], 0)
                graph.variable('probe_x', -16, 16)
                expr = Linear(sign * F(5, 4), {'probe_x': sign * F(1, 64)})
                graph.quantize(expr, 4, mode, 'probe_q')
                node = graph.nodes[-1]
                common = [(z3.Int(f'delta_{k}'), z3.IntVal(0)) for k in range(118, 124)]
                clauses = z3.And(*graph.solver.assertions())
                for i in range(-16, 17):
                    want = rounded(sign * (F(5, 4) + F(i, 64)), mode + '4')
                    expected = (want - node['base']) / (node['sign'] * node['step'])
                    self.assertEqual(expected.denominator, 1)
                    for q in range(int(expected) - 1, int(expected) + 2):
                        bindings = common + [(z3.Int('probe_x'), z3.IntVal(i)), (z3.Int('probe_q'), z3.IntVal(q))]
                        valid = z3.is_true(z3.simplify(z3.substitute(clauses, *bindings)))
                        self.assertEqual(valid, q == expected)

    def test_centered_graph_complete_independent_assignments(self):
        graph = Graph(data_points(), 28)
        rng = random.Random('D0014 centered arithmetic calibration')
        for _ in range(8):
            offsets = {k: rng.randrange(-graph.bound, graph.bound + 1) for k in range(118, 124)}
            graph.check_assignment(offsets)

    def test_wide_error_envelope_contains_concrete_rounding_error(self):
        graph = wide_envelope(data_points(), 60)
        _, _, evidence = constraints(graph)
        rng = random.Random('D0014 independent rounding envelopes')
        offsets = [{k: sign * graph.bound for k in range(118, 124)} for sign in (-1, 1)]
        offsets += [{k: rng.randrange(-graph.bound, graph.bound + 1) for k in range(118, 124)} for _ in range(8)]
        for offset in offsets:
            coefficients = {k: ROM[k] + offset[k] * graph.units[k] for k in range(118, 124)}
            for (_, t, _), point in zip(graph.data, evidence):
                _, trace = concrete(t['z'], coefficients)
                polynomial = sum(F(weight) * coefficients[int(k)] for k, weight in point['unrounded_polynomial_weights'].items())
                error = trace['h118'] - polynomial
                self.assertLessEqual(F(point['accumulated_error_lo']), error)
                self.assertLessEqual(error, F(point['accumulated_error_hi']))

    def test_stored_rational_certificate_and_weight_mutation(self):
        report = json.loads((BASE / 'd0014-continuous-b28-certificate.json').read_text())
        rows = report['certificate']['inequalities']
        weights = [F(row['weight']) for row in rows]

        def valid(values):
            return (all(w >= 0 for w in values) and
                    all(sum(w * r['coefficients'][k] for w, r in zip(values, rows)) == 0 for k in range(6)) and
                    sum(w * r['bound'] for w, r in zip(values, rows)) < 0)

        self.assertTrue(valid(weights))
        changed = list(weights)
        changed[0] += 1
        self.assertFalse(valid(changed))


if __name__ == '__main__':
    unittest.main()
