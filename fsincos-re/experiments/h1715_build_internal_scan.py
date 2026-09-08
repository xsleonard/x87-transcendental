#!/usr/bin/env python3
"""Build only an instrumented copy; the main algorithm is unchanged."""
import argparse
import subprocess
from pathlib import Path
from h1709_paired_retained_census import digest,save
from h1714_build_rounding_scan import SOURCE


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    main=root/'src/fsincos_skylake.c';assert digest(main)==SOURCE
    source=main.read_text();probe=root/'experiments/h1715_internal_boundary_scan.c';driver=root/'experiments/h1715_internal_boundary_driver.c'
    anchor='static wv_t acc_round_bits_mode(\n    u256 acc, int32_t scale, int bits, p5_round_t mode)\n{'
    assert source.count(anchor)==1
    source=source.replace(anchor,probe.read_text()+'\n'+anchor+'\n    h1715_internal(acc,bits,mode);')
    anchor='static sf_t acc_round64_rc(u256 acc, int32_t scale, int neg_out, sf_rc_t rc)\n{'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+'\n    h1715_endpoint(acc);')
    source='#include <assert.h>\n#define main h1715_original_main\n'+source+'\n#undef main\n'+driver.read_text()
    out.mkdir(parents=True)
    with (out/'instrumented.c').open('x') as f:f.write(source)
    built=subprocess.run(['cc','-O2','-std=c11','-I',str(root/'src'),str(out/'instrumented.c'),'-lm','-o',str(out/'scanner')],text=True,capture_output=True)
    with (out/'build.stderr').open('x') as f:f.write(built.stderr)
    built.check_returncode()
    evidence={str(x.relative_to(root)):digest(x) for x in [main,probe,driver,Path(__file__),root/'src/ia64_sf.h',
        root/'src/p5_rom_constants.h',*sorted((root/'src/general').glob('*.h'))]}
    save(out/'prepared.json',dict(status='SOFTWARE_ONLY_NOT_FROZEN',candidate_changed=False,
        sha256=dict(evidence=evidence,binary=digest(out/'scanner'),instrumented=digest(out/'instrumented.c'))))
    print('PASS instrumented build')


if __name__=='__main__':main()
