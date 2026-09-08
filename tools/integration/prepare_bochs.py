"""Apply the narrow x87trans adapter to the pinned, disposable Bochs checkout.

No download, guest execution, upstream submission or deletion is performed.
The caller builds Bochs with x87trans's include and link paths afterward.
"""
import argparse
from pathlib import Path
import subprocess

PIN='c4b78268fe79e03cbc04c512d2b47e40e03cdfb9'
ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout',type=Path)
    args=parser.parse_args()
    checkout=args.checkout.resolve()
    assert subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()==PIN
    cpu=checkout/'bochs/cpu/cpu.h'
    trans=checkout/'bochs/cpu/fpu/fpu_trans.cc'
    header=cpu.read_text();source=trans.read_text()
    assert 'FPU_x87trans' not in header+source, 'adapter is already present'
    declaration='  BX_SMF void F2XM1(bxInstruction_c *) BX_CPP_AttrRegparmN(1);'
    assert declaration in header
    header=header.replace(declaration,'  BX_SMF bool FPU_x87trans(bxInstruction_c *, unsigned);\n'+declaration)
    for index,op in enumerate(('FSIN','FCOS','FSINCOS','FPTAN','F2XM1','FPATAN','FYL2X','FYL2XP1')):
        start=source.index('BX_CPU_C::'+op+'(')
        at=source.index('  softfloat_status_t status =',start)
        assert at < source.index('\n}\n',start)
        source=source[:at]+f'  if (FPU_x87trans(i, {index})) {{\n    BX_NEXT_INSTR(i);\n  }}\n\n'+source[at:]
    anchor='extern softfloat_status_t i387cw_to_softfloat_status_word(Bit16u control_word);'
    assert anchor in source
    source=source.replace(anchor,anchor+'\n\n#include "x87trans.inc"')
    # All original code and its comments remain available for outside-scope
    # fallback. Mutate only after validating every insertion point.
    cpu.write_text(header);trans.write_text(source)
    (trans.parent/'x87trans.inc').write_bytes((ROOT/'integrations/bochs/x87trans.inc').read_bytes())
    print('Applied x87trans adapter to Bochs',PIN)


if __name__=='__main__':main()
