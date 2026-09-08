"""Staged arithmetic, exact SMT encoding and frozen quotient-relation tests."""
import json
import unittest
import z3
from model import F,ROM,cut
from d0010_causal_intervals import BASE
from d0011_verify_role_certificate import matches,rounded
from d0012_staged_format_audit import direct
from d0012_aligned_add_audit import fixed
from d0012_coefficient_solve import Graph,rat
from verify_d0013_plan import quotient


class D0012Tests(unittest.TestCase):
    def test_staged_rounder_resolves_only_the_small_core(self):
        core=json.loads((BASE/'d0011-fixed-role-certificate.json').read_text())['two_point_final_role_obstruction']
        for point in core:
            v=direct(F(point['z']),'chop64','rn64','exact','chop67','chop67>rn64','chop67',2)
            rows=[r for g in point['rows'] for r in g['observations']]
            self.assertTrue(matches(v,rows))

    def test_alignment_modes(self):
        for sign in (-1,1):
            self.assertEqual(fixed(sign*F(9,8),F(1,4),'chop'),sign)
            self.assertEqual(fixed(sign*F(9,8),F(1,4),'rn'),sign)
            self.assertEqual(fixed(sign*F(11,8),F(1,4),'rn'),sign*F(3,2))
            self.assertEqual(fixed(sign*F(9,8),F(1,4),'away'),sign*F(5,4))
            self.assertEqual(fixed(sign*F(9,8),F(1,4),'odd'),sign*F(5,4))
            self.assertEqual(fixed(sign*F(11,8),F(1,4),'odd'),sign*F(5,4))

    def test_quantizer_constraints_with_independent_rounder(self):
        for sign in (-1,1):
            for mode in ('chop','rn'):
                g=Graph([],0,69);x=z3.Real('probe_x')
                bounds=(F(1),F(3,2)) if sign>0 else (-F(3,2),-F(1))
                out,_=g.quantize(x,bounds,4,mode,'probe_q')
                common=[(d,z3.IntVal(0)) for d in g.offsets.values()]
                constraints=z3.And(*g.solver.assertions())
                for i in range(33):
                    value=sign*(F(1)+F(i,64));want=rounded(value,mode+'4')
                    for q in range(6,15):
                        bindings=common+[(x,rat(value)),(z3.Int('probe_q'),z3.IntVal(q))]
                        valid=z3.is_true(z3.simplify(z3.substitute(constraints,*bindings)))
                        self.assertEqual(valid,want==sign*F(q,8))

    def test_frozen_quotient_relations_without_model_arithmetic(self):
        data=json.loads((BASE/'d0012-quotient-discriminators.json').read_text())
        count=0
        for g in data['groups']:
            old=tuple(int(x,16) for x in g['anchor_input'].split()[3:]);q,e,_=quotient(old)
            for p in g['pairs']:
                qq,ee,r=quotient(p['raw'])
                self.assertEqual((qq,ee),(q,e));self.assertEqual(r,F(p['discarded_fraction']));count+=1
        self.assertEqual(count,2192)


if __name__=='__main__':unittest.main()
