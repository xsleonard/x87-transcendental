"""Local arithmetic/preimage crosschecks; no hardware execution."""
import random
import unittest
from model import F,cut,pow2
from d0010_causal_intervals import Interval
from d0011_terminal_preimage import Recipe,solve,tail,selftest,lattice
from d0011_rom_constraint_audit import inverse_rn_range
from d0011_verify_role_certificate import rounded


class ArithmeticTests(unittest.TestCase):
    def test_independent_rounder(self):
        rng=random.Random(0xd0011)
        for _ in range(512):
            v=F(rng.randrange(-2**80,2**80),rng.randrange(1,2**70))
            for w in (4,5,7,64,67,69):
                for mode in ('chop','rn'):
                    self.assertEqual(rounded(v,mode+str(w)),cut(v,mode+str(w)))

    def test_interval_helpers(self):
        selftest()
        for bits in (4,5,7):
            grid=sorted({F(n)*pow2(e-bits+1) for e in (-2,-1,0,1,2)
                         for n in range(2**(bits-1),2**bits)})
            for i in range(1,len(grid)-2):
                lo,hi=grid[i],grid[i+1];band=inverse_rn_range(lo,hi,bits)
                for v in (band.lo,band.hi,(band.lo+lo)/2,(lo+hi)/2,(hi+band.hi)/2):
                    self.assertEqual(band.contains(v),lo<=rounded(v,'rn'+str(bits))<=hi)

    def test_terminal_inverse_against_small_width_bruteforce(self):
        grid=sorted({F(n)*pow2(e-3) for e in range(-20,9) for n in range(8,16)})
        for order in ('square-h-z','z-h-square','square-z-h'):
            p=Recipe('small-proof',z_read='chop4',square='chop4',first_bits=4,last_bits=4,h_bits=4,order=order)
            for z in (F(5,16),F(7,16)):
                outputs={z-tail(z,h,p) for h in grid}
                for n in range(1,65):
                    angle=z-F(n,2**14);band=Interval(angle,angle,True,True)
                    self.assertEqual(solve(z,band,p)['feasible'],angle in outputs)


if __name__=='__main__':unittest.main()
