#!/usr/bin/env python3
"""Verify promoted paired arithmetic, standalone isolation and opened hardware.

No captures, private access, new predictions after observation or paper claims.
"""
import argparse
import json
import random
import re
import subprocess
from collections import Counter
from pathlib import Path
import h1710_verify_paired_program as independent
import h1707_packaged_candidate_regression as standalone
import h1708_verify_promotion as previous
import h1712_score_paired_capture as capture
from h1713_promoted_regression import SOURCE, HEADER
from h1709_paired_retained_census import digest, save


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    assert digest(root/'src/fsincos_skylake.c')==SOURCE and digest(root/'src/general/paired.h')==HEADER
    identity=previous.header_identity(root);independent.constants(root)
    original=root/'tmp/ledger33/current/h1710_independent_paired_program'
    assert digest(original/'report.json')=='9800d366202639dac4f031fc7e8058db402f3dfe53ff1f1cadb2772bee4723a2'
    old=json.loads((original/'report.json').read_text())
    archived=original/'last_O2';assert digest(archived)==old['sha256']['binaries']['last_O2']
    standalone_old=root/'tmp/ledger33/current/h1708_default_promotion/O2'
    record=json.loads((root/'tmp/ledger33/current/h1708_default_promotion/report.json').read_text())
    assert digest(standalone_old)==record['sha256']['binaries']['O2']
    kit=root/'transfer-tests/h1712';freeze=json.loads((kit/'FREEZE.json').read_text())
    assert digest(kit/'FREEZE.json')=='3138415249016c51047ad56110826c2f700e7ec09037c292de22bae35e4a36fa'
    assert digest(kit/'manifest.json')==freeze['sha256']['manifest']
    assert digest(kit/'hardware-output/state-output.txt')=='c617a6851407bb5a890219e26883b582c2609c2a5c49c4a8cbcc86e457b6081e'
    manifest=json.loads((kit/'manifest.json').read_text());raw=(kit/'hardware-output/state-output.txt').read_text().splitlines()
    operands=set(json.loads((original/'inputs.json').read_text()));operands.update(r['operand'] for r in manifest)
    rng=random.Random(0x1713)
    for _ in range(4096):
        ef=rng.choice([0,1,0x7fff,*range(0x3fba,0x403f),rng.randrange(0x8000)])
        s=rng.getrandbits(64)
        if ef!=0x7fff:s|=1<<63
        operands.add(f'{ef|(rng.randrange(2)<<15):04x} {s:016x}')
    operands=sorted(operands);out.mkdir(parents=True);save(out/'inputs.json',operands)
    source=(root/'src/fsincos_skylake.c').read_text();counts=Counter();cache={};binaries={};warnings={}
    configs={'O0':['-O0'],'O2':['-O2'],'O3':['-O3'],'ubsan':['-O2','-fsanitize=undefined','-fno-sanitize-recover=all']}
    for label,flags in configs.items():
        binary=out/label
        build=subprocess.run(['cc',*flags,'-DG_GENERAL_TRACE=1','-Wall','-Wextra','-Wno-unused-const-variable',
            '-std=c11','-I',str(root/'src'),'-x','c','-','-lm','-o',str(binary)],input=source,text=True,capture_output=True,check=True)
        with (out/(label+'.build.log')).open('x') as f:f.write(build.stderr)
        warnings[label]=Counter(re.findall(r'warning: (.+?) \[(-W[^\]]+)\]',build.stderr))
        prior=(root/'tmp/ledger33/current/h1708_default_promotion/default.build.log').read_text()
        assert warnings[label]==Counter(re.findall(r'warning: (.+?) \[(-W[^\]]+)\]',prior))
        test=previous.run(binary,['--selftest']);assert test.stdout=='SELFTEST: ok\n'
        # Trace-enabled builds also report the selftest's two signed-zero
        # paired calls; neither belongs to a numbered input batch.
        assert test.stderr.splitlines()==['HPAIR 18446744073709551615 special 0 0 0']*2
        binaries[label]=digest(binary)
        for mode in ('rn','rd','ru','rz'):
            values,meta=independent.run(binary,mode,operands,True)
            old_values,old_meta=independent.run(archived,mode,operands,True)
            assert (values,meta)==(old_values,old_meta)
            for i,op in enumerate(operands):
                expected,metadata=independent.expected(op,mode,'last',cache)
                assert (values[i],meta.get(i))==(expected,metadata),(label,mode,op)
                counts['independent_paired_instruction_rows']+=1;counts['paired_lane_outputs']+=2 if expected else 0
            for insn in ('fsin','fcos'):
                assert standalone.cmodel.run(binary,insn,mode,operands)==standalone.cmodel.run(standalone_old,insn,mode,operands)
                counts['standalone_isolation_rows']+=len(operands)
        print(label,'independent paired and standalone isolation pass',flush=True)
    # The actual quiet Makefile binary, not only the audit build, is checked
    # against every immutable H1712 raw numerical/C1 observation.
    main=root/'src/fsincos_skylake';fresh={};fresh_counts=Counter();ops=sorted({r['operand'] for r in manifest})
    for mode in ('rn','rd','ru','rz'):
        values,meta=independent.run(main,mode,ops,True)
        quiet,_=independent.run(main,mode,ops,False);assert quiet==values
        for i,op in enumerate(ops):fresh[op,mode]=(values[i],meta.get(i))
    for row,line in zip(manifest,raw):
        value,meta=fresh[row['operand'],row['mode']];fields=capture.parse(line)
        assert all(capture.inspect(row,fields).values())
        if value is None:assert int(fields['A_SW'],16)&0x400;fresh_counts['C2']+=1
        else:
            assert value==(fields['A_R1'],fields['A_R0'])
            assert meta[1] and meta[3]==(int(fields['A_SW'],16)>>9)&1
            fresh_counts['outputs']+=2;fresh_counts['C1']+=1
        fresh_counts['tuples']+=1
    report=dict(experiment='h1713_verify_promotion',status='PASS_PROMOTED_IMPLEMENTATION',operands=len(operands),
        counts=dict(counts),opened_H1712=dict(fresh_counts),standalone_header_identity=identity,
        compiler_warnings=sum(warnings['O2'].values()),new_compiler_warnings=0,
        hardware_execution='none_replay_only',private_access='none',
        sha256=dict(source=SOURCE,header=HEADER,script=digest(Path(__file__)),binaries=binaries,
            main_binary=digest(main),inputs=digest(out/'inputs.json'),frozen_campaign=digest(kit/'FREEZE.json')))
    save(out/'report.json',report);print(report['status'],dict(counts),dict(fresh_counts),flush=True)


if __name__=='__main__':main()
