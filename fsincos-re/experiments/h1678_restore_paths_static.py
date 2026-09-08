#!/usr/bin/env python3
"""Authenticate the restoration-only ELF and audit its no-wait observation CFG."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from h1640_remaining_scope_freshness import save

BUILD='tmp/ledger33/current/h1678_capture_build/'
LOCKS={
    'capture-kit/x87_restore_paths_capture.c':'afbd0cf2efe33a091c165623a49c2c3941fcda81f6b2df8d128f05f383059f16',
    BUILD+'x87_restore_paths_capture':'f093eb12fd2d2102bc5711618b69427b499d2bbdb907bfebbfc4700fbf134bee',
    BUILD+'capture.disassembly.txt':'b9fefc8c454c6f70112c501f6d8ae6af722c0306a4ba580ffd52e9a692f767ac',
    BUILD+'compiler.txt':'8c59c3b7b9051484db9a6b6576edf12a3aca7381a06a174a2d4dbfd6ce08681f',
    'tmp/pdfs/h1644-intel-sdm-089.txt':'2d0bdfd69ca26783461d6054aab6e20f5f1ee51cd412b704a93d2b296f753267',
}
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path); a=p.parse_args()
    root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    code={}; symbols={}
    for line in (root/BUILD/'capture.disassembly.txt').read_text().splitlines():
        label=re.fullmatch(r'([0-9a-f]+) <([^>]+)>:',line)
        if label: symbols[label[2]]=int(label[1],16)
        parts=line.split('\t')
        if len(parts)>=3 and re.fullmatch(r'\s*[0-9a-f]+:',parts[0]):
            code[int(parts[0].strip()[:-1],16)]=parts[2].split('#',1)[0].strip()
    addresses=sorted(code); following=dict(zip(addresses,addresses[1:]))
    all_ops=Counter(v.split()[0] for v in code.values())
    assert not any(all_ops[x] for x in ('fsin','fcos','fsincos','fwait','wait','fadd','fdiv','fmul'))
    allowed_fpu={'fninit','fldcw','fldt','fxsave64','fxrstor64','fnstenv','fldenv','frstor','fnstsw','fnstcw','fnclex'}
    assert {op for op in all_ops if op.startswith('f')}<=allowed_fpu
    cuts={}
    for name,expected in [('h1678_scalar_first',['fnstsw','fnstcw','fxsave64','fnclex','ret']),
                          ('h1678_fx_first',['fxsave64','fnstsw','fnstcw','fnclex','ret'])]:
        address=symbols[name]; seen=[]
        for expected_op in expected:
            assert code[address].split()[0]==expected_op
            seen.append(hex(address)); address=following[address]
        cuts[name]=seen
    sites={'fxrstor':0x171f,'fldenv':0x1a10,'frstor':0x1a1c,'fldcw':0x1a6a,'fnstenv':0x19ce}
    paths={}
    for method,start in sites.items():
        assert code[start].split()[0]==('fxrstor64' if method=='fxrstor' else method)
        pending=[(following[start],[])]; completed=[]
        while pending:
            address,seen=pending.pop(); assert address not in seen and len(seen)<50
            instruction=code[address]; op=instruction.split()[0]; seen=seen+[address]
            if op=='call':
                assert any('<'+name+'>' in instruction for name in cuts),instruction
                completed.append([hex(x) for x in seen]); continue
            assert not op.startswith('f') and op!='ret',instruction
            if op.startswith('j'):
                target=int(instruction.split()[1],16); pending.append((target,seen))
                if op=='jmp': continue
            pending.append((following[address],seen))
        assert len(completed)==2; paths[method]=completed
    assert code[0x1537]=='fninit' and code[0x1539].startswith('fldcw')
    assert '$0x7f,%ebx' in code[0x1527]
    assert code[0x1a61].startswith('fxrstor64') and following[0x1a61]==0x1a6a
    assert code[0x19c5].startswith('fxrstor64') and following[0x19c5]==0x19ce
    source=(root/'capture-kit/x87_restore_paths_capture.c').read_text()
    assert 'put16(seed.b,load_cw)' in source and 'requested&~0x8080u' in source
    manual=(root/'tmp/pdfs/h1644-intel-sdm-089.txt').read_text()
    assert 'The B-bit (bit 15) is included for 8087 compatibility only. It reflects the contents of the ES flag.' in manual
    assert 'then masks all floating-point exceptions.' in manual
    out.mkdir(parents=True)
    report=dict(experiment='h1678_restore_paths_static',status='PASS_STATIC_NOT_EXECUTED',
        observation_cuts=cuts,post_establishment_paths=paths,fpu_instruction_counts={k:all_ops[k] for k in sorted(allowed_fpu)},
        actual_FPU_executions=0,manifest_frozen=False,default_or_paper_change='none',
        claim_boundary='No transcendental or FWAIT opcode in ELF; five setup sites have two acyclic integer-only paths to no-wait observation/cleanup. Waiting setup begins under all masks. This is instrumentation validation, not observed restoration semantics or all-input silicon proof.',
        source_context=dict(url='https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf',
            sections=['Vol.1 8.1.3.3 and 8.6','Vol.2A FLDCW, FLDENV, FRSTOR, FNSTENV, FNSTSW, FXRSTOR'],
            limit='Architectural descriptions motivate the test; no promise that legacy restore establishes off-diagonal ES/B. Condition codes for FLDCW/FNSTENV remain unpredicted.'),
        sha256=dict(script=digest(Path(__file__)),evidence=LOCKS))
    save(out/'report.json',report); print(report['status'],flush=True)
if __name__=='__main__': main()
