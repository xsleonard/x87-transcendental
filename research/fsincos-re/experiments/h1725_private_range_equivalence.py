#!/usr/bin/env python3
"""Local aggregate-only equivalence audit of the decimal range-check edit.

No private names, values, hashes or membership lists are serialized. This
compares the previous and corrected parser on the actual supplemental files
before accepting any selected input for hardware.
"""
from pathlib import Path
import types
import h1725_select_full as current
from h1725_full_campaign import BASE,save,suite

path=Path(current.__file__);source=path.read_text()
new="""if e and len(e[1].lstrip('+-0'))>len(str(len(mantissa)+5001)):
                    # Even every mantissa character cannot offset such an
                    # exponent into raw80 range, including decimal zero padding."""
old="""if e and (len(e[1].lstrip('+-0'))>6 or abs(int(e[1]))>200000):
                    # Even all digits in this bounded local file cannot offset
                    # such an exponent into the finite raw80 range.
                    if len(digits)>100000:raise RuntimeError('Private decimal range unresolved')"""
assert source.count(new)==1
prior=types.ModuleType('h1725_previous_range_check');prior.__file__=str(path)
exec(compile(source.replace(new,old),str(path),'exec'),prior.__dict__)
before,counts_before=prior.private_signatures()
after,counts_after=current.private_signatures()
assert before==after
save(BASE/'PRIVATE_RANGE_EQUIVALENCE.json',dict(status='PASS',signature_sets_equal=True,
    current_parser_sha256=suite.digest(path),private_names_contents_hashes_memberships_published=False,
    hardware_execution='none',scope='Old and corrected range predicates produce identical exclusion sets on the actual local supplemental bytes.'))
print('PASS: private exclusion sets unchanged by the decimal range correction; no private details published.')
