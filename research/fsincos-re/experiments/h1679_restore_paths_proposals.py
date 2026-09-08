#!/usr/bin/env python3
"""Fresh restoration-only proposals; recomputed ES/B remains a frozen hypothesis."""
import argparse
import json
import random
from collections import Counter
from pathlib import Path
from h1678_restore_paths_static import digest,LOCKS
from h1640_remaining_scope_freshness import save

STATIC='tmp/ledger33/current/h1678_restore_paths_static/report.json'

def proposals():
    rng=random.Random(0x1679); rows=[]; used=set(); serial=0
    profiles=[(0,63),(0,12)]
    for flags in (1,2,4,8,16,32,0x41,0x7f):
        profiles.extend(((flags,63),(flags,12 if flags==0x7f else 63^(flags&63))))
    for method in ('fxrstor','fldenv','frstor','fldcw','fnstenv'):
        for flags,masks in profiles:
            for summary in ((0,128,32768,32896) if method in ('fxrstor','fldenv','frstor') else (0,)):
                for order in ('scalar','fx'):
                    while True:
                        sig=rng.getrandbits(63)|(1<<63)|1
                        if sig not in used: break
                    used.add(sig); depth=1+serial%8; cc=sum(((serial>>i)&1)<<b for i,b in enumerate((8,9,10,14)))
                    mode,rc=(('rn',0),('rd',1024),('ru',2048),('rz',3072))[serial%4]
                    pc,pcbits=((24,0),(53,512),(64,768))[(serial//4)%3]
                    cw=0x40|masks|rc|pcbits; top=(-depth)%8; requested=(top<<11)|cc|flags|summary
                    final_cw=cw|63 if method=='fnstenv' else cw
                    final_sw=(requested&~0x8080)|(0x8080 if flags&~final_cw&63 else 0)
                    known=0xb8ff if method in ('fldcw','fnstenv') else 0xffff
                    for sign in (0,32768):
                        case=f'J{len(rows)+1:06d}'; operand=f'{0x3ffc|sign:04x} {sig:016x}'
                        capture=f'{case} {method} {order} {mode} pc{pc} {masks:02x} {depth} {cc:04x} {flags:02x} {summary:04x} {operand}'
                        saved=dict(CW=cw,SW=(requested&~0x8080)|(0x8080 if flags&~cw&63 else 0),TW=(1<<(2*top))-1) if method=='fnstenv' else dict(CW=0,SW=0,TW=0)
                        rows.append(dict(case_id=case,method=method,order=order,mode=mode,pc=pc,masks=masks,depth=depth,
                            cc=cc,flags=flags,summary=summary,operand=operand,requested_CW=cw,requested_SW=requested,
                            capture_line=capture,prediction=dict(CW=final_cw,SW=final_sw,SW_known_mask=known,
                                FTW=((1<<depth)-1)<<top,TOP=top,output=operand.replace(' ',':'),saved=saved),
                            unknown_fields=['FOP','FIP','FDP','unoccupied_registers']+(['post_CC'] if known!=0xffff else []),
                            execution_credit='restoration_only_no_transcendental_or_delivery'))
                    serial+=1
    assert len(rows)==1008==len({r['operand'] for r in rows}) and len(used)==504
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path); a=p.parse_args()
    root,out=a.root.resolve(),a.output_dir.resolve(); assert not out.exists()
    for name,sha in LOCKS.items(): assert digest(root/name)==sha,name
    audit=json.loads((root/STATIC).read_text()); assert audit['status']=='PASS_STATIC_NOT_EXECUTED'
    assert audit['sha256']['evidence']==LOCKS
    assert audit['sha256']['script']==digest(root/'experiments/h1678_restore_paths_static.py')
    rows=proposals(); out.mkdir(parents=True)
    bank=dict(experiment='h1679_restore_paths_proposals',capture_state='SOFTWARE_ONLY_NOT_FROZEN',rows=rows,
        method_counts=dict(Counter(r['method'] for r in rows)),hardware_execution='none',
        hypothesis='Actual ES=B=bool(flags & ~final_masks & 63), independently of requested ES/B and observation order.',
        claim_boundary='A hypothesis about five setup paths, not a physical pending selector or new numerical law. No FSIN/FCOS/FWAIT executes. Undefined condition codes and pointer fields are not predicted credit.',
        sha256=dict(script=digest(Path(__file__)),evidence=dict(LOCKS,**{STATIC:digest(root/STATIC),
            'experiments/h1678_restore_paths_static.py':digest(root/'experiments/h1678_restore_paths_static.py')})))
    save(out/'bank.json',bank); print(json.dumps(bank['method_counts'],sort_keys=True),flush=True)
if __name__=='__main__': main()
