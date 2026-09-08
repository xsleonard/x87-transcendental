#!/usr/bin/env python3
"""Authenticate read-only enumeration and limit testing to advertised XRSTOR."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from h1640_remaining_scope_freshness import save

BASE='tmp/ledger33/current/h1684_xsave_capabilities/'
LOCKS={
    'capture-kit/x87_xsave_capabilities.c':'23ec5cf8af023869a6b451fe5000042025f5b36a8447814094f4fad79c17c802',
    BASE+'x87_xsave_capabilities':'ba255368b465dd5646595210692ae56326745f8c0844611d6b7ab4a453d36fe3',
    BASE+'capability.disassembly.txt':'086c888d727efcb71509a61b604b21e6062f7e99533110a9419907da6440039e',
    BASE+'capabilities.txt':'17a60568824e046b1cea51320519118c1288f9b1d091bca4aef48e025da709dd',
    'tmp/pdfs/h1644-intel-sdm-089.txt':'2d0bdfd69ca26783461d6054aab6e20f5f1ee51cd412b704a93d2b296f753267',
}
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path); a=p.parse_args()
    root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    leaves={}; xcr0=None
    for line in (root/BASE/'capabilities.txt').read_text().splitlines():
        row=dict(word.split('=') for word in line.split())
        if 'XCR0' in row: assert xcr0 is None; xcr0=int(row['XCR0'],16); continue
        assert set(row)=={'LEAF','SUBLEAF','EAX','EBX','ECX','EDX'}
        key=tuple(int(row[k],16) for k in ('LEAF','SUBLEAF')); assert key not in leaves
        leaves[key]={k:int(row[k],16) for k in ('EAX','EBX','ECX','EDX')}
    vendor=b''.join(leaves[0,0][r].to_bytes(4,'little') for r in ('EBX','EDX','ECX')).decode()
    version=leaves[1,0]['EAX']; family=(version>>8)&15; model=((version>>4)&15)|((version>>12)&240)
    assert (vendor,family,model)==('GenuineIntel',6,85)
    assert leaves[1,0]['ECX']&(3<<26)==3<<26
    features=leaves[13,1]['EAX']; assert features==1 and xcr0==0x2e7
    assert (leaves[13,0]['EDX']<<32)|leaves[13,0]['EAX']==xcr0
    ops=[]
    for line in (root/BASE/'capability.disassembly.txt').read_text().splitlines():
        parts=line.split('\t')
        if len(parts)>=3 and re.fullmatch(r'\s*[0-9a-f]+:',parts[0]): ops.append(parts[2].split()[0])
    assert ops.count('xgetbv')==1 and 'cpuid' in ops
    assert not any(op.startswith('f') or op in ('xsetbv','wrmsr','rdmsr','xrstor','xrstor64','xsave','xsave64') for op in ops)
    actions=[dict(requested=r,image_present=s,action='skip' if not r else 'load' if s else 'initialize')
             for r in (0,1) for s in (0,1)]
    out.mkdir(parents=True)
    report=dict(experiment='h1684_xsave_capability_audit',status='READ_ONLY_CAPABILITY_SCOPE',
        host='45.32.204.118',vendor=vendor,family=family,model=model,xcr0=hex(xcr0),
        user_state_bits=[i for i in range(64) if xcr0>>i&1],standard_area_bytes=leaves[13,0]['EBX'],
        standard_XRSTOR=True,compacted_XRSTOR=False,XRSTORS=False,XGETBV_ECX1=False,XSAVEOPT=True,
        enumeration_anomalies=[dict(field='CPUID.0D.1.EBX',observed=hex(leaves[13,1]['EBX']),
            documented_without_XSAVEC_or_XSAVES='zero',action='Retain as virtual enumeration anomaly; do not use it as capability permission.')],
        x87_component_actions=actions,
        next_scope='Standard XRSTOR/XRSTOR64 with request masks 0/1, XSTATE_BV 0/1, all-zero XCOMP_BV/reserved header, 64-byte alignment. No other state component requested.',
        no_x87_or_restore_instruction_executed=True,processor_settings_changed=False,
        claim_boundary='Current host enumeration plus source-backed branch classification, not actual restore validation. Unsupported/privileged forms are not probed or silently counted covered.',
        manual_url='https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf',
        sha256=dict(script=digest(Path(__file__)),evidence=LOCKS))
    save(out/'report.json',report); print(json.dumps({k:report[k] for k in ('xcr0','standard_XRSTOR','compacted_XRSTOR','XRSTORS','enumeration_anomalies')},sort_keys=True),flush=True)
if __name__=='__main__': main()
