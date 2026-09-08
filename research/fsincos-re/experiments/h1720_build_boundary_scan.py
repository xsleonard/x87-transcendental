#!/usr/bin/env python3
"""Instrument a copy of the frozen policy-2 implementation, software only."""
import argparse
import subprocess
from pathlib import Path
from h1719_run_saved_suite import PINS, digest, save


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    for name,sha in PINS.items():assert digest(root/name)==sha,name
    source=(root/'src/fsincos_skylake.c').read_text()
    fraction=(root/'experiments/h1715_internal_boundary_scan.c').read_text()
    fraction=fraction[fraction.index('static uint32_t h1715_fraction'):fraction.index('\nstatic void h1715_internal')]
    probe=root/'experiments/h1720_policy2_boundary_scan.c'
    driver=root/'experiments/h1720_policy2_boundary_driver.c'
    anchor='static wv_t acc_round_bits_mode(\n    u256 acc, int32_t scale, int bits, p5_round_t mode)\n{'
    assert source.count(anchor)==1
    source=source.replace(anchor,fraction+'\n'+probe.read_text()+'\n'+anchor+'\n    h1720_internal(acc,bits,mode);')
    anchor='static sf_t acc_round64_rc(u256 acc, int32_t scale, int neg_out, sf_rc_t rc)\n{'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+'\n    h1720_endpoint(acc);')
    source='#include <assert.h>\n#define main h1720_original_main\n'+source+'\n#undef main\n'+driver.read_text()
    out.mkdir(parents=True,exist_ok=False)
    with (out/'instrumented.c').open('x') as f:f.write(source)
    build=subprocess.run(['cc','-O2','-std=c11','-ffp-contract=off','-I',str(root/'src'),str(out/'instrumented.c'),'-lm','-o',str(out/'scanner')],capture_output=True,text=True)
    with (out/'build.stderr').open('x') as f:f.write(build.stderr)
    build.check_returncode()
    evidence={str(x.relative_to(root)):digest(x) for x in [Path(__file__),probe,driver,root/'experiments/h1715_internal_boundary_scan.c']}
    save(out/'prepared.json',dict(status='SOFTWARE_ONLY_NOT_FROZEN',candidate_changed=False,
        sha256=dict(evidence={**PINS,**evidence},binary=digest(out/'scanner'),instrumented=digest(out/'instrumented.c'))))
    print('PASS passive instrumented build',flush=True)


if __name__=='__main__':main()
