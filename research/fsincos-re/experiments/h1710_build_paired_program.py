#!/usr/bin/env python3
"""Assemble an explicitly enabled analysis-only paired program; defaults untouched."""
import argparse
import subprocess
from pathlib import Path
from h1709_paired_retained_census import SOURCE_SHA, digest


def source_string(root):
    path=root/'src/fsincos_skylake.c';assert digest(path)==SOURCE_SHA
    source=path.read_text()
    anchor='static fsincos_status_t fsincos_ref(x80_t in, x80_t *sin_out, x80_t *cos_out, sf_rc_t rc)\n{'
    assert source.count(anchor)==1
    prefix=('static fsincos_status_t h1710_paired_ref(x80_t, x80_t *, x80_t *, sf_rc_t);\n'
        '#ifndef G_H1710_PAIRED\n#define G_H1710_PAIRED 0\n#endif\n')
    source=source.replace(anchor,prefix+anchor+'\n    if (G_H1710_PAIRED) return h1710_paired_ref(in, sin_out, cos_out, rc);')
    anchor='static fsincos_status_t fsin_ref(x80_t in, x80_t *sin_out, sf_rc_t rc)'
    assert source.count(anchor)==1
    return source.replace(anchor,'#include "h1710_paired_program.h"\n\n'+anchor)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--opt',choices=('O0','O2','O3','ubsan'),default='O2')
    p.add_argument('--materialize',choices=('baseline','last','all'),default='baseline')
    a=p.parse_args();root=a.root.resolve();binary=a.binary.resolve();assert not binary.exists()
    flags=['-O2','-fsanitize=undefined','-fno-sanitize-recover=all'] if a.opt=='ubsan' else ['-'+a.opt]
    policy={'baseline':0,'last':1,'all':2}[a.materialize]
    proc=subprocess.run(['cc',*flags,'-std=c11','-DG_H1710_PAIRED=1','-DG_H1710_MATERIALIZE='+str(policy),'-I',str(root/'src'),'-I',str(root/'experiments'),
        '-x','c','-','-lm','-o',str(binary)],input=source_string(root),text=True,capture_output=True,check=True)
    assert not proc.stderr
    test=subprocess.run([str(binary),'--selftest'],text=True,capture_output=True,check=True)
    assert test.stdout=='SELFTEST: ok\n' and not test.stderr
    print(binary, digest(binary))


if __name__=='__main__': main()
