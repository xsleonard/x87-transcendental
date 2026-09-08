"""Ensure the hardware scorer rejects lost metadata, not only wrong values."""
import unittest
from replay import check_results


class ReplayContract(unittest.TestCase):
    def test_metadata_is_required(self):
        row=('fsin','rn',64,['0','0'],[],(0,0),None,0,0,None)
        fields='0 0 0 1 0000 0000000000000000 0000 0000000000000000 0000 0600 00 3f 1'.split()
        self.assertEqual(check_results([row],[' '.join(fields)])['C1'],1)
        for known in ('0000','0200','0400'):
            with self.subTest(known=known), self.assertRaises(AssertionError):
                changed=fields.copy();changed[9]=known
                check_results([row],[' '.join(changed)])


if __name__=='__main__':unittest.main()
